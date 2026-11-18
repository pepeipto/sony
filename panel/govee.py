from pathlib import Path
import re
# Luces Govee de casa para Sony.
# - Preferido: control LOCAL por la red (LAN Control activado en Govee Home): UDP 4001/4003, instantáneo y sin internet.
# - Respaldo: API oficial en la nube (openapi.api.govee.com) con la clave del usuario, guardada en el Administrador de credenciales.
import json, socket, threading, time, urllib.request, uuid

import chat
import correo

API = "https://openapi.api.govee.com/router/api/v1"
_cache = {"t": 0, "nube": [], "lan": {}}


def clave():
    return correo.cred_leer("govee-api")[1]


def _api(metodo, ruta, datos=None):
    r = urllib.request.Request(API + ruta, data=json.dumps(datos).encode() if datos is not None else None, method=metodo,
                               headers={"Govee-API-Key": clave() or "", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=15) as resp:
        return json.loads(resp.read())


def buscar_lan(segundos=3):
    """Luces con LAN Control: responden al «scan» por multicast."""
    vistas = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", 4002)); s.settimeout(0.5)
        q = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); q.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        q.sendto(json.dumps({"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}).encode(), ("239.255.255.250", 4001)); q.close()
        fin = time.time() + segundos
        while time.time() < fin:
            try:
                d, a = s.recvfrom(4096); x = json.loads(d).get("msg", {}).get("data", {})
                vistas[x.get("device", a[0])] = {"ip": a[0], "sku": x.get("sku")}
            except socket.timeout:
                pass
    finally:
        s.close()
    return vistas


def dispositivos(refrescar=False):
    if refrescar or time.time() - _cache["t"] > 600:
        nube = []
        if clave():
            try:
                nube = [{"nombre": d.get("deviceName"), "sku": d.get("sku"), "id": d.get("device"),
                         "capacidades": [c.get("instance") for c in d.get("capabilities", [])]} for d in _api("GET", "/user/devices").get("data", [])]
            except Exception:
                nube = _cache["nube"]
        _cache.update(t=time.time(), nube=nube, lan=buscar_lan())
    out = []
    for d in _cache["nube"]:
        out.append({**d, "local": d["id"] in _cache["lan"], "ip": _cache["lan"].get(d["id"], {}).get("ip")})
    for dev, v in _cache["lan"].items():  # luces LAN que no estén en la nube
        if not any(o["id"] == dev for o in out):
            out.append({"nombre": f"Govee {v['sku']} ({v['ip']})", "sku": v["sku"], "id": dev, "local": True, "ip": v["ip"], "capacidades": []})
    return out


COLORES = {"rojo": (255, 0, 0), "verde": (0, 255, 0), "azul": (0, 0, 255), "blanco": (255, 255, 255), "amarillo": (255, 200, 0), "naranja": (255, 120, 0),
           "morado": (150, 0, 255), "rosa": (255, 80, 160), "cian": (0, 255, 255), "calido": (255, 170, 90), "cálido": (255, 170, 90), "frio": (200, 220, 255)}


def _lan(ip, cmd, data):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(json.dumps({"msg": {"cmd": cmd, "data": data}}).encode(), (ip, 4003)); s.close()


def controlar(d, accion, valor=None):
    """accion: encender | apagar | brillo (1-100) | color (nombre o #rrggbb)."""
    rgb = None
    if accion == "color":
        v = str(valor or "").strip().lower()
        rgb = COLORES.get(v) or (tuple(int(v.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if v.startswith("#") and len(v) == 7 else None)
        if not rgb:
            return f"No conozco el color «{valor}». Prueba con: {', '.join(list(COLORES)[:9])} o #rrggbb."
    if d.get("local") and d.get("ip"):
        if accion in ("encender", "apagar"):
            _lan(d["ip"], "turn", {"value": 1 if accion == "encender" else 0})
        elif accion == "brillo":
            _lan(d["ip"], "brightness", {"value": max(1, min(100, int(valor)))})
        elif accion == "color":
            _lan(d["ip"], "colorwc", {"color": {"r": rgb[0], "g": rgb[1], "b": rgb[2]}, "colorTemInKelvin": 0})
        return f"{d['nombre']}: {accion} (local)"
    if not clave():
        return f"{d['nombre']} no tiene LAN Control y falta la clave de Govee (Ajustes → Conectores → Govee)."
    cap = {"encender": ("devices.capabilities.on_off", "powerSwitch", 1), "apagar": ("devices.capabilities.on_off", "powerSwitch", 0),
           "brillo": ("devices.capabilities.range", "brightness", max(1, min(100, int(valor or 50)))),
           "color": ("devices.capabilities.color_setting", "colorRgb", (rgb[0] << 16) + (rgb[1] << 8) + rgb[2] if rgb else 0)}[accion]
    r = _api("POST", "/device/control", {"requestId": str(uuid.uuid4()), "payload": {"sku": d["sku"], "device": d["id"],
             "capability": {"type": cap[0], "instance": cap[1], "value": cap[2]}}})
    return f"{d['nombre']}: {accion} (nube) — {r.get('msg', 'ok')}"


def estado_luz(d):
    """Estado real de una luz (API oficial: device/state). Solo lectura."""
    import uuid
    try:
        r = _api("POST", "/device/state", {"requestId": uuid.uuid4().hex, "payload": {"sku": d["sku"], "device": d["id"]}})
        caps = {c.get("instance"): (c.get("state") or {}).get("value") for c in r.get("payload", {}).get("capabilities", [])}
        if caps.get("online") is False:
            return "sin conexión"
        enc = caps.get("powerSwitch")
        txt = "encendida" if enc == 1 else "apagada" if enc == 0 else "estado desconocido"
        if enc == 1:
            if caps.get("brightness") is not None:
                txt += f", brillo {caps['brightness']} %"
            col = caps.get("colorRgb")
            if isinstance(col, int) and col:
                txt += f", color #{col:06x}"
            elif caps.get("colorTemperatureK"):
                txt += f", blanco {caps['colorTemperatureK']} K"
        return txt
    except Exception as e:
        return f"estado no disponible ({type(e).__name__})"


# ---------- herramienta de Hermes ----------
def t_luces(a):
    accion = (a.get("accion") or "").lower().strip()
    if accion in ("", "listar", "lista", "estado"):
        ds = dispositivos(True)
        if not ds:
            return "No encuentro luces Govee."
        return "Luces Govee (estado REAL ahora mismo; no lo cambies si no te lo piden):\n" + "\n".join(
            f"- {d['nombre']} ({d['sku']}): {estado_luz(d)}{' · local' if d['local'] else ''}" for d in ds)
    if Path(__file__).with_name("_tutorial_sin_cambios").exists():  # durante pruebas de Claude: nunca se cambia una luz
        return "Modo prueba: ahora mismo no se cambian las luces (solo listar)."
    nombre = (a.get("nombre") or "").lower().strip()
    ds = dispositivos()
    elegidas = ds if nombre in ("todas", "todo", "*", "") else [d for d in ds if nombre in (d["nombre"] or "").lower()]
    if not elegidas:
        return f"No encuentro ninguna luz que se llame «{a.get('nombre')}». Usa accion=listar para ver los nombres."
    return "\n".join(controlar(d, accion, a.get("valor")) for d in elegidas[:30])


HERRAMIENTAS = {
    "luces_govee": (t_luces, False, "Manejar las luces Govee de casa",
                    {"accion": "string", "nombre": "string", "valor": "string"},
                    "Luces Govee de casa. accion: listar (da el estado REAL de cada luz: encendida/apagada, brillo y color; nunca lo inventes) | encender | apagar | brillo (valor 1-100) | color (valor: rojo, azul, cálido… o #rrggbb). "
                    "nombre: parte del nombre de la luz o «todas»."),
}


# ---------- API para Ajustes ----------
def api_config(h):
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se cambia desde el PC."})
    d = chat.leer_cuerpo(h)
    if d.get("borrar"):
        correo.cred_borrar("govee-api"); return h.send(200, {"ok": True})
    if d.get("probar"):
        try:
            ds = dispositivos(True)
            return h.send(200, {"ok": True, "total": len(ds), "local": sum(1 for x in ds if x["local"]), "nombres": [x["nombre"] for x in ds][:40]})
        except urllib.error.HTTPError as e:
            return h.send(200, {"ok": False, "error": "Clave no válida." if e.code in (401, 403) else f"Error {e.code}"})
        except Exception as e:
            return h.send(200, {"ok": False, "error": str(e)[:120]})
    k = (d.get("clave") or "").strip()
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", k)
    if m:  # el email de Govee trae «API GUID : …»; nos quedamos solo con la clave
        k = m.group(0)
    if len(k) < 20:
        return h.send(400, {"error": "Eso no parece una clave de Govee"})
    correo.cred_guardar("govee-api", "govee", k); _cache["t"] = 0
    h.send(200, {"ok": True})


def api_estado(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no disponible"})
    h.send(200, {"clave": bool(clave())})


def register(R):
    R[("POST", "/api/govee/config")] = api_config
    R[("GET", "/api/govee/estado")] = api_estado
