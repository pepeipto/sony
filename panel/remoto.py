# Acceso desde el móvil por Tailscale («tailscale serve»): solo dentro de la red privada del usuario, siempre con PIN.
# Perfiles: «usuario» (todo, como en el PC) e «invitada» (solo chatear con Qwen 27B, sin datos ni herramientas del usuario).
import hashlib, hmac, json, os, secrets, threading, time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import chat

F = Path(__file__).resolve().parent / "remoto.json"  # solo hashes de los PIN, nunca el PIN en claro
_sesiones = {}  # token -> {"rol", "exp"}
_fallos = {"n": 0, "hasta": 0}
_lock = threading.Lock()
DURACION = 12 * 3600

INVITADA_OK = [  # (método, ruta o prefijo) que puede usar el perfil invitada
    ("GET", "/chat"), ("GET", "/static/"), ("GET", "/api/chat/estado"), ("POST", "/api/chat/completar"), ("POST", "/api/chat/titulo"),
    ("POST", "/api/chat/cargar"), ("GET", "/api/hilos"), ("GET", "/api/hilos/"), ("POST", "/api/hilos/"), ("DELETE", "/api/hilos/"),
    ("GET", "/api/ajustes"), ("POST", "/api/voz/"), ("GET", "/api/voz/"), ("GET", "/api/sesion"), ("POST", "/api/adjuntos"),
    ("GET", "/api/proyectos"), ("GET", "/api/programados"), ("POST", "/api/salir"),
    ("GET", "/sw.js"), ("GET", "/api/push/"), ("POST", "/api/push/"),
]


def config():
    return chat.leer(F, {})


def _hash(pin, sal):
    return hashlib.scrypt(pin.encode(), salt=bytes.fromhex(sal), n=2 ** 14, r=8, p=1).hex()


def es_remota(h):
    host = (h.headers.get("Host") or "").lower().split(":")[0]
    return host.endswith(".ts.net") or bool(h.headers.get("Tailscale-User-Login")) or bool(h.headers.get("X-Forwarded-For"))


def origen_ok(h):
    o = h.headers.get("Origin")
    if not o:
        return h.command != "POST"
    return urlparse(o).hostname and urlparse(o).hostname.endswith(".ts.net") and o.startswith("https://")


def sesion(h):
    ck = h.headers.get("Cookie") or ""
    tok = next((p.split("=", 1)[1] for p in ck.split("; ") if p.startswith("sony_sesion=")), None)
    s = _sesiones.get(tok) if tok else None
    if s and s["exp"] > time.time():
        return s["rol"]
    return None


def permitido(rol, metodo, ruta):
    if rol == "usuario":
        return not ruta.startswith("/api/remoto")  # los PIN solo se cambian desde el PC
    if rol == "invitada":
        return any(m == metodo and (ruta == p or (p.endswith("/") and ruta.startswith(p))) for m, p in INVITADA_OK)
    return False


PAGINA = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sony</title><link rel="apple-touch-icon" href="/static/icono-sony-180.png"><link rel="icon" type="image/png" href="/static/icono-sony-192.png"><link rel="manifest" href="/static/manifest.webmanifest"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Sony"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="theme-color" content="#0e0c0c"><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(700px 400px at 50% 110%,rgba(150,18,34,.25),transparent 60%),#0e0c0c;font:16px system-ui,sans-serif;color:#f1e9e6}
form{background:#1b1717;border:1px solid #3a2e2e;padding:28px;border-radius:20px;box-shadow:0 8px 32px rgba(60,0,8,.45);width:min(320px,88vw);text-align:center;box-sizing:border-box}form::before{content:"";display:block;width:72px;height:72px;margin:0 auto 12px;border-radius:18px;background:url(/static/icono-sony-192.png) center/cover;box-shadow:0 0 18px rgba(255,46,72,.35)}
h1{font:400 30px Georgia,serif;margin:0 0 6px}p{color:#bfaea9;margin:0 0 18px}input{width:100%;box-sizing:border-box;font-size:22px;text-align:center;letter-spacing:.3em;padding:12px;border:1px solid #3a2e2e;border-radius:12px;background:#141111;color:#f1e9e6}
button{margin-top:14px;width:100%;padding:12px;border:0;border-radius:12px;background:linear-gradient(180deg,#e0334b,#b81d33);color:#fff;font-size:16px}.e{color:#ff6b7d;margin-top:10px}</style></head>
<body><form method="post" action="/login"><h1>Sony</h1><p>Escribe tu PIN</p><input name="pin" type="password" inputmode="numeric" autocomplete="current-password" autofocus>
<button>Entrar</button>__ERR__</form></body></html>"""


def login(h):
    if h.command == "GET":
        return h.send(200, PAGINA.replace("__ERR__", ""), "text/html; charset=utf-8")
    if time.time() < _fallos["hasta"]:
        return h.send(429, PAGINA.replace("__ERR__", '<div class="e">Demasiados intentos. Espera unos minutos.</div>'), "text/html; charset=utf-8")
    n = int(h.headers.get("Content-Length", 0))
    pin = parse_qs(h.rfile.read(n).decode()).get("pin", [""])[0].strip()
    cfg = config(); rol = None
    coinciden = [r for r in ("usuario", "invitada")
                 if cfg.get(r) and pin and hmac.compare_digest(_hash(pin, cfg[r]["sal"]), cfg[r]["hash"])]
    rol = coinciden[0] if coinciden else None  # el del usuario manda (antes ganaba «invitada» si los dos PIN eran iguales)
    if len(coinciden) == 2:
        chat_log("aviso_pines_iguales")
    if not rol:
        with _lock:
            _fallos["n"] += 1
            if _fallos["n"] >= 5:
                _fallos.update(n=0, hasta=time.time() + 600)
        chat_log("login_fallido")
        return h.send(401, PAGINA.replace("__ERR__", '<div class="e">PIN incorrecto.</div>'), "text/html; charset=utf-8")
    _fallos["n"] = 0
    tok = secrets.token_urlsafe(32)
    _sesiones[tok] = {"rol": rol, "exp": time.time() + DURACION}
    chat_log("login", rol=rol, quien=h.headers.get("Tailscale-User-Login", ""))
    h.send_response(303)
    h.send_header("Location", "/chat")
    h.send_header("Set-Cookie", f"sony_sesion={tok}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={DURACION}")
    h.send_header("Content-Length", "0"); h.end_headers()


def salir(h):
    ck = h.headers.get("Cookie") or ""
    tok = next((p.split("=", 1)[1] for p in ck.split("; ") if p.startswith("sony_sesion=")), None)
    _sesiones.pop(tok, None)
    h.send(200, {"ok": True}, extra={"Set-Cookie": "sony_sesion=; Path=/; Max-Age=0; Secure"})


def chat_log(evento, **d):
    with open(r"~/IA\logs\remoto.log", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "evento": evento, **d}, ensure_ascii=False) + "\n")


def api_sesion(h):
    h.send(200, {"remoto": getattr(h, "rol", None) is not None, "rol": getattr(h, "rol", None) or "local"})


def api_pines(h):
    # Solo desde el propio PC (el servidor ya bloquea /api/remoto a quien entra por Tailscale).
    if h.command == "GET":
        cfg = config()
        return h.send(200, {"usuario": "usuario" in cfg, "invitada": "invitada" in cfg, "acceso_movil": cfg.get("acceso_movil", False)})
    d = chat.leer_cuerpo(h); cfg = config()
    for r in ("usuario", "invitada"):
        pin = str(d.get(r) or "").strip()
        if pin:
            if not pin.isdigit() or len(pin) < 6:
                return h.send(400, {"error": "El PIN debe tener al menos 6 números."})
            otro = cfg.get("invitada" if r == "usuario" else "usuario")
            if otro and hmac.compare_digest(_hash(pin, otro["sal"]), otro["hash"]):
                return h.send(400, {"error": "El PIN del usuario y el de la invitada tienen que ser distintos."})
            sal = secrets.token_hex(16); cfg[r] = {"sal": sal, "hash": _hash(pin, sal)}
        if d.get("quitar_" + r):
            cfg.pop(r, None)
    if "acceso_movil" in d:
        cfg["acceso_movil"] = bool(d["acceso_movil"])
    chat.escribir(F, cfg); _sesiones.clear()
    h.send(200, {"usuario": "usuario" in cfg, "invitada": "invitada" in cfg, "acceso_movil": cfg.get("acceso_movil", False)})


TS = Path(r"C:\Program Files\Tailscale\tailscale.exe")


def api_tailscale(h):
    # Estado de Tailscale (solo desde el PC). Tailscale no usa la gráfica.
    import subprocess
    if not TS.exists():
        return h.send(200, {"instalado": False})
    try:
        out = subprocess.run([str(TS), "status", "--json"], capture_output=True, text=True, timeout=10, creationflags=0x08000000).stdout
        st = json.loads(out or "{}")
        dns = (st.get("Self") or {}).get("DNSName", "").rstrip(".")
        return h.send(200, {"instalado": True, "estado": st.get("BackendState"), "direccion": f"https://{dns}" if dns else None})
    except Exception as e:
        return h.send(200, {"instalado": True, "estado": "parado", "error": str(e)[:120]})


def register(R):
    R[("GET", "/api/remoto/tailscale")] = api_tailscale
    R[("GET", "/login")] = login
    R[("POST", "/login")] = login
    R[("POST", "/api/salir")] = salir
    R[("GET", "/api/sesion")] = api_sesion
    R[("GET", "/api/remoto/pines")] = api_pines
    R[("POST", "/api/remoto/pines")] = api_pines
