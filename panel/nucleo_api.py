# Datos de la pantalla «núcleo» de Sony: estado de las conexiones y lo de hoy. Solo lectura. Nunca inventa datos:
# si algo no está conectado, lo dice («sin conectar»).
import datetime as _dt, threading, time, urllib.parse

import chat

_cache = {"t": 0, "datos": None}
_lock = threading.Lock()


def _hoy_calendario():
    import google_con
    if not google_con.conectado():
        return None
    hoy = _dt.datetime.now().astimezone()
    ini = hoy.replace(hour=0, minute=0, second=0, microsecond=0); fin = ini + _dt.timedelta(days=1)
    r = google_con.g("GET", "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + urllib.parse.urlencode(
        {"timeMin": ini.isoformat(), "timeMax": fin.isoformat(), "singleEvents": "true", "orderBy": "startTime", "maxResults": 12}))
    out = []
    for e in r.get("items", []):
        s = e.get("start", {}); dt = s.get("dateTime")
        out.append({"hora": dt[11:16] if dt else "Todo el día", "texto": (e.get("summary") or "(sin título)")[:80], "fuente": "Calendario"})
    return out


def _datos():
    con = []
    try:
        import correo
        cs = correo.cuentas() if hasattr(correo, "cuentas") else []
        n = sum(1 for c in cs if c.get("conectada"))
        con.append({"nombre": "Correo", "ok": n > 0, "detalle": f"{n} cuenta{'s' if n != 1 else ''}" if n else "sin conectar"})
    except Exception:
        con.append({"nombre": "Correo", "ok": False, "detalle": "sin conectar"})
    try:
        import google_con
        g = google_con.conectado()
    except Exception:
        g = False
    con.append({"nombre": "Calendario", "ok": g, "detalle": "" if g else "sin conectar"})
    con.append({"nombre": "Drive", "ok": g, "detalle": "" if g else "sin conectar"})
    con.append({"nombre": "WhatsApp", "ok": False, "detalle": "sin conectar"})
    hoy, aviso = [], None
    try:
        cal = _hoy_calendario()
        if cal is None:
            aviso = "Calendario sin conectar"
        else:
            hoy += cal
    except Exception as e:
        aviso = f"No he podido leer el calendario ({type(e).__name__})"
    try:  # tareas programadas de Sony para hoy
        ahora = time.localtime()
        for p in chat.leer(chat.F_PROG, []) or []:
            if p.get("activa", p.get("activo", True)) is False or p.get("cada_min"):
                continue
            hora = str(p.get("hora") or "")[:5]
            rep = p.get("repeticion") or ("semanal" if p.get("dias") else "diaria")
            hoy_txt = time.strftime("%Y-%m-%d", ahora)
            toca = (rep == "diaria" or (rep == "una" and str(p.get("fecha", ""))[:10] == hoy_txt)
                    or (rep == "semanal" and str(ahora.tm_wday) in [str(x) for x in (p.get("dias") or [])]))
            if hora and toca:
                hoy.append({"hora": hora, "texto": str(p.get("titulo") or p.get("nombre") or "Tarea programada")[:80], "fuente": "Programado"})
    except Exception:
        pass
    hoy.sort(key=lambda x: x["hora"])
    return {"conexiones": con, "hoy": hoy[:8], "aviso": aviso, "t": time.time()}


def api_estado(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    if not _cache["datos"] or time.time() - _cache["t"] > 120:  # como mucho una consulta cada 2 minutos
        if _lock.acquire(blocking=not _cache["datos"]):  # si ya hay datos, nadie espera a Google: se dan los anteriores
            try:
                if not _cache["datos"] or time.time() - _cache["t"] > 120:
                    _cache["datos"] = _datos(); _cache["t"] = time.time()
            finally:
                _lock.release()
    h.send(200, _cache["datos"])


_mac = {"t": 0, "d": None}
_lock_mac = threading.Lock()


def _uso_mac():
    """Procesador, memoria y gráfica del Mac en % (lecturas locales: ps, vm_stat e ioreg)."""
    import re, subprocess, compat
    out = {"cpu": None, "mem": None, "gpu": None}
    try:
        ncpu = int(subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, timeout=3).stdout.strip() or 1)
        ps = subprocess.run(["ps", "-A", "-o", "%cpu="], capture_output=True, text=True, timeout=5).stdout.split()
        out["cpu"] = round(min(100.0, sum(float(x.replace(",", ".")) for x in ps) / ncpu), 1)
    except Exception:
        pass
    try:
        total, disp = compat.memoria()
        if total:
            out["mem"] = round(100 * (total - disp) / total, 1)
    except Exception:
        pass
    try:
        io = subprocess.run(["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r'"Device Utilization %"=(\d+)', io)
        if m:
            out["gpu"] = float(m.group(1))
    except Exception:
        pass
    return out


def api_mac(h):
    with _lock_mac:
        if not _mac["d"] or time.time() - _mac["t"] > 2:
            _mac["d"] = _uso_mac(); _mac["t"] = time.time()
        d = _mac["d"]
    h.send(200, d)


def register(R):
    R[("GET", "/api/nucleo/estado")] = api_estado
    R[("GET", "/api/nucleo/mac")] = api_mac
