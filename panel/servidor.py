# Panel IA Sony - servidor local (solo 127.0.0.1:8099). Python 3.12, sin dependencias.
import json, os, subprocess, sys, threading, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compat
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

HOST, PORT = "127.0.0.1", int(os.environ.get("SONY_PUERTO", "8099"))  # SONY_PUERTO: solo para pruebas en otro puerto
BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
LLAMA_URL = "http://127.0.0.1:11434"  # Ollama (compartido)

HISTORY = deque(maxlen=300)  # 300 muestras x 2 s = 10 min
LOCK = threading.Lock()


def ram():
    total, disp = compat.memoria()
    return {"total": total, "used": total - disp, "commit_total": total, "commit_used": total - disp}


def run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def gpu():
    return None  # Apple Silicon: memoria unificada, sin gráfica aparte (ver ram())


def gpu_procs():
    return []


def model():
    try:
        with urllib.request.urlopen(LLAMA_URL + "/v1/models", timeout=1) as r:
            data = json.loads(r.read())
            ids = [m.get("id") for m in data.get("data", []) if str(m.get("id", "")).startswith("qwen-sony")]
            return ids[0] if ids else None
    except Exception:
        return None


def sampler():
    while True:
        s = {"t": time.time(), "ram": ram(), "gpu": gpu()}
        with LOCK:
            HISTORY.append(s)
        time.sleep(2)


def snapshot():
    with LOCK:
        hist = list(HISTORY)
    cur = hist[-1] if hist else {"ram": ram(), "gpu": gpu()}
    return {"now": cur, "procs": gpu_procs(), "model": model(),
            "history": [{"t": h["t"], "ram": round(h["ram"]["used"], 2),
                         "vram": round(h["gpu"]["vram_used"], 2) if h["gpu"] else 0,
                         "util": h["gpu"]["util"] if h["gpu"] else 0} for h in hist]}


ROUTES = {}  # otras partes (chat, nebulosa) se registran aqui


class Handler(BaseHTTPRequestHandler):
    server_version = "PanelIA"

    def log_message(self, *a):
        pass

    def guard(self):
        self.rol = None
        remoto = None  # acceso remoto (Tailscale) desactivado en el Mac
        if remoto and remoto.es_remota(self):
            # Llega por Tailscale (tailscale serve): solo con PIN y según el perfil.
            if not remoto.origen_ok(self):
                self.send_error(403, "Origin no permitido"); return False
            ruta = urlparse(self.path).path.rstrip("/") or "/"
            if ruta == "/login" or ruta.startswith("/static/icono-sony-") or ruta in ("/static/manifest.webmanifest", "/sw.js"):
                return True  # el PIN, el icono y el service worker (sin datos; si /sw.js pidiera PIN, el iPhone no podría actualizarlo)
            rol = remoto.sesion(self)
            if not rol:
                if self.command == "GET" and not ruta.startswith("/api/"):
                    self.send_response(303); self.send_header("Location", "/login"); self.send_header("Content-Length", "0"); self.end_headers()
                else:
                    self.send(401, {"error": "Entra con tu PIN"})
                return False
            if not remoto.permitido(rol, self.command, ruta):
                self.send(403, {"error": "No disponible desde este perfil"}); return False
            self.rol = rol
            return True
        if self.headers.get("Host", "") not in ALLOWED_HOSTS:
            self.send_error(403, "Host no permitido"); return False
        origin = self.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            self.send_error(403, "Origin no permitido"); return False
        if self.command == "POST" and not origin:
            self.send_error(403, "Falta Origin"); return False
        return True

    def send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        extra = dict(extra or {})
        self.send_header("Cache-Control", extra.pop("Cache-Control", "no-store"))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def static(self, name):
        f = (STATIC / name).resolve()
        if STATIC not in f.parents or not f.is_file():
            return self.send(404, {"error": "no existe"})
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}
        self.send(200, f.read_bytes(), types.get(f.suffix, "application/octet-stream"))

    def dispatch(self):
        if not self.guard():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        key = (self.command, path)
        if key in ROUTES:
            return ROUTES[key](self)
        for (m, p), fn in ROUTES.items():
            if m == self.command and p.endswith("/*") and path.startswith(p[:-1]):
                return fn(self)
        if self.command == "GET":
            if path == "/":
                return self.static("panel.html")
            if path == "/api/stats":
                return self.send(200, snapshot())
            if path.startswith("/static/"):
                return self.static(path[len("/static/"):])
        self.send(404, {"error": "no encontrado"})

    def seguro(self):
        """Ningún fallo de una ruta tumba la respuesta en silencio: se apunta en el log y se devuelve un error legible."""
        try:
            self.dispatch()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # el navegador cerró la conexión (por ejemplo, al parar una respuesta)
        except Exception as e:
            import traceback
            print(f"[error] {time.strftime('%Y-%m-%d %H:%M:%S')} {self.command} {self.path}\n{traceback.format_exc()}", flush=True)
            try:
                self.send(500, {"error": f"Error interno ({type(e).__name__}). Está apuntado en ~/IA/logs/servidor.log"})
            except Exception:
                pass

    do_GET = seguro
    do_POST = seguro
    do_DELETE = seguro


def main():
    for mod in ("chat", "correo", "buscador", "google_con", "github_con", "agente", "programador", "claude_api", "redes", "skills_panel", "diario", "nebulosa", "cerebro_rag", "estado_conectores", "nucleo_api"):
        try:
            __import__(mod).register(ROUTES)
        except Exception as e:
            print(f"[aviso] módulo {mod} no cargado: {type(e).__name__}: {e}")
    compat.rotar_logs()
    threading.Thread(target=sampler, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Panel IA en http://{HOST}:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE))
    main()
