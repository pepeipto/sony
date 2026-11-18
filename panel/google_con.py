# Conector de Google para Sony: Drive, Docs, Sheets, Calendar, Gmail y Contactos.
# OAuth de «app de escritorio» con PKCE y redirección a 127.0.0.1. El client_id/secret y el token
# se guardan cifrados en el Administrador de credenciales de Windows (nunca en archivos ni registros).
import base64, hashlib, json, os, secrets, socket, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import chat
import correo  # reutiliza cred_guardar / cred_leer / cred_borrar

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents",
          "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/contacts.readonly", "https://mail.google.com/", "openid", "email"]
_tok = {}  # email -> {"access", "exp"}
F_CUENTAS_G = correo.CARP / "google-cuentas.json"  # solo la lista de correos; los tokens van cifrados en Windows
_actual = threading.local()


def cliente():
    cid, sec = correo.cred_leer("google-cliente")
    return (cid, sec) if cid else (None, None)


def cuentas_g():
    lista = chat.leer(F_CUENTAS_G, None)
    if lista is None:  # migración desde la versión de una sola cuenta
        lista = []
        email, rt = correo.cred_leer("google-token")
        if email and rt:
            correo.cred_guardar(f"google-token/{email}", email, rt); correo.cred_borrar("google-token"); lista = [email]
        chat.escribir(F_CUENTAS_G, lista)
    return [e for e in lista if correo.cred_leer(f"google-token/{e}")[0]]


def conectado():
    return bool(cuentas_g())


def cuenta_email():
    c = cuentas_g()
    return c[0] if c else None


def resolver(cuenta):
    """Acepta un correo o un alias de cuenta (personal, trabajo…) y devuelve el correo de Google."""
    lista = cuentas_g()
    if not lista:
        raise PermissionError("Google no está conectado. El usuario tiene que pulsar «Conectar Google» en Ajustes → Conectores.")
    if not cuenta:
        return lista[0]
    c = str(cuenta).strip().lower()
    for e in lista:
        if e.lower() == c:
            return e
    for x in correo.cuentas():
        if c in (x["id"].lower(), x["nombre"].lower()) and x.get("direccion") in lista:
            return x["direccion"]
    raise ValueError(f"No hay ninguna cuenta de Google conectada que sea «{cuenta}». Conectadas: {', '.join(lista)}")


def usar(a):
    _actual.email = resolver(a.get("cuenta")); return _actual.email


def access_token(email=None):
    email = email or getattr(_actual, "email", None) or resolver(None)
    t = _tok.get(email)
    if t and time.time() < t["exp"] - 60:
        return t["access"]
    cid, sec = cliente(); rt = correo.cred_leer(f"google-token/{email}")[1]
    if not (cid and rt):
        raise PermissionError(f"La cuenta de Google {email} no está conectada.")
    d = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "refresh_token": rt, "grant_type": "refresh_token"}).encode()
    r = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", d, timeout=20).read())
    _tok[email] = {"access": r["access_token"], "exp": time.time() + r.get("expires_in", 3600)}
    return r["access_token"]


def g(metodo, url, datos=None, crudo=False, ctype="application/json"):
    cuerpo = None if datos is None else (datos if isinstance(datos, bytes) else json.dumps(datos).encode())
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers={"Authorization": "Bearer " + access_token(), "Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=40) as r:
        b = r.read()
    return b if crudo else (json.loads(b) if b else {})


# ---------- conexión (la hace el usuario) ----------
def conectar(timeout=300):
    cid, sec = cliente()
    if not cid:
        raise PermissionError("Primero pega el ID y el secreto de cliente de Google.")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]; s.close()
    verif = secrets.token_urlsafe(64); estado = secrets.token_urlsafe(24)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verif.encode()).digest()).rstrip(b"=").decode()
    redir = f"http://127.0.0.1:{puerto}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redir, "response_type": "code", "scope": " ".join(SCOPES),
        "code_challenge": reto, "code_challenge_method": "S256", "state": estado, "access_type": "offline", "prompt": "select_account consent"})
    res = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == estado:
                res["code"] = q.get("code", [None])[0]; res["error"] = q.get("error", [None])[0]
            ok = bool(res.get("code"))
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(("<h2 style='font-family:sans-serif'>" + ("Listo: Google conectado a Sony. Ya puedes cerrar esta pestaña." if ok else "No se ha concedido el acceso.") + "</h2>").encode())

    srv = HTTPServer(("127.0.0.1", puerto), H); srv.timeout = 2
    __import__('webbrowser').open(url)
    fin = time.time() + timeout
    while "code" not in res and "error" not in res and time.time() < fin:
        srv.handle_request()
    srv.server_close()
    if not res.get("code"):
        raise PermissionError("No se completó el inicio de sesión de Google (" + str(res.get("error") or "tiempo agotado") + ").")
    d = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "code": res["code"], "code_verifier": verif,
                                "grant_type": "authorization_code", "redirect_uri": redir}).encode()
    try:
        r = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", d, timeout=20).read())
    except urllib.error.HTTPError as e:  # p. ej. invalid_client si el secreto del cliente no vale
        try:
            det = json.loads(e.read() or b"{}")
        except Exception:
            det = {}
        raise PermissionError(f"Google rechazó el cambio del código ({e.code}: {det.get('error', '')} {det.get('error_description', '')})".strip())
    if not r.get("refresh_token"):
        raise PermissionError("Google no ha devuelto permiso permanente; vuelve a intentarlo.")
    email = json.loads(urllib.request.urlopen(urllib.request.Request("https://openidconnect.googleapis.com/v1/userinfo",
                                                                     headers={"Authorization": "Bearer " + r["access_token"]}), timeout=20).read()).get("email", "")
    correo.cred_guardar(f"google-token/{email}", email, r["refresh_token"])
    _tok[email] = {"access": r["access_token"], "exp": time.time() + r.get("expires_in", 3600)}
    lista = cuentas_g()
    if email not in lista:
        chat.escribir(F_CUENTAS_G, lista + [email])
    return email


# ---------- herramientas ----------
def t_drive_buscar(a):  # 15/11: hasta 50 resultados, busca por nombre y contenido, y dice en qué carpeta está cada archivo
    usar(a)
    q = a.get("texto", "").replace("'", "\\'")
    filtro = f"(name contains '{q}' or fullText contains '{q}') and trashed = false" if q else "trashed = false"
    r = g("GET", "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(
        {"q": filtro, "pageSize": min(int(a.get("maximo") or 50), 100), "fields": "files(id,name,mimeType,modifiedTime,parents)",
         **({"orderBy": "modifiedTime desc"} if not q else {})}))
    archivos = r.get("files", [])
    carpetas = {}
    for pid in {f["parents"][0] for f in archivos if f.get("parents")}:
        try:
            carpetas[pid] = g("GET", f"https://www.googleapis.com/drive/v3/files/{pid}?fields=name")["name"]
        except Exception:
            carpetas[pid] = "?"
    filas = [f"[{f['id']}] {f['name']} · {f['mimeType'].split('.')[-1].split('/')[-1]} · carpeta «{carpetas.get((f.get('parents') or [''])[0], '')}» · {f['modifiedTime'][:10]}"
             for f in archivos]
    return (f"{len(filas)} archivos:\n" + "\n".join(filas)) if filas else "Nada encontrado."


def t_drive_leer(a):
    usar(a)
    fid = a["id"]
    meta = g("GET", f"https://www.googleapis.com/drive/v3/files/{fid}?fields=name,mimeType,size")
    mt = meta["mimeType"]
    exportar = {"application/vnd.google-apps.document": "text/plain", "application/vnd.google-apps.spreadsheet": "text/csv",
                "application/vnd.google-apps.presentation": "text/plain"}
    if mt in exportar:
        b = g("GET", f"https://www.googleapis.com/drive/v3/files/{fid}/export?mimeType={urllib.parse.quote(exportar[mt])}", crudo=True)
    elif mt.startswith("text/") or mt in ("application/json",):
        b = g("GET", f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media", crudo=True)
    elif mt == "application/pdf" or mt.startswith("application/vnd.openxmlformats"):  # 15/11: PDF y Word/Excel/PowerPoint
        import chat
        datos = g("GET", f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media", crudo=True)
        nombre = meta["name"] if "." in meta["name"] else meta["name"] + (".pdf" if mt == "application/pdf" else ".docx")
        tipo, texto = chat.extraer(nombre, datos)
        if not texto:
            return f"{meta['name']}: es un PDF escaneado o sin texto; no puedo leer su contenido."
        return f"{meta['name']}\n\n" + texto[:30000]
    else:
        return f"{meta['name']} es de tipo {mt}: no puedo leerlo como texto."
    return f"{meta['name']}\n\n" + b.decode("utf-8", "replace")[:15000]


def t_doc_crear(a):
    usar(a)
    d = g("POST", "https://docs.googleapis.com/v1/documents", {"title": a.get("titulo", "Documento de Sony")})
    if a.get("texto"):
        g("POST", f"https://docs.googleapis.com/v1/documents/{d['documentId']}:batchUpdate",
          {"requests": [{"insertText": {"location": {"index": 1}, "text": a["texto"]}}]})
    return f"Documento creado: {a.get('titulo')} → https://docs.google.com/document/d/{d['documentId']}/edit"


def t_sheets_leer(a):
    usar(a)
    r = g("GET", f"https://sheets.googleapis.com/v4/spreadsheets/{a['id']}/values/{urllib.parse.quote(a.get('rango') or 'A1:Z200')}")
    return "\n".join(" | ".join(str(c) for c in fila) for fila in r.get("values", [])) or "Vacía."


def t_calendario_ver(a):
    usar(a)
    dias = int(a.get("dias") or 7)
    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); hasta = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + dias * 86400))
    r = g("GET", "https://www.googleapis.com/calendar/v3/calendars/primary/events?" + urllib.parse.urlencode(
        {"timeMin": ahora, "timeMax": hasta, "singleEvents": "true", "orderBy": "startTime", "maxResults": 50}))
    def _dia(s):  # 15/11: con el día de la semana (el modelo se equivocaba contando)
        import datetime as _dt
        f = _dt.date.fromisoformat(s[:10]); n = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][f.weekday()]
        return f"{n} {f.day}/{f.month}" + (" " + s[11:16] if len(s) > 10 else "")
    return "\n".join(f"{_dia(e['start'].get('dateTime') or e['start'].get('date'))} · {e.get('summary', '(sin título)')}"
                     for e in r.get("items", [])) or f"Nada en los próximos {dias} días."


def t_calendario_crear(a):
    usar(a)
    ev = {"summary": a["titulo"], "start": {"dateTime": a["inicio"], "timeZone": "Europe/Madrid"},
          "end": {"dateTime": a["fin"], "timeZone": "Europe/Madrid"}, "description": a.get("descripcion", "")}
    r = g("POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events", ev)
    return f"Evento creado: {a['titulo']} ({a['inicio']}) → {r.get('htmlLink')}"


def t_contactos_buscar(a):
    usar(a)
    r = g("GET", "https://people.googleapis.com/v1/people:searchContacts?" + urllib.parse.urlencode(
        {"query": a["texto"], "readMask": "names,emailAddresses,phoneNumbers", "pageSize": 10}))
    out = []
    for x in r.get("results", []):
        p = x["person"]
        out.append(f"{(p.get('names') or [{}])[0].get('displayName', '?')} · {', '.join(e['value'] for e in p.get('emailAddresses', []))} · {', '.join(t['value'] for t in p.get('phoneNumbers', []))}")
    return "\n".join(out) or "Sin resultados."


HERRAMIENTAS = {
    "drive_buscar": (t_drive_buscar, False, "Buscar en Google Drive", {"cuenta": "string", "texto": "string", "maximo": "integer"}, "Busca archivos en el Google Drive del usuario (texto vacío = los más recientes)."),
    "drive_leer": (t_drive_leer, False, "Leer un archivo de Drive", {"cuenta": "string", "id": "string"}, "Lee el TEXTO de un archivo de Drive por su id: Google Docs, Sheets y Slides, PDF (también escaneados: los lee con OCR), Word, Excel, PowerPoint y texto. Úsalo también para los PDF (no hace falta descargarlos)."),
    "doc_crear": (t_doc_crear, True, "Crear un documento de Google Docs", {"cuenta": "string", "titulo": "string", "texto": "string"}, "Crea un Google Doc nuevo con ese texto."),
    "sheets_leer": (t_sheets_leer, False, "Leer una hoja de cálculo", {"cuenta": "string", "id": "string", "rango": "string"}, "Lee valores de una Google Sheet (rango tipo A1:D50)."),
    "calendario_ver": (t_calendario_ver, False, "Ver tu calendario", {"cuenta": "string", "dias": "integer"}, "Lista los eventos del calendario del usuario de los próximos días."),
    "calendario_crear": (t_calendario_crear, True, "Crear un evento en el calendario", {"cuenta": "string", "titulo": "string", "inicio": "string", "fin": "string", "descripcion": "string"},
                         "Crea un evento (inicio y fin en formato 2026-11-20T10:00:00, hora de Madrid)."),
    "contactos_buscar": (t_contactos_buscar, False, "Buscar en tus contactos", {"cuenta": "string", "texto": "string"}, "Busca personas en los contactos de Google del usuario."),
}


# ---------- API para Ajustes → Conectores ----------
def api_estado(h):
    cid, _ = cliente(); lista = cuentas_g()
    nombres = {x.get("direccion", "").lower(): x["nombre"] for x in correo.cuentas()}
    h.send(200, {"cliente": bool(cid), "conectado": bool(lista), "email": lista[0] if lista else None,
                 "cuentas": [{"email": e, "nombre": nombres.get(e.lower(), "")} for e in lista]})


def api_borrar_json(h):
    # Mueve a la papelera los JSON de credencial de Google que haya en Descargas para este cliente.
    from pathlib import Path
    import agente
    cid, _ = cliente(); movidos = []
    dl = Path.home() / "Downloads"
    for f in list(dl.glob("client_secret*.json")):
        try:
            if cid and cid in f.read_text(encoding="utf-8", errors="ignore"):
                agente.a_papelera(f); movidos.append(f.name)
        except Exception:
            pass
    h.send(200, {"movidos": movidos})


def api_cliente(h):
    d = chat.leer_cuerpo(h)
    d = d.get("installed") or d.get("web") or d  # admite el JSON tal cual lo descarga Google
    cid = (d.get("client_id") or "").strip(); sec = (d.get("client_secret") or "").strip()
    if not cid.endswith(".apps.googleusercontent.com") or not sec:
        return h.send(400, {"error": "El ID de cliente debe terminar en .apps.googleusercontent.com y el secreto no puede estar vacío."})
    correo.cred_guardar("google-cliente", cid, sec)
    h.send(200, {"ok": True})


def api_conectar(h):
    try:
        email = conectar()
    except Exception as e:
        try:  # solo el motivo (sin códigos ni llaves)
            with open(chat.LOGS / "google.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"{type(e).__name__}: {str(e)[:300]}\n")
        except Exception:
            pass
        return h.send(200, {"ok": False, "mensaje": str(e)})
    # Cada Gmail conectado pasa a usar este permiso (sin contraseña de aplicación).
    cs = [{k: v for k, v in x.items() if k not in ("conectada", "proveedor_nombre", "ayuda")} for x in correo.cuentas()]
    c = next((x for x in cs if x.get("direccion", "").lower() == email.lower()), None)
    if c is None and len(cuentas_g()) == 1:
        c = next((x for x in cs if x["id"] == "personal"), None)
    if c is None:
        c = {"id": "g-" + email.split("@")[0].replace(".", "-")[:20], "nombre": email.split("@")[0], "color": "#8a6fb0",
             "dominio": email.split("@")[1], "proveedor": "gmail"}
        cs.append(c)
    c["direccion"] = email; c["oauth"] = "google"
    chat.escribir(correo.F_CUENTAS, cs)
    h.send(200, {"ok": True, "mensaje": f"Cuenta de Google conectada: {email}"})


def api_desconectar(h):
    email = chat.leer_cuerpo(h).get("email") or ""
    if email:
        correo.cred_borrar(f"google-token/{email}"); _tok.pop(email, None)
        chat.escribir(F_CUENTAS_G, [e for e in cuentas_g() if e != email])
    h.send(200, {"ok": True})


def register(R):
    R[("GET", "/api/google/estado")] = api_estado
    R[("POST", "/api/google/cliente")] = api_cliente
    R[("POST", "/api/google/borrar_json")] = api_borrar_json
    R[("POST", "/api/google/conectar")] = api_conectar
    R[("POST", "/api/google/desconectar")] = api_desconectar
