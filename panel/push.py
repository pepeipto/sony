# Notificaciones Web Push para Sony en el iPhone (iOS 16.4+, desde el icono de la pantalla de inicio).
# - Claves VAPID generadas aquí y guardadas en el Administrador de credenciales de Windows (nunca en archivos ni registros).
# - El texto es genérico («Sony te ha respondido»): pasa por los servidores de Apple, así que nunca va el contenido del chat.
# - Cada perfil (usuario / invitada) tiene sus suscripciones; la invitada solo recibe avisos de lo suyo.
import base64, json, threading, time
import privado
from pathlib import Path

import chat
import correo

F_SUBS = chat.CHATS / "_push.json"
LOG = Path(r"~/IA\logs\push.log")
_visto = {}  # rol -> última vez que la app estaba a la vista (para no avisar si la estás mirando)
_lock = threading.Lock()


def _log(evento, **d):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "evento": evento, **d}, ensure_ascii=False) + "\n")


def _vapid():
    from py_vapid import Vapid01
    from cryptography.hazmat.primitives import serialization
    pem = correo.cred_leer("vapid-privada")[1]
    if not pem:
        v = Vapid01(); v.generate_keys()
        pem = v.private_pem().decode() if isinstance(v.private_pem(), bytes) else v.private_pem()
        correo.cred_guardar("vapid-privada", "vapid", pem); _log("claves_vapid_creadas")
    v = Vapid01.from_pem(pem.encode())
    pub = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return v, base64.urlsafe_b64encode(pub).rstrip(b"=").decode()


def _rol(h):
    return getattr(h, "rol", None) or "usuario"


def avisar(rol, cuerpo, titulo="Sony", url="/", tag="sony", solo_si_no_mira=False):
    """Envía un aviso genérico a los dispositivos de ese perfil. No bloquea."""
    return  # avisos push (móvil) desactivados en el Mac
    if solo_si_no_mira and time.time() - _visto.get(rol, 0) < 30:
        return
    threading.Thread(target=_enviar, args=(rol, titulo, cuerpo, url, tag), daemon=True).start()


def _enviar(rol, titulo, cuerpo, url, tag):
    from pywebpush import webpush, WebPushException
    with _lock:
        subs = chat.leer(F_SUBS, {})
        lista = subs.get(rol, [])
        if not lista:
            return
        v, _ = _vapid(); vivos = []
        for s in lista:
            try:
                webpush(s["sub"], json.dumps({"titulo": titulo, "cuerpo": cuerpo, "url": url, "tag": tag}), vapid_private_key=v,
                        vapid_claims={"sub": privado.get("push_sub", "mailto:sony@localhost")}, ttl=3600, timeout=15)
                vivos.append(s)
            except WebPushException as e:
                code = getattr(e.response, "status_code", None)
                if code in (404, 410):
                    _log("suscripcion_caducada", rol=rol); continue  # el iPhone la quitó
                _log("error_push", rol=rol, code=code); vivos.append(s)
            except Exception as e:
                _log("error_push", rol=rol, error=type(e).__name__); vivos.append(s)
        subs[rol] = vivos; chat.escribir(F_SUBS, subs)
    _log("aviso", rol=rol, cuerpo=cuerpo, dispositivos=len(vivos))


# ---------- API ----------
def api_clave(h):
    h.send(200, {"publica": _vapid()[1]})


def api_suscribir(h):
    d = chat.leer_cuerpo(h); sub = d.get("sub") or {}
    if not str(sub.get("endpoint", "")).startswith("https://"):
        return h.send(400, {"error": "suscripción no válida"})
    rol = _rol(h)
    with _lock:
        subs = chat.leer(F_SUBS, {})
        lista = [s for s in subs.get(rol, []) if s["sub"].get("endpoint") != sub["endpoint"]]
        lista.append({"sub": sub, "desde": time.strftime("%d/%m/%Y %H:%M"), "disp": (d.get("disp") or "")[:60]})
        subs[rol] = lista; chat.escribir(F_SUBS, subs)
    _log("suscrito", rol=rol)
    avisar(rol, "Notificaciones activadas. Te avisaré aquí.", tag="prueba")
    h.send(200, {"ok": True})


def api_visible(h):
    _visto[_rol(h)] = time.time(); h.send(200, {"ok": True})


def api_estado(h):
    subs = chat.leer(F_SUBS, {})
    h.send(200, {"dispositivos": len(subs.get(_rol(h), []))})


def sw(h):
    b = (chat.BASE / "static" / "sw.js").read_bytes()
    h.send_response(200); h.send_header("Content-Type", "application/javascript; charset=utf-8")
    h.send_header("Service-Worker-Allowed", "/"); h.send_header("Cache-Control", "no-cache")
    h.send_header("Content-Length", str(len(b))); h.end_headers(); h.wfile.write(b)


def register(R):
    R[("GET", "/sw.js")] = sw
    R[("GET", "/api/push/clave")] = api_clave
    R[("POST", "/api/push/suscribir")] = api_suscribir
    R[("POST", "/api/push/visible")] = api_visible
    R[("GET", "/api/push/estado")] = api_estado
