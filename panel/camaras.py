# Cámaras Dahua en Sony: vista en directo (go2rtc, sin recodificar: casi 0 CPU y 0 gráfica) y PTZ/zoom por la API CGI de Dahua.
# - go2rtc (v1.9.15, sha256 comprobado con GitHub) escucha SOLO en 127.0.0.1:1984; todo pasa por el panel (local y Tailscale).
# - Arranca al abrir la pestaña Cámaras y se para a los 5 minutos sin mirar. Nada arranca con Windows.
# - Usuario y contraseña en el Administrador de credenciales; nunca en archivos, registros ni el cerebro (go2rtc los recibe por variables de entorno).
# - El perfil invitada no tiene acceso.
import json, subprocess, threading, time, urllib.parse, urllib.request
from pathlib import Path

import chat
import correo

DIR = Path(r"~/IA\camaras"); EXE = DIR / "go2rtc.exe"; CFG = DIR / "go2rtc.yaml"
G2R = "http://127.0.0.1:1984"
NO_WINDOW = 0x08000000
PARAR_TRAS_S = 300
# Orden de la cuadrícula: las 3 motorizadas primero (PTZ), luego el resto (zoom motorizado). La lista está en privado.json.
import privado
CAMARAS = [tuple(x) for x in privado.get("camaras", [])]  # nombre, IP, tipo: en privado.json
_proc = {"p": None, "uso": 0.0}
_lock = threading.Lock()


def _id(ip):
    return "c" + ip.rsplit(".", 1)[1]


def credenciales():
    return correo.cred_leer("camaras")  # (usuario, contraseña) o (None, None)


def _config():
    lineas = ["api:", '  listen: "127.0.0.1:1984"', "rtsp:", '  listen: ""', "webrtc:", '  listen: ""', "log:", "  level: warn", "streams:"]
    for _, ip, _t in CAMARAS:
        for nombre, sub in (("sub", 1), ("main", 0)):
            lineas.append(f"  {_id(ip)}_{nombre}: rtsp://${{CAM_USER}}:${{CAM_PASS}}@{ip}:554/cam/realmonitor?channel=1&subtype={sub}")
    CFG.write_text("\n".join(lineas) + "\n", encoding="utf-8")  # sin contraseñas: van por variables de entorno


def arrancar():
    with _lock:
        _proc["uso"] = time.time()
        if _proc["p"] and _proc["p"].poll() is None:
            return True
        u, p = credenciales()
        if not p or (DIR / "PAUSA").exists():  # 16/11: pausa mientras el usuario/clave fallan (evita bloquear las cuentas Dahua)
            return False
        _config()
        env = {**__import__("os").environ, "CAM_USER": urllib.parse.quote(u or "admin", safe=""), "CAM_PASS": urllib.parse.quote(p, safe="")}
        log = open(chat.LOGS / "go2rtc.log", "ab")
        _proc["p"] = subprocess.Popen([str(EXE), "-config", str(CFG)], cwd=str(DIR), env=env, stdout=log, stderr=log, creationflags=NO_WINDOW)
    for _ in range(40):
        try:
            urllib.request.urlopen(G2R + "/api", timeout=0.5); return True
        except Exception:
            time.sleep(0.25)
    return True


def parar():
    with _lock:
        p = _proc["p"]
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except Exception:
                p.kill()
        _proc["p"] = None


def vigilante():
    while True:
        time.sleep(30)
        if _proc["p"] and time.time() - _proc["uso"] > PARAR_TRAS_S:
            parar()


def _dahua(ip, ruta):
    u, p = credenciales()
    gestor = urllib.request.HTTPPasswordMgrWithDefaultRealm(); gestor.add_password(None, f"http://{ip}/", u or "admin", p or "")
    abre = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(gestor), urllib.request.HTTPBasicAuthHandler(gestor))
    with abre.open(f"http://{ip}{ruta}", timeout=6) as r:
        return r.status, r.read(500).decode("utf-8", "replace")


# ---------- API ----------
def _no_invitada(h):
    if getattr(h, "rol", None) == "invitada":
        h.send(403, {"error": "no disponible"}); return False
    return True


def api_lista(h):
    if not _no_invitada(h):
        return
    h.send(200, {"credenciales": bool(credenciales()[1]), "activo": bool(_proc["p"] and _proc["p"].poll() is None),
                 "camaras": [{"id": _id(ip), "nombre": n, "ip": ip, "tipo": t} for n, ip, t in CAMARAS]})


def api_g2r(h):
    """Pasa las peticiones de vídeo (MP4/HLS) a go2rtc local, en tiempo real."""
    if not _no_invitada(h):
        return
    if not arrancar():
        return h.send(400, {"error": "Falta el usuario y la contraseña de las cámaras (Ajustes → Conectores → Cámaras)."})
    _proc["uso"] = time.time()
    ruta = h.path[len("/api/camaras/g2r/"):]
    try:
        r = urllib.request.urlopen(f"{G2R}/api/{ruta}", timeout=20)
    except urllib.error.HTTPError as e:
        return h.send(e.code, {"error": f"go2rtc {e.code}"})
    except Exception as e:
        return h.send(502, {"error": str(e)[:120]})
    h.send_response(200)
    for k in ("Content-Type", "Content-Length"):
        if r.headers.get(k):
            h.send_header(k, r.headers[k])
    h.send_header("Cache-Control", "no-store"); h.end_headers()
    try:
        while True:
            b = r.read(65536)
            if not b:
                break
            h.wfile.write(b); h.wfile.flush(); _proc["uso"] = time.time()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        r.close()


CODIGOS = {"arriba": "Up", "abajo": "Down", "izquierda": "Left", "derecha": "Right", "acercar": "ZoomTele", "alejar": "ZoomWide"}


def api_ptz(h):
    if not _no_invitada(h):
        return
    d = chat.leer_cuerpo(h)
    cam = next((c for c in CAMARAS if _id(c[1]) == d.get("id")), None)
    if not cam:
        return h.send(404, {"error": "cámara desconocida"})
    ip, tipo = cam[1], cam[2]
    try:
        if d.get("preset"):
            ruta = f"/cgi-bin/ptz.cgi?action=start&channel=1&code=GotoPreset&arg1=0&arg2={int(d['preset'])}&arg3=0"
        else:
            codigo = CODIGOS.get(d.get("accion"))
            if not codigo or (tipo != "ptz" and codigo not in ("ZoomTele", "ZoomWide")):
                return h.send(400, {"error": "esa cámara no se mueve, solo hace zoom"})
            accion = "stop" if d.get("parar") else "start"
            vel = max(1, min(8, int(d.get("velocidad", 4))))
            ruta = f"/cgi-bin/ptz.cgi?action={accion}&channel=1&code={codigo}&arg1=0&arg2={vel}&arg3=0"
        estado, txt = _dahua(ip, ruta)
        h.send(200, {"ok": "OK" in txt or estado == 200})
    except urllib.error.HTTPError as e:
        h.send(e.code, {"error": "La cámara rechazó el usuario o la contraseña." if e.code == 401 else f"Error {e.code}"})
    except Exception as e:
        h.send(502, {"error": str(e)[:120]})


def api_config(h):
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se cambia desde el PC."})
    d = chat.leer_cuerpo(h)
    if d.get("borrar"):
        correo.cred_borrar("camaras"); parar(); return h.send(200, {"ok": True})
    if d.get("probar"):  # el usuario prueba SUS credenciales contra una cámara (una sola petición)
        try:
            estado, txt = _dahua(CAMARAS[0][1], "/cgi-bin/magicBox.cgi?action=getDeviceType")
            return h.send(200, {"ok": True, "respuesta": txt.strip()[:80]})
        except urllib.error.HTTPError as e:
            return h.send(200, {"ok": False, "error": "Usuario o contraseña incorrectos." if e.code == 401 else f"Error {e.code}"})
        except Exception as e:
            return h.send(200, {"ok": False, "error": str(e)[:120]})
    u, p = (d.get("usuario") or "admin").strip(), d.get("contrasena") or ""
    if not p:
        return h.send(400, {"error": "Falta la contraseña"})
    correo.cred_guardar("camaras", u, p); parar()
    h.send(200, {"ok": True})


def pagina(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no disponible"})
    h.static("camaras.html")


def register(R):
    R[("GET", "/camaras")] = pagina
    R[("GET", "/api/camaras/lista")] = api_lista
    R[("GET", "/api/camaras/g2r/*")] = api_g2r
    R[("POST", "/api/camaras/ptz")] = api_ptz
    R[("POST", "/api/camaras/config")] = api_config
    threading.Thread(target=vigilante, daemon=True).start()
