# Correo de IA Sony: varias cuentas IMAP/SMTP. Las contraseñas las pega el usuario y se guardan
# guardadas en el Llavero de macOS (nunca en archivos ni en registros).
import base64, email, email.policy, imaplib, json, re, smtplib, ssl, subprocess, time
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path

import chat

CARP = Path(__file__).resolve().parent / "correo"; CARP.mkdir(exist_ok=True)
F_CUENTAS = CARP / "cuentas.json"
PROVEEDORES = {
    "gmail": {"nombre": "Gmail (Google)", "imap": ["imap.gmail.com", 993], "smtp": ["smtp.gmail.com", 465],
              "ayuda": "Necesitas la verificación en 2 pasos de Google y una «contraseña de aplicación» (myaccount.google.com/apppasswords). Pega esa contraseña de 16 letras, no la normal."},
    "google": {"nombre": "Google Workspace", "imap": ["imap.gmail.com", 993], "smtp": ["smtp.gmail.com", 465],
               "ayuda": "Igual que Gmail: verificación en 2 pasos + contraseña de aplicación (si el administrador lo permite)."},
    "ionos": {"nombre": "IONOS", "imap": ["imap.ionos.es", 993], "smtp": ["smtp.ionos.es", 465],
              "ayuda": "Usa la dirección completa y la contraseña de ese buzón de IONOS."},
    "microsoft": {"nombre": "Microsoft 365 / Outlook", "imap": ["outlook.office365.com", 993], "smtp": ["smtp.office365.com", 587],
                  "ayuda": "Microsoft ya no deja entrar con contraseña normal por IMAP; hará falta inicio de sesión oficial de Microsoft (se prepara cuando conectes)."},
    "otro": {"nombre": "Otro proveedor", "imap": ["", 993], "smtp": ["", 465], "ayuda": "Necesito el servidor IMAP/SMTP de tu proveedor."},
}
CUENTAS_INICIALES = [
    {"id": "personal", "nombre": "Personal", "color": "#5a7fa8", "direccion": "", "dominio": "gmail.com", "proveedor": "gmail"},
]
import privado as _privado  # noqa: E402
CUENTAS_INICIALES += _privado.get("cuentas_extra", [])


# ---------- Llavero de macOS ----------
from llavero import cred_guardar, cred_leer, cred_borrar  # noqa: E402


# ---------- cuentas ----------
def proveedor_de(dominio):
    if not dominio:
        return "pendiente"
    if dominio.lower() in ("gmail.com", "googlemail.com"):
        return "gmail"
    try:
        out = subprocess.run(["dig", "+short", "MX", dominio], capture_output=True, text=True, timeout=15).stdout.lower()
    except Exception:
        return "otro"
    if "google" in out:
        return "google"
    if "outlook" in out or "protection.outlook" in out:
        return "microsoft"
    if "ionos" in out or "1and1" in out:
        return "ionos"
    return "otro" if out.strip() else "pendiente"


def cuentas():
    cs = chat.leer(F_CUENTAS, None)
    if cs is None:
        cs = CUENTAS_INICIALES; chat.escribir(F_CUENTAS, cs)
    for c in cs:
        c["conectada"] = cred_leer(c["id"])[0] is not None or (c.get("oauth") == "google" and cred_leer(f"google-token/{c['direccion']}")[0] is not None)
        info = PROVEEDORES.get(c["proveedor"])
        c["proveedor_nombre"] = info["nombre"] if info else "Sin decidir: falta el dominio"
        c["ayuda"] = info["ayuda"] if info else "Dime la dirección de correo de esta cuenta y detecto el proveedor."
    return cs


def cuenta(cid):
    c = next((x for x in cuentas() if x["id"] == cid or x["nombre"].lower() == str(cid).lower()), None)
    if not c:
        raise ValueError(f"No existe la cuenta «{cid}». Cuentas: " + ", ".join(x["nombre"] for x in cuentas()))
    return c


def servidores(c):
    p = PROVEEDORES.get(c["proveedor"]) or PROVEEDORES["otro"]
    imap = c.get("imap") or p["imap"]; smtp = c.get("smtp") or p["smtp"]
    return imap, smtp


def _xoauth(c):
    import google_con
    tok = google_con.access_token(c["direccion"])
    return f"user={c['direccion']}\x01auth=Bearer {tok}\x01\x01"


def imap_abrir(c):
    if c.get("oauth") == "google":
        (host, port), _ = servidores(c)
        m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30)
        m.authenticate("XOAUTH2", lambda _: _xoauth(c).encode())
        return m
    usuario, clave = cred_leer(c["id"])
    if not usuario:
        raise PermissionError(f"La cuenta «{c['nombre']}» no está conectada. El usuario tiene que pulsar «Conectar» en Ajustes → Conectores.")
    (host, port), _ = servidores(c)
    m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30)
    m.login(usuario, clave)
    return m


def _dec(v):
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:
        return v or ""


def _texto(msg):
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain" and not p.get_filename():
                return p.get_content()
        for p in msg.walk():
            if p.get_content_type() == "text/html":
                return re.sub(r"<[^>]+>", " ", p.get_content())
        return ""
    return msg.get_content() if msg.get_content_type().startswith("text/") else ""


# ---------- herramientas del agente ----------
SIN_LEER = {"is:unread", "unread", "sin leer", "no leidos", "no leídos", "nuevos", "unseen"}


def t_buscar(a):
    # 15/11: sin cuenta → las tres (antes solo personal, y el agente repetía la llamada sin fin)
    if not (a.get("cuenta") or "").strip():
        try:
            if not any(c.get("conectada") for c in cuentas()):
                return "No hay ninguna cuenta de correo conectada. El usuario tiene que conectarla en Ajustes → Conectores."
        except Exception:
            pass
        partes = []
        for k in [x["id"] for x in CUENTAS_INICIALES]:
            try:
                partes.append(t_buscar({**a, "cuenta": k}))
            except Exception as e:
                partes.append(f"Cuenta {k}: no se pudo leer ({type(e).__name__}).")
        return "\n\n".join(partes)
    c = cuenta(a.get("cuenta", "personal")); m = imap_abrir(c)
    try:
        m.select("INBOX", readonly=True)
        q = (a.get("texto") or "").strip()
        if q.lower() in SIN_LEER:  # «is:unread» es de Gmail; en IMAP los no leídos son UNSEEN (antes salía siempre «Sin correos»)
            typ, data = m.uid("SEARCH", None, "UNSEEN")
        else:
            crit = ["ALL"] if not q else ["TEXT", '"' + q.replace('"', "") + '"']
            typ, data = m.uid("SEARCH", "CHARSET", "UTF-8", *crit) if q else m.uid("SEARCH", None, "ALL")
        uids = (data[0] or b"").split()[-int(a.get("maximo", 10)):][::-1]
        out = []
        for u in uids:
            typ, d = m.uid("FETCH", u, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            h = email.message_from_bytes(d[0][1])
            out.append(f"[{u.decode()}] {_dec(h['Date'])[:22]} · {_dec(h['From'])} · {_dec(h['Subject'])}")
        return f"Cuenta {c['nombre']} ({c['direccion']}):\n" + ("\n".join(out) or "Sin correos.")
    finally:
        m.logout()


def t_leer(a):
    c = cuenta(a.get("cuenta", "personal")); m = imap_abrir(c)
    try:
        m.select("INBOX", readonly=True)
        typ, d = m.uid("FETCH", str(a["id"]), "(BODY.PEEK[])")
        msg = email.message_from_bytes(d[0][1], policy=email.policy.default)
        adj = [p.get_filename() for p in msg.walk() if p.get_filename()]
        return (f"De: {msg['From']}\nPara: {msg['To']}\nFecha: {msg['Date']}\nAsunto: {msg['Subject']}\n"
                + (f"Adjuntos: {', '.join(adj)}\n" if adj else "") + "\n" + _texto(msg)[:15000])
    finally:
        m.logout()


def _nuevo(c, a):
    msg = EmailMessage(); msg["From"] = c["direccion"]; msg["To"] = a["para"]; msg["Subject"] = a.get("asunto", "")
    msg["Date"] = email.utils.formatdate(localtime=True); msg.set_content(a.get("cuerpo", ""))
    return msg


def t_borrador(a):
    c = cuenta(a.get("cuenta", "personal")); m = imap_abrir(c)
    try:
        carpeta = "[Gmail]/Drafts" if c["proveedor"] in ("gmail", "google") else "Drafts"
        typ, lst = m.list()
        for l in lst or []:
            s = l.decode(errors="replace")
            if "\\Drafts" in s:
                carpeta = s.split(' "/" ')[-1].strip().strip('"'); break
        m.append(f'"{carpeta}"', "\\Draft", imaplib.Time2Internaldate(time.time()), bytes(_nuevo(c, a)))
        return f"Borrador guardado en {c['nombre']} (carpeta {carpeta}). No se ha enviado nada."
    finally:
        m.logout()


def t_enviar(a):
    c = cuenta(a.get("cuenta", "personal")); usuario, clave = cred_leer(c["id"])
    if c.get("oauth") == "google":
        _, (host, port) = servidores(c); msg = _nuevo(c, a)
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
            s.ehlo(); s.docmd("AUTH", "XOAUTH2 " + base64.b64encode(_xoauth(c).encode()).decode()); s.send_message(msg)
        return f"Enviado desde {c['nombre']} ({c['direccion']}) a {a['para']}."
    if not usuario:
        raise PermissionError("Cuenta no conectada.")
    _, (host, port) = servidores(c); msg = _nuevo(c, a)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
            s.login(usuario, clave); s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ssl.create_default_context()); s.login(usuario, clave); s.send_message(msg)
    return f"Enviado desde {c['nombre']} ({c['direccion']}) a {a['para']}."


def t_mover(a):
    c = cuenta(a.get("cuenta", "personal")); m = imap_abrir(c)
    try:
        m.select("INBOX")
        destino = a.get("carpeta") or ("[Gmail]/Trash" if c["proveedor"] in ("gmail", "google") else "Trash")
        r = m.uid("COPY", str(a["id"]), f'"{destino}"')
        if r[0] != "OK":
            return f"No existe la carpeta {destino}."
        m.uid("STORE", str(a["id"]), "+FLAGS", "(\\Deleted)"); m.expunge()
        return f"Correo {a['id']} movido a {destino} en {c['nombre']} (no se ha borrado del todo)."
    finally:
        m.logout()


def detalle_correo(nombre, a):
    try:
        c = cuenta(a.get("cuenta", "personal")); de = f"{c['nombre']} <{c['direccion'] or 'sin conectar'}>"
    except Exception:
        de = a.get("cuenta", "?")
    if nombre == "correo_enviar":
        return f"DESDE: {de}\nPARA: {a.get('para')}\nASUNTO: {a.get('asunto', '')}\n\n{a.get('cuerpo', '')}"
    return f"CUENTA: {de}\nCORREO: {a.get('id')}\nA LA CARPETA: {a.get('carpeta') or 'Papelera'}"


# ---------- API para Ajustes → Conectores → Correo ----------
def api_cuentas(h):
    if h.command == "GET":
        return h.send(200, cuentas())
    d = chat.leer_cuerpo(h); cs = cuentas()
    c = next((x for x in cs if x["id"] == d.get("id")), None)
    if not c:
        return h.send(404, {"error": "No existe esa cuenta"})
    for k in ("nombre", "color"):
        if d.get(k):
            c[k] = d[k]
    chat.escribir(F_CUENTAS, [{k: v for k, v in x.items() if k not in ("conectada", "proveedor_nombre", "ayuda")} for x in cs])
    h.send(200, cuentas())


def api_conectar(h):
    d = chat.leer_cuerpo(h)  # {id, direccion, clave}  — la clave NUNCA se escribe en disco ni en el registro
    cs = [{k: v for k, v in x.items() if k not in ("conectada", "proveedor_nombre", "ayuda")} for x in cuentas()]
    c = next((x for x in cs if x["id"] == d.get("id")), None)
    direccion = (d.get("direccion") or "").strip()
    if not c or "@" not in direccion:
        return h.send(400, {"error": "Escribe la dirección de correo completa."})
    c["direccion"] = direccion; c["dominio"] = direccion.split("@")[1].lower()
    c["proveedor"] = proveedor_de(c["dominio"])
    chat.escribir(F_CUENTAS, cs)
    if c["proveedor"] in ("microsoft", "pendiente", "otro"):
        return h.send(200, {"ok": False, "mensaje": f"Proveedor detectado: {PROVEEDORES.get(c['proveedor'], {}).get('nombre', 'desconocido')}. " + (PROVEEDORES.get(c['proveedor']) or PROVEEDORES['otro'])["ayuda"]})
    clave = d.get("clave") or ""
    if not clave:
        return h.send(200, {"ok": False, "mensaje": "Dirección guardada. Ahora pega la contraseña y pulsa Conectar."})
    (host, port), _ = servidores(c)
    try:
        m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30); m.login(direccion, clave); m.logout()
    except Exception:
        return h.send(200, {"ok": False, "mensaje": "El servidor ha rechazado la contraseña. " + PROVEEDORES[c["proveedor"]]["ayuda"]})
    cred_guardar(c["id"], direccion, clave)
    h.send(200, {"ok": True, "mensaje": f"Conectada {c['nombre']} ({direccion})."})


def api_desconectar(h):
    cred_borrar(chat.leer_cuerpo(h).get("id", "")); h.send(200, cuentas())


def register(R):
    R[("GET", "/api/correo/cuentas")] = api_cuentas
    R[("POST", "/api/correo/cuentas")] = api_cuentas
    R[("POST", "/api/correo/conectar")] = api_conectar
    R[("POST", "/api/correo/desconectar")] = api_desconectar
