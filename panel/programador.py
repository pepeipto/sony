# Motor de tareas programadas de Sony. Vive dentro del servidor de la app: solo funciona mientras está encendido.
# Nada en el arranque de Windows ni en el Programador de tareas de Windows.
#  - Tareas de IA: texto libre que hace el agente Hermes con Qwen 27B (sin cargar nunca otros modelos).
#  - Tareas de sistema (sin modelo, 0 de gráfica): recordatorio de citas y aviso de correos nuevos.
import datetime as dt, email, imaplib, json, re, ssl, subprocess, threading, time, uuid
from email.header import decode_header, make_header
from pathlib import Path

import chat

F_TAREAS = chat.F_PROG  # ~/IA\panel\chats\_programados.json (la lista que ve la app)
F_ESTADO = chat.CHATS / "_programador_estado.json"
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_lock = threading.Lock()
_corriendo = set()


def log(*a):
    with open(__import__("compat").LOGS / "programador.log", "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


def tareas():
    return chat.leer(F_TAREAS, [])


def guardar_tareas(ts):
    chat.escribir(F_TAREAS, ts)


def estado():
    return chat.leer(F_ESTADO, {"avisados_citas": {}, "correos_vistos": {}})


# ---------- avisos de Windows (sin ventanas) ----------
def notificar(titulo, texto):
    esc = lambda s: str(s).replace("\\", " ").replace('"', "'")[:200]
    try:
        subprocess.run(["osascript", "-e", f'display notification "{esc(texto)}" with title "{esc(titulo)}"'], timeout=20)
    except Exception as e:
        log("aviso_error", e)
    try:
        import telegram_con
        telegram_con.avisar(titulo, texto)  # también por Telegram si está emparejado
        import push
        push.avisar("usuario", "Tienes un aviso nuevo de Sony", tag="aviso")  # al móvil, sin el contenido
    except Exception as e:
        log("aviso_telegram_error", e)


# ---------- cuándo toca ----------
def ultima_programada(t, ahora):
    """Último momento programado <= ahora (o None)."""
    if t.get("cada_min"):
        return None
    try:
        hh, mm = map(int, (t.get("hora") or "09:00").split(":"))
    except ValueError:
        return None
    rep = t.get("repeticion") or ("semanal" if t.get("dias") else "diaria")
    if rep == "una":
        try:
            f = dt.datetime.fromisoformat(f"{t['fecha']}T{t['hora']}")
        except Exception:
            return None
        return f if f <= ahora else None
    for atras in range(0, 8):
        d = (ahora - dt.timedelta(days=atras)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if d > ahora:
            continue
        wd = d.weekday()
        if rep == "diaria" or (rep == "laborables" and wd < 5) or (rep == "semanal" and DIAS[wd] in (t.get("dias") or DIAS)):
            return d
    return None


def gpu_ocupada():
    if chat._proc.get("modelo") not in (None, "rapido") or chat._proc.get("estado") == "cargando":
        return True  # hay otro modelo (pesado, nocturno o una prueba)
    try:
        if chat._proc.get("modelo") == "rapido":
            return False  # nuestro modelo diario ya está cargado: se puede usar
        _t, disp = __import__("compat").memoria()
        if disp < 16.0:
            return True  # memoria justa: no se lanza una tarea que cargue el modelo
    except Exception:
        pass
    return False


# ---------- tareas de IA ----------
def ejecutar_ia(t):
    import agente
    if gpu_ocupada():
        return "reintentar"
    if not chat.cargar("rapido"):
        return "error: falta el modelo"
    for _ in range(600):
        if chat.llama_listo():
            break
        time.sleep(0.5)
    hid = uuid.uuid4().hex[:12]
    hilo = {"id": hid, "titulo": f"⏰ {t['nombre']} · {time.strftime('%d/%m %H:%M')}", "proyecto": t.get("proyecto"), "fijado": False,
            "programado": t["id"], "creado": time.time(), "mensajes": [{"rol": "user", "texto": t["prompt"], "t": time.time()}]}
    r = {"rol": "ia", "texto": "", "pasos": [], "t": time.time()}

    def ev(tipo, **d):
        if tipo == "texto":
            r["texto"] += d["texto"]
        elif tipo == "paso":
            p = next((x for x in r["pasos"] if x["id"] == d["id"]), None)
            if p:
                p.update({k: v for k, v in d.items() if k != "tipo"})
            else:
                r["pasos"].append({k: v for k, v in d.items() if k != "tipo"})

    cuerpo = {"mensajes": hilo["mensajes"], "proyecto": t.get("proyecto")}
    msgs, _ = chat.construir_mensajes(cuerpo)
    msgs[0]["content"] = (agente.SISTEMA_AGENTE + "\n\nEsta es una TAREA PROGRAMADA: El usuario no está delante. Haz lo que puedas sin permisos; "
                          "lo que necesite permiso quedará pendiente para él.\n\nSKILLS:\n" + agente.indice_skills() + "\n\n" + msgs[0]["content"])
    agente.ejecutar(msgs, agente.herramientas_para(hilo["mensajes"]), t.get("proyecto") or "-", ev, lambda *a: "pendiente")
    hilo["mensajes"].append(r)
    chat.escribir(chat.CHATS / f"{hid}.json", {**hilo, "actualizado": time.time()})
    pend = sum(1 for p in r["pasos"] if p.get("estado") == "pendiente")
    notificar(f"Sony · {t['nombre']}", (r["texto"].strip()[:180] or "Tarea hecha") + (f" · {pend} acción(es) esperan tu permiso" if pend else ""))
    return "hecho" + (f" ({pend} pendiente/s)" if pend else "")


# ---------- tareas de sistema (sin modelo) ----------
def _dec(v):
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return v or ""


def sistema_citas(t, est):
    import google_con
    ahora = dt.datetime.now(dt.timezone.utc); avisados = est["avisados_citas"]; n = 0
    margen = int(t.get("aviso_min") or 30)
    for email_g in google_con.cuentas_g():
        try:
            google_con._actual.email = email_g
            q = {"timeMin": ahora.isoformat().replace("+00:00", "Z"), "timeMax": (ahora + dt.timedelta(minutes=margen + 2)).isoformat().replace("+00:00", "Z"),
                 "singleEvents": "true", "orderBy": "startTime"}
            import urllib.parse
            r = google_con.g("GET", "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + urllib.parse.urlencode(q))
        except Exception as e:
            log("citas_error", email_g, e); continue
        for e in r.get("items", []):
            ini = e["start"].get("dateTime")
            if not ini:
                continue  # eventos de día completo: no se avisa
            clave = f"{e['id']}|{ini}"
            if clave in avisados:
                continue
            hora = ini[11:16]
            notificar(f"📅 {e.get('summary', 'Cita')} a las {hora}", " · ".join(x for x in [e.get("location"), email_g] if x))
            avisados[clave] = time.time(); n += 1
    for k in [k for k, v in avisados.items() if time.time() - v > 3 * 86400]:
        del avisados[k]
    return f"hecho ({n} aviso/s)"


def sistema_correos(t, est):
    import correo
    vistos = est["correos_vistos"]; nuevos = []
    for c in correo.cuentas():
        if not c.get("conectada"):
            continue
        try:
            m = correo.imap_abrir(c)
            m.select("INBOX", readonly=True)  # solo lectura: nunca marca como leído
            if c["proveedor"] in ("gmail", "google"):
                typ, d = m.uid("SEARCH", "X-GM-RAW", '"category:primary is:unread newer_than:2d"')
            else:
                typ, d = m.uid("SEARCH", None, "UNSEEN")
            uids = (d[0] or b"").split()[-30:]
            prev = set(vistos.get(c["id"], []))
            primera_vez = c["id"] not in vistos
            for u in uids:
                if u.decode() in prev:
                    continue
                typ, h = m.uid("FETCH", u, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                cab = email.message_from_bytes(h[0][1])
                if not primera_vez:
                    nuevos.append((c["nombre"], _dec(cab["From"]).split("<")[0].strip().strip('"'), _dec(cab["Subject"])))
            vistos[c["id"]] = [u.decode() for u in uids]
            m.logout()
        except Exception as e:
            log("correos_error", c["id"], e)
    if nuevos:
        if len(nuevos) == 1:
            cta, de, asunto = nuevos[0]; notificar(f"✉️ {de} ({cta})", asunto)
        else:
            notificar(f"✉️ {len(nuevos)} correos nuevos", " · ".join(f"{de}: {asunto}" for _, de, asunto in nuevos[:4]))
    return f"hecho ({len(nuevos)} nuevo/s)"


SISTEMA = {"citas": sistema_citas, "correos": sistema_correos}


# ---------- bucle ----------
def ejecutar_tarea(t, motivo):
    if t["id"] in _corriendo:
        return
    _corriendo.add(t["id"])
    try:
        log("ejecutar", t["nombre"], motivo)
        if t.get("tipo", "ia") == "ia":
            res = ejecutar_ia(t)
        else:
            with _lock:
                est = estado()
                res = SISTEMA[t["tipo"]](t, est)
                chat.escribir(F_ESTADO, est)
    except Exception as e:
        res = f"error: {e}"
    finally:
        _corriendo.discard(t["id"])
    with _lock:
        ts = tareas()
        for x in ts:
            if x["id"] == t["id"]:
                if res == "reintentar":
                    x["reintentar"] = time.time() + 600; x["ultimo_resultado"] = "saltada: gráfica ocupada (se reintenta en 10 min)"
                else:
                    x["ultima"] = time.time(); x["ultimo_resultado"] = res; x.pop("reintentar", None)
                    if x.get("repeticion") == "una":
                        x["pausada"] = True
        guardar_tareas(ts)
    log("resultado", t["nombre"], res)


def bucle():
    time.sleep(20)
    while True:
        try:
            ahora = dt.datetime.now()
            for t in tareas():
                if t.get("pausada"):
                    continue
                if t.get("reintentar") and time.time() < t["reintentar"]:
                    continue
                if t.get("cada_min"):
                    if time.time() - (t.get("ultima") or 0) >= t["cada_min"] * 60 - 5:
                        threading.Thread(target=ejecutar_tarea, args=(t, "intervalo"), daemon=True).start()
                    continue
                ult = ultima_programada(t, ahora)
                # toca si la última hora programada es posterior a la última ejecución (también cubre el PC apagado: se hace una vez)
                if ult and ult.timestamp() > (t.get("ultima") or t.get("creada") or 0):
                    threading.Thread(target=ejecutar_tarea, args=(t, "hora"), daemon=True).start()
        except Exception as e:
            log("bucle_error", e)
        time.sleep(30)


# ---------- API ----------
def api_ejecutar(h):
    tid = chat.leer_cuerpo(h).get("id")
    t = next((x for x in tareas() if x["id"] == tid), None)
    if not t:
        return h.send(404, {"error": "no existe"})
    threading.Thread(target=ejecutar_tarea, args=(t, "ahora"), daemon=True).start()
    h.send(200, {"ok": True})


def api_notificacion_prueba(h):
    notificar("Sony", "Prueba de aviso de Windows")
    h.send(200, {"ok": True})


def register(R):
    R[("POST", "/api/programados/ejecutar")] = api_ejecutar
    R[("POST", "/api/programados/prueba_aviso")] = api_notificacion_prueba
    threading.Thread(target=bucle, daemon=True).start()
