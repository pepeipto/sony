# SAI Phasak Smart Pro PH 9230 (online, 3000 VA / 3000 W, onda senoidal pura), visto por Windows como «Batería SAI (UPS) HID».
# Por USB-HID Windows solo da: % de batería, autonomía estimada y si está en red o en batería. (Carga en W y voltajes
# los muestra la pantalla del SAI o el software oficial PowerMaster; aquí no.)
# - Apunta cada corte (paso a batería y vuelta) en ~/IA\logs\sai.jsonl.
# - Al pasar a batería: Sony descarga el modelo (menos consumo) y avisa por Telegram y al móvil.
# - Si la batería baja del % elegido (30 % por defecto) estando en batería: guarda y apaga el PC con 60 s de aviso.
import json, subprocess, threading, time
from pathlib import Path

import chat

LOG = Path(r"~/IA\logs\sai.jsonl")
F_CONF = Path(__file__).resolve().parent / "sai.json"
NO_WINDOW = 0x08000000
estado = {"ok": False, "pct": None, "min": None, "en_bateria": None, "visto": 0, "apagando": False}


def conf():
    c = chat.leer(F_CONF, {}); c.setdefault("apagado_pct", 30); c.setdefault("apagado_activo", True); return c


def _log(**d):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), **d}, ensure_ascii=False) + "\n")


def leer():
    ps = "Get-CimInstance Win32_Battery | Select-Object -First 1 EstimatedChargeRemaining,EstimatedRunTime,BatteryStatus | ConvertTo-Json -Compress"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
    d = json.loads(r.stdout) if r.stdout.strip() else None
    if not d:
        return None
    mins = d.get("EstimatedRunTime")
    return {"pct": d.get("EstimatedChargeRemaining"), "min": mins if mins and mins < 10000 else None,
            "en_bateria": d.get("BatteryStatus") == 1}  # 1 = descargando (en batería); 2 = en red


def _avisar(txt):
    for f in (lambda: __import__("telegram_con").enviar("🔋 " + txt), lambda: __import__("push").avisar("usuario", txt, tag="sai")):
        try:
            f()
        except Exception:
            pass


def bucle():
    while True:
        try:
            d = leer()
            if d:
                antes = estado.get("en_bateria")
                estado.update(ok=True, visto=time.time(), **d)
                if antes is not None and d["en_bateria"] != antes:
                    if d["en_bateria"]:
                        _log(evento="corte", pct=d["pct"], min=d["min"])
                        try:
                            chat.descargar()  # menos consumo mientras dure el corte
                        except Exception:
                            pass
                        _avisar(f"Se ha ido la luz: el PC va con el SAI ({d['pct']} %, unos {d['min'] or '?'} min). He descargado el modelo.")
                    else:
                        _log(evento="vuelve_luz", pct=d["pct"]); _avisar(f"Ha vuelto la luz (batería al {d['pct']} %).")
                c = conf()
                if d["en_bateria"] and c["apagado_activo"] and d["pct"] is not None and d["pct"] <= c["apagado_pct"] and not estado["apagando"]:
                    estado["apagando"] = True
                    _log(evento="apagado", pct=d["pct"]); _avisar(f"Batería al {d['pct']} %: apago el PC en 60 s de forma ordenada.")
                    try:
                        chat.descargar()
                    except Exception:
                        pass
                    subprocess.run(["shutdown", "/s", "/t", "60", "/c", f"SAI al {d['pct']} %: Sony apaga el PC para proteger los datos."],
                                   creationflags=NO_WINDOW)
            else:
                estado["ok"] = False
        except Exception:
            estado["ok"] = False
        time.sleep(30 if not estado.get("en_bateria") else 10)


def api_estado(h):
    cortes = []
    if LOG.exists():
        cortes = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines()[-20:] if l.strip()][::-1]
    h.send(200, {**{k: estado[k] for k in ("ok", "pct", "min", "en_bateria")}, "modelo": "Phasak Smart Pro PH 9230 (online, 3000 W)",
                 **conf(), "historial": cortes})


def api_config(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    d = chat.leer_cuerpo(h); c = conf()
    if "apagado_pct" in d:
        c["apagado_pct"] = max(15, min(80, int(d["apagado_pct"])))
    if "apagado_activo" in d:
        c["apagado_activo"] = bool(d["apagado_activo"])
    chat.escribir(F_CONF, c); h.send(200, c)


def t_sai(a):  # herramienta de solo lectura para Sony
    d = leer()
    if not d or not d.get("ok", True):
        return "No veo el SAI (¿cable USB conectado?)."
    return (f"SAI Phasak PH 9230: batería {d.get('pct')} %, autonomía ~{d.get('min')} min, "
            f"{'FUNCIONANDO CON BATERÍA (corte de luz)' if d.get('en_bateria') else 'con corriente normal'}.")


HERRAMIENTAS = {
    "sai_estado": (t_sai, False, "Ver el estado del SAI", {}, "Estado del SAI (sistema de alimentación ininterrumpida) del usuario: batería, autonomía y si hay corte de luz."),
}


def register(R):
    R[("GET", "/api/sai/estado")] = api_estado
    R[("POST", "/api/sai/config")] = api_config
    threading.Thread(target=bucle, daemon=True).start()
