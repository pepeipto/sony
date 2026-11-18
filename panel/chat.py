# Chat «IA Sony»: hilos, proyectos, adjuntos, ajustes y conexión con llama-server (Qwen 27B).
import base64, json, os, re, socket, subprocess, threading, time, uuid, zipfile, io, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).resolve().parent
CHATS = BASE / "chats"; PAPELERA = CHATS / "_papelera"; ADJ = BASE / "adjuntos"
for d in (CHATS, PAPELERA, ADJ):
    d.mkdir(parents=True, exist_ok=True)
F_PROY = CHATS / "_proyectos.json"; F_PROG = CHATS / "_programados.json"; F_AJ = BASE / "ajustes.json"
import compat
LOGS = compat.LOGS
LLAMA = compat.LLAMA
MODELOS = {
    "rapido": {"nombre": "Qwen 27B", "desc": "Rápido · ve imágenes",
               "gguf": compat.MODELOS / "Qwen3.8-27B-UD-Q5_K_M.gguf",
               "mmproj": compat.MODELOS / "mmproj-F16.gguf"},
}
PORT_LLAMA = 11434  # Mac Studio: el modelo lo sirve Ollama (compartido); Sony no lo arranca ni lo mata
OLLAMA_MODELO = "qwen-sony"
ARRANCAR_OLLAMA = compat.IA / "arrancar-ollama.sh"
NO_WINDOW = 0
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

AJUSTES_DEF = {
    "nombre": "El usuario", "tema": "sombra", "letra": "normal", "modelo": "rapido",
    "temperatura": 0.7, "max_tokens": 4096, "razonamiento": False, "contexto_qwen": 32768,
    "instrucciones": "", "memoria": [], "avisos_windows": False,
    "descargar_tras_min": 15, "voz": {"activada": False, "pausa_ms": 700},
}

_lock = threading.Lock()
_proc = {"p": None, "modelo": None, "ultimo_uso": 0.0, "estado": "apagado"}


def leer(f, defecto):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def escribir(f, data):
    f = Path(f); tmp = f.with_suffix(f.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def ajustes():
    a = dict(AJUSTES_DEF); a.update(leer(F_AJ, {})); return a


# ---------- llama-server ----------
def puerto_vivo():
    try:
        with socket.create_connection(("127.0.0.1", PORT_LLAMA), timeout=0.4):
            return True
    except OSError:
        return False


def modelo_ocupado():
    try:
        return _en_curso[0] > 0  # Ollama no expone /slots: se cuentan las peticiones de Sony que siguen abiertas
    except Exception:
        return False


CLAUDE = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}  # modelos por API que salen en el selector


def claude_id(k):
    """Identificador real del modelo en la API. Se puede cambiar en ajustes.json → "claude_ids": {"haiku": "...", "sonnet": "..."}
    si Anthropic retira un modelo, sin tocar el código."""
    return (ajustes().get("claude_ids") or {}).get(k) or CLAUDE[k]


def es_claude():
    return _proc.get("modelo") in CLAUDE


def abrir(payload, timeout=600, modelo=None):
    """Pide una respuesta al motor indicado (o al activo): llama-server local o la API de Claude (mismo formato OpenAI)."""
    m = modelo or _proc.get("modelo")
    if m in CLAUDE:
        import claude_api
        return claude_api.abrir(payload, timeout, claude_id(m))
    payload = _a_ollama(payload)
    req = urllib.request.Request(f"http://127.0.0.1:{PORT_LLAMA}/v1/chat/completions",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return _Contada(urllib.request.urlopen(req, timeout=timeout))


_en_curso = [0]
_en_curso_lock = threading.Lock()


class _Contada:
    """Envuelve la respuesta de Ollama para saber cuántas siguen abiertas (así las tareas de fondo esperan y no le quitan velocidad al usuario)."""
    def __init__(self, r):
        self._r = r; self._abierta = True
        with _en_curso_lock:
            _en_curso[0] += 1

    def _cerrar(self):
        if self._abierta:
            self._abierta = False
            with _en_curso_lock:
                _en_curso[0] -= 1

    def read(self, *a):
        try:
            d = self._r.read(*a)
        except Exception:
            self._cerrar(); raise
        if not a:
            self._cerrar()
        return d

    def __iter__(self):
        try:
            yield from self._r
        finally:
            self._cerrar()

    def close(self):
        self._cerrar(); self._r.close()

    def __enter__(self):
        return self

    def __exit__(self, *e):
        self.close()

    def __getattr__(self, k):
        return getattr(self._r, k)

    def __del__(self):
        self._cerrar()


def _a_ollama(payload):
    """Adapta una petición pensada para llama-server a Ollama: nombre del modelo y razonamiento (enable_thinking → reasoning_effort)."""
    p = dict(payload); p["model"] = OLLAMA_MODELO
    kw = p.pop("chat_template_kwargs", None) or {}
    p["reasoning_effort"] = "medium" if kw.get("enable_thinking") else "none"
    return p


def lista_modelos():
    out = [{"id": k, "nombre": v["nombre"], "desc": v["desc"], "disponible": (v.get("completo") or v["gguf"]).exists(), "reserva": bool(v.get("reserva"))} for k, v in MODELOS.items()]
    out.append({"id": "auto", "nombre": "Automático", "desc": "Haiku por defecto; Sonnet solo si Haiku falla dos veces. El Qwen local es la reserva (sin clave, sin tope o sin internet)",
                "disponible": True, "reserva": False})
    try:
        import claude_api
        hay = claude_api.hay_clave()
        for k, mid in CLAUDE.items():
            m = claude_api._precio(claude_id(k)); m = {**m, 'nombre': m['nombre'] if claude_id(k) == mid else claude_id(k)}
            out.append({"id": k, "nombre": m["nombre"].replace("Claude ", ""), "desc": f"API de Claude · {m['in']:g}/{m['out']:g} $ por millón de tokens · ve imágenes",
                        "disponible": hay, "reserva": False})
    except Exception:
        pass
    return out


def llama_listo():
    if es_claude():
        return True
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT_LLAMA}/api/tags", timeout=1) as r:
            return any(m.get("name", "").split(":")[0] == OLLAMA_MODELO for m in json.loads(r.read()).get("models", []))
    except Exception:
        return False


def _parar_todo_8080():
    """En el Mac el modelo vive en Ollama, compartido: aquí solo se olvida el estado de Sony. Nunca se mata ningún proceso."""
    _proc.update(p=None, modelo=None, estado="apagado")


NECESITA_GB = 16.0  # medido: con ~17 GB libres el modelo (mmap, 19,9 GB) + contexto 16k carga sin swap


def esperar_grafica_libre(max_s=60, seguidos_s=5):
    """Regla 6 del usuario: no se carga el modelo si la memoria va justa. Se espera a que macOS libere la del modelo anterior."""
    t0 = time.time(); desde = None; disp = 0.0
    while time.time() - t0 < max_s:
        disp = compat.memoria()[1]
        if disp >= NECESITA_GB:
            desde = desde or time.time()
            if time.time() - desde >= seguidos_s:
                _log_espera(f"memoria disponible {disp:.1f} GB tras {round(time.time() - t0)} s")
                return True
        else:
            desde = None
        time.sleep(1)
    _log_espera(f"memoria disponible insuficiente en {max_s} s ({disp:.1f} GB < {NECESITA_GB} GB): no se carga el modelo")
    return False


def _log_espera(texto):
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "cambio-modelo.log", "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + texto + "\n")


PAUSA_TXT = "La gráfica está en pausa hasta que revisen el cable (Strimer): ahora no se carga ningún modelo."


MODO_CPU_TXT = "Modo CPU: más lento mientras revisan la gráfica."
SIN_LIMITE_TXT = "El modelo local no está disponible ahora mismo."


def modo_cpu():
    a = ajustes(); return bool(a.get("pausa_gpu") and a.get("modo_cpu"))


def cargar(clave="rapido"):
    _proc["aviso"] = None
    if clave in CLAUDE:  # motor por API: no carga nada; se libera el modelo local para devolver la memoria
        import claude_api
        if not claude_api.hay_clave():
            _proc["estado"] = "sin_clave"; return False
        with _lock:
            p = _proc["p"]
            if p and p.poll() is None:
                p.terminate()
                try: p.wait(10)
                except Exception: p.kill()
            _parar_todo_8080()
            _proc.update(p=None, modelo=clave, estado="listo", ultimo_uso=time.time())
        return True
    if es_claude():
        _proc.update(modelo=None, estado="apagado")
    clave = "rapido"  # en este Mac solo hay un modelo local (qwen-sony en Ollama)
    if llama_listo():
        _proc.update(p=None, modelo=clave, ultimo_uso=time.time(), estado="listo"); return True
    with _lock:  # solo para no lanzar el script dos veces a la vez
        if not puerto_vivo() and ARRANCAR_OLLAMA.exists():  # Ollama apagado: se arranca con el script de siempre (solo 127.0.0.1)
            subprocess.run(["/bin/zsh", str(ARRANCAR_OLLAMA)], timeout=20, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _proc.update(p=None, modelo=clave, ultimo_uso=time.time(), estado="cargando")
    for _ in range(40):
        if llama_listo():
            _proc["estado"] = "listo"; return True
        time.sleep(0.5)
    _proc["estado"] = "falta_modelo"; return False


def descargar():
    """El modelo de Ollama es compartido y se queda cargado: Sony solo marca su estado como apagado."""
    _proc.update(p=None, modelo=None, estado="apagado")


def estado():
    if es_claude():
        return {"estado": "listo", "modelo": _proc["modelo"], "aviso": None, "modelos": lista_modelos()}
    p = _proc["p"]
    if p and p.poll() is not None:
        _proc.update(p=None, estado="error")
    if _proc["estado"] in ("cargando", "listo") or puerto_vivo():
        _proc["estado"] = "listo" if llama_listo() else ("cargando" if puerto_vivo() else "apagado")
    return {"estado": "apagado" if _proc["estado"] == "sin_clave" else _proc["estado"], "modelo": _proc["modelo"],
            "aviso": _proc.get("aviso") or (MODO_CPU_TXT if modo_cpu() else (PAUSA_TXT if ajustes().get("pausa_gpu") else None)),
            "modelos": lista_modelos()}


def vigilante():
    # Descarga el modelo tras X minutos sin uso (para liberar la VRAM para juegos).
    while True:
        time.sleep(30)
        mins = ajustes().get("descargar_tras_min", 20)
        if mins and _proc["p"] and time.time() - _proc["ultimo_uso"] > mins * 60:
            descargar()


# ---------- adjuntos ----------
TEXTO = {".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".html", ".css", ".xml", ".yml", ".yaml", ".log", ".sql", ".ini", ".bat", ".ps1", ".java", ".c", ".cpp", ".cs", ".go", ".rs"}
IMAGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def extraer(nombre, datos):
    ext = Path(nombre).suffix.lower()
    if ext in TEXTO:
        return "texto", datos.decode("utf-8", "replace")[:200000]
    if ext in IMAGEN:  # 15/11: además se saca su texto con OCR (en CPU) para los modelos que no ven imágenes
        try:
            import ocr
            t = ocr.imagen(datos)
            return "imagen", (f"(Texto de la imagen, leído con OCR:)\n{t}" if len(t.split()) >= 3 else None)
        except Exception:
            return "imagen", None
    if ext in (".docx", ".pptx", ".xlsx", ".odt"):
        try:
            z = zipfile.ZipFile(io.BytesIO(datos)); partes = []
            for n in z.namelist():
                if re.match(r"(word/document|ppt/slides/slide\d+|xl/sharedStrings|content)\.xml$", n):
                    xml = z.read(n).decode("utf-8", "replace")
                    xml = re.sub(r"</(w:p|a:p|text:p|si)>", "\n", xml)
                    partes.append(re.sub(r"<[^>]+>", "", xml))
            return "documento", "\n".join(partes)[:200000]
        except Exception:
            return "documento", None
    if ext == ".pdf":  # 15/11: texto del PDF con pypdf (local, sin internet)
        try:
            import pypdf
            r = pypdf.PdfReader(io.BytesIO(datos))
            texto = "\n\n".join((pg.extract_text() or "") for pg in r.pages[:200])
            if texto.strip():
                return "documento", texto[:200000]
        except Exception:
            pass
        try:  # 15/11: PDF escaneado (solo imagen) → OCR en CPU
            import ocr
            texto, leidas, total = ocr.pdf(datos)
            if texto.strip():
                aviso = f"(PDF escaneado, leído con OCR: {leidas} de {total} páginas)\n\n"
                return "documento", (aviso + texto)[:200000]
        except Exception:
            pass
        return "pdf", None
    if ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
        return "audio", None
    if ext in (".mp4", ".mkv", ".mov", ".webm", ".avi"):
        return "video", None
    return "archivo", None


def subir(h):
    nombre = Path(h.headers.get("X-Nombre", "archivo")).name[:120]
    try: nombre = bytes(nombre, "latin-1").decode("utf-8")
    except Exception: pass
    n = int(h.headers.get("Content-Length", 0))
    if n > 500 * 1024 * 1024:
        return h.send(413, {"error": "Máximo 500 MB"})
    datos = h.rfile.read(n)
    aid = uuid.uuid4().hex[:16]
    carpeta = ADJ / aid; carpeta.mkdir()
    (carpeta / nombre).write_bytes(datos)
    tipo, texto = extraer(nombre, datos)
    meta = {"id": aid, "nombre": nombre, "tipo": tipo, "bytes": n, "texto": texto is not None}
    if texto is not None:
        (carpeta / "_texto.txt").write_text(texto, encoding="utf-8")
    escribir(carpeta / "_meta.json", meta)
    h.send(200, meta)


def adjunto_para_modelo(aid):
    if not ID_RE.match(aid):
        return None
    carpeta = ADJ / aid; meta = leer(carpeta / "_meta.json", None)
    if not meta:
        return None
    if meta["tipo"] == "imagen":
        datos = (carpeta / meta["nombre"]).read_bytes()
        ext = Path(meta["nombre"]).suffix.lower().strip(".").replace("jpg", "jpeg")
        return {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64," + base64.b64encode(datos).decode()}}
    if (carpeta / "_texto.txt").exists():
        t = (carpeta / "_texto.txt").read_text(encoding="utf-8")
        return {"type": "text", "text": f"[Archivo adjunto: {meta['nombre']}]\n{t}"}
    aviso = {"pdf": "PDF escaneado o sin texto (no se puede leer su texto)", "audio": "audio (la transcripción llegará con Whisper)",
             "video": "vídeo (la transcripción llegará con Whisper)"}.get(meta["tipo"], "archivo sin texto legible")
    return {"type": "text", "text": f"[Adjunto: {meta['nombre']} — {aviso}]"}


def biblioteca(h):
    out = []
    for m in ADJ.glob("*/_meta.json"):
        d = leer(m, None)
        if d:
            d["fecha"] = m.stat().st_mtime; out.append(d)
    out.sort(key=lambda x: -x["fecha"])
    h.send(200, out[:300])


def servir_adjunto(h):
    partes = urlparse(h.path).path.split("/")
    aid = partes[3] if len(partes) > 3 else ""
    if not ID_RE.match(aid):
        return h.send(404, {"error": "no existe"})
    meta = leer(ADJ / aid / "_meta.json", None)
    if not meta:
        return h.send(404, {"error": "no existe"})
    f = ADJ / aid / meta["nombre"]
    tipos = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    h.send(200, f.read_bytes(), tipos.get(f.suffix.lower(), "application/octet-stream"),
           {"Content-Disposition": "inline" if f.suffix.lower() in tipos else f'attachment; filename="{aid}{f.suffix}"',
            "Cache-Control": "private, max-age=31536000, immutable"})  # un adjunto nunca cambia: así no se descarga en cada repintado


# ---------- hilos y proyectos ----------
def leer_cuerpo(h):
    n = int(h.headers.get("Content-Length", 0))
    return json.loads(h.rfile.read(n) or b"{}")


def lista_hilos(h):
    out = []
    for f in CHATS.glob("*.json"):
        if f.name.startswith("_"):
            continue
        d = leer(f, None)
        if d and (d.get("perfil") == "invitada") == (getattr(h, "rol", None) == "invitada"):
            out.append({k: d.get(k) for k in ("id", "titulo", "proyecto", "fijado", "actualizado", "creado")})
    out.sort(key=lambda x: -(x.get("actualizado") or 0))
    h.send(200, out)


def hilo(h):
    hid = urlparse(h.path).path.rsplit("/", 1)[-1]
    if not ID_RE.match(hid):
        return h.send(400, {"error": "id no válido"})
    f = CHATS / f"{hid}.json"
    if getattr(h, "rol", None) == "invitada":  # la invitada solo ve y toca sus propios chats
        actual = leer(f, None)
        if actual is not None and actual.get("perfil") != "invitada":
            return h.send(404, {"error": "no existe"})
    if h.command == "GET":
        d = leer(f, None)
        return h.send(200, d) if d else h.send(404, {"error": "no existe"})
    if h.command == "POST":
        d = leer_cuerpo(h); d["id"] = hid; d["actualizado"] = time.time()
        if getattr(h, "rol", None) == "invitada":
            d["perfil"] = "invitada"; d["proyecto"] = None
        d.setdefault("creado", time.time()); escribir(f, d); return h.send(200, {"ok": True})
    if h.command == "DELETE":
        if f.exists():
            f.replace(PAPELERA / f.name)
        return h.send(200, {"ok": True})


def buscar(h):
    q = (parse_qs(urlparse(h.path).query).get("q", [""])[0]).lower().strip()
    res = []
    if q:
        for f in CHATS.glob("*.json"):
            if f.name.startswith("_"):
                continue
            d = leer(f, {})
            texto = " ".join(m.get("texto", "") for m in d.get("mensajes", []))
            pos = texto.lower().find(q)
            if q in (d.get("titulo") or "").lower() or pos >= 0:
                frag = texto[max(0, pos - 40): pos + 80] if pos >= 0 else ""
                res.append({"id": d["id"], "titulo": d.get("titulo"), "fragmento": frag, "actualizado": d.get("actualizado")})
    res.sort(key=lambda x: -(x.get("actualizado") or 0))
    h.send(200, res[:40])


def proyectos(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(200, [])
    if h.command == "GET":
        return h.send(200, leer(F_PROY, []))
    escribir(F_PROY, leer_cuerpo(h)); h.send(200, {"ok": True})


def programados(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(200, [])
    if h.command == "GET":
        return h.send(200, leer(F_PROG, []))
    escribir(F_PROG, leer_cuerpo(h)); h.send(200, {"ok": True})


def ajustes_api(h):
    if h.command == "GET":
        a = ajustes()
        if getattr(h, "rol", None) == "invitada":
            a = {k: v for k, v in a.items() if k in ("tema", "letra", "voz")}; a["nombre"] = "invitada"; a["modelo"] = "rapido"
        return h.send(200, a)
    a = ajustes(); a.update(leer_cuerpo(h)); escribir(F_AJ, a); h.send(200, a)


def datos_api(h):
    total = sum(f.stat().st_size for f in CHATS.rglob("*") if f.is_file())
    adj = sum(f.stat().st_size for f in ADJ.rglob("*") if f.is_file())
    h.send(200, {"chats_mb": round(total / 1e6, 2), "adjuntos_mb": round(adj / 1e6, 2),
                 "hilos": len([f for f in CHATS.glob("*.json") if not f.name.startswith("_")])})


def exportar(h):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in CHATS.rglob("*.json"):
            z.write(f, f.relative_to(BASE))
    h.send(200, buf.getvalue(), "application/zip", {"Content-Disposition": 'attachment; filename="chats-ia-sony.zip"'})


def conectores(h):  # 15/11: ya no hay textos fijos; es el estado real comprobado en vivo (estado_conectores.py)
    import estado_conectores
    d = estado_conectores.leer()
    h.send(200, [{"id": x["id"], "nombre": x["nombre"], "estado": {"ok": "listo", "error": "error"}.get(x["estado"], "sin configurar"),
                  "detalle": x["detalle"]} for x in d["conectores"]])


# ---------- conversación ----------
HONESTIDAD = """Regla del usuario: «Si no tengo razón, no me la des».
- No le des la razón para complacerle. Si dice algo incorrecto o propone algo con un fallo, díselo claro y con respeto, explica por qué (con datos o fuentes) y propone la alternativa.
- Si de verdad tiene razón, díselo sin adornos.
- Nada de halagos vacíos («¡Excelente pregunta!», «¡Gran idea!»).
- Si no estás segura de algo, di que no lo sabes en vez de inventarlo."""


SISTEMA = """Te llamas Sony y eres la asistente personal del usuario; funcionas en local, en su PC. Si te preguntan cómo te llamas, di que eres Sony, su asistente. Responde en español salvo que te pidan otro idioma.
Usa Markdown. Cuando escribas una página o gráfico completo, ponlo en un bloque ```html o ```svg (se puede ver como artefacto).
Si te piden un plan de pasos, puedes mostrar una tarjeta de progreso con un bloque ```progreso que contenga JSON: {"titulo": "...", "pasos": [{"texto": "...", "estado": "hecho|en_curso|pendiente"}]}.
Si necesitas que el usuario elija entre opciones, usa un bloque ```decision con JSON: {"pregunta": "...", "opciones": ["...", "..."]}.
TUS CAPACIDADES REALES (no las niegues nunca):
- Oídos y voz: TIENES OÍDOS. El micrófono de la app y Whisper son tus oídos, y Piper (local, en el Mac) es tu voz. Si el usuario te pregunta si le escuchas, responde simplemente «Sí, te escucho» (sin matices ni «salvedades»). Nunca digas «no tengo oído», «no tengo manos» ni «solo recibo texto».
- Manos: cuando el usuario pide una acción, la app te pasa sola al modo Agente con herramientas: luces Govee, correo (Gmail y otras cuentas), Drive, Calendario, Contactos, GitHub, Telegram, archivos del PC, segundo cerebro, búsqueda web, SAI, redes sociales, tareas programadas y skills. Lo que envía, publica o borra pide antes una tarjeta de permiso al usuario.
- Si en este mensaje no tienes herramientas a mano, NO digas que no puedes ni inventes comandos, puertos o direcciones: di que lo haces en el modo Agente (botón «Agente» o pídelo con un verbo de acción, por ejemplo «enciende la tira») y no des código para que el usuario lo pegue.
""" + HONESTIDAD


SISTEMA_INVITADA = """Te llamas Sony y eres un asistente de IA que funciona en local en el PC del usuario. Ahora hablas con una persona invitada de su familia (no con el usuario).
Responde en español, con amabilidad. No tienes acceso a los datos, correos, archivos, notas ni cuentas del usuario y no debes inventarlos ni hablar de ellos.
Nunca pidas ni muestres contraseñas, claves ni datos de pago. Usa Markdown.
Sé sincera: no des la razón por complacer, corrige con respeto lo que no sea correcto, nada de halagos vacíos y, si no sabes algo, dilo.
La familia del usuario: su mujer Ana y sus hijos Erika y el usuario hijo. Desde este perfil te puede hablar cualquiera de ellos; si te dice su nombre, úsalo. Si es uno de los niños, háblale con cariño y con un lenguaje adecuado para su edad, sin contenido para adultos ni bromas pesadas; si pide algo que no te corresponde, dile que se lo pida a su padre."""


# Tono de la voz: solo con el usuario y en modo voz. Clientes, WhatsApp e invitada: siempre amable y profesional.
TONOS = {
    "cercano_f": "TONO (modo voz con el usuario, voz femenina): simpática, cálida, alegre y con chispa, algo coqueta pero con elegancia. "
                 "Frases cortas y naturales, como en una conversación.",
    "cercano_m": "TONO (modo voz con el usuario, voz masculina): de amigo de confianza, cercano, con bromas ligeras (no pesadas) y riéndote con él; "
                 "sin coqueteo. Frases cortas y naturales.",
    "profesional": "TONO: amable y profesional, claro y respetuoso, sin bromas ni coqueteo.",
}
REGLAS_TONO = ("Reglas del tono: las bromas nunca a costa de terceros ni en temas serios (salud, dinero, problemas). "
               "Si el usuario está serio o tiene prisa, ve al grano. En modo voz, respuestas cortas (2-4 frases) salvo que pida detalle.")


DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_texto():  # hora local del PC = España (Europe/Madrid); con día de la semana y «mañana» para que no se equivoque
    import datetime as _dt
    hoy = _dt.datetime.now(); m = hoy + _dt.timedelta(days=1)
    return (f"Hoy es {DIAS_ES[hoy.weekday()]} {hoy.day} de {MESES_ES[hoy.month - 1]} de {hoy.year}, son las {hoy:%H:%M} (hora de Madrid). "
            f"Mañana es {DIAS_ES[m.weekday()]} {m.day} de {MESES_ES[m.month - 1]}. Próximos días: "
            + ", ".join(f"{DIAS_ES[(hoy + _dt.timedelta(days=k)).weekday()]} {(hoy + _dt.timedelta(days=k)).day}" for k in range(1, 8)) + ".")


CANALES = {"voz": "Canal: MODO VOZ (tu respuesta se leerá en voz alta). En este turno NO tienes herramientas: nunca digas que has hecho, enviado, apuntado o mirado algo; si el usuario pide una acción, dile que te lo repita con «hazlo» y entonces la harás. MÁXIMO 3 frases cortas, SIN listas, sin negritas, sin emojis ni símbolos, números como se dicen. Si hay mucho, da lo esencial y ofrece el detalle en pantalla.",
           "movil": "Canal: MÓVIL (pantalla pequeña): aplica la sección 10 de tus instrucciones.",
           "telegram": "Canal: TELEGRAM (móvil): aplica la sección 10 de tus instrucciones."}


def construir_mensajes(cuerpo, invitada=False):
    if invitada:
        msgs = [{"role": "system", "content": SISTEMA_INVITADA + "\n" + fecha_texto() + ("\n" + CANALES[cuerpo["canal"]] if cuerpo.get("canal") in CANALES else "")}]
        for m in cuerpo.get("mensajes", [])[-30:]:  # recorte: los chats largos de la invitada no desbordan el contexto
            msgs.append({"role": "assistant" if m.get("rol") == "ia" else "user", "content": m.get("texto", "")})
        return msgs, {k: v for k, v in ajustes().items() if k in ("temperatura", "max_tokens")}
    a = ajustes(); proy = None
    if cuerpo.get("proyecto"):
        proy = next((p for p in leer(F_PROY, []) if p.get("id") == cuerpo["proyecto"]), None)
    # 15/11 (velocidad): el mensaje de sistema es ESTABLE (no cambia entre mensajes) para que llama.cpp reutilice su caché y no
    # reprocese ~20.000 tokens cada vez. Todo lo que cambia (hora, notas del cerebro, diario, fijados, estado) va en un bloque
    # «contexto de este mensaje» pegado al ÚLTIMO mensaje del usuario.
    sistema = SISTEMA + f"\nLa persona se llama {a.get('nombre') or 'el usuario'}. Vive en España (hora de Madrid)."
    if a.get("instrucciones"):
        sistema += "\n\nInstrucciones personales:\n" + a["instrucciones"]
    if a.get("memoria"):
        sistema += "\n\nCosas que debes recordar siempre:\n" + "\n".join("- " + m for m in a["memoria"])
    try:  # lecciones permanentes de Sony (~/segundo-cerebro/sony/lecciones.md), también en el chat normal
        import agente as _ag
        sistema += "\n\n" + _ag.lecciones()
    except Exception:
        pass
    variable = [fecha_texto()]
    try:  # segundo cerebro automático (mapa de temas + notas relevantes a este mensaje). Solo para el usuario.
        import cerebro_rag
        ultimo = next((m.get("texto", "") for m in reversed(cuerpo.get("mensajes", [])) if m.get("rol") == "user"), "")
        sistema += "\n\n" + cerebro_rag.mapa_estable()
        voz = cuerpo.get("canal") == "voz"  # Mac: en voz, menos contexto = empieza a hablar antes
        ctx, usadas, ms = cerebro_rag.recuperar(ultimo, notas=2, caracteres=300) if voz else cerebro_rag.recuperar(ultimo)
        if ctx:
            variable.append(ctx)
            a["_cerebro"] = usadas; a["_cerebro_ms"] = ms
    except Exception:
        pass
    if proy and proy.get("instrucciones"):
        sistema += f"\n\nInstrucciones del proyecto «{proy.get('nombre')}»:\n" + proy["instrucciones"]
    tono = cuerpo.get("tono")
    if (tono in ("cercano_f", "cercano_m") and (a.get("voz") or {}).get("tono_personal", True)) or tono == "profesional":
        sistema += "\n\n" + TONOS[tono] + "\n" + REGLAS_TONO
    if cuerpo.get("canal") in CANALES:
        variable.append(CANALES[cuerpo["canal"]])
    try:  # diario de los últimos 7 días
        import diario
        d7 = None if cuerpo.get("canal") == "voz" else diario.diario_7d(excluir=cuerpo.get("hilo"))
        if d7:
            variable.append(d7)
    except Exception:
        pass
    # Mensajes FIJADOS (📌) de este chat: siempre presentes y nunca se recortan.
    todos = cuerpo.get("mensajes", [])
    fijados = [m for m in todos if m.get("fijado")]
    if fijados:
        variable.append("MENSAJES FIJADOS DE ESTE CHAT (el usuario los ha marcado como importantes; tenlos siempre presentes):\n" +
                        "\n".join(f"- {'Sony' if m.get('rol') == 'ia' else 'el usuario'}: {m.get('texto', '')[:1500]}" for m in fijados))
    for extra in cuerpo.get("_variable_extra", []):
        variable.append(extra)
    # Recorte por presupuesto: si el chat es muy largo, se quedan los últimos mensajes que caben (los fijados ya van en el contexto).
    presupuesto = 16000 if modo_cpu() else 48000  # caracteres de historial (~ 4.500 / 14.000 tokens)
    elegidos, usados = [], 0
    for m in reversed(todos):
        largo = len(m.get("texto", "") or "") + 200 * len(m.get("adjuntos") or [])
        if elegidos and usados + largo > presupuesto:
            break
        elegidos.append(m); usados += largo
    elegidos.reverse()
    if len(elegidos) < len(todos):
        variable.append(f"(Este chat es largo: solo ves los últimos {len(elegidos)} de {len(todos)} mensajes, más los fijados. Si te falta algo, usa chat_leer o pide al usuario que lo fije.)")
    msgs = [{"role": "system", "content": sistema}]
    for m in elegidos:
        rol = "assistant" if m.get("rol") == "ia" else "user"
        if rol == "user" and m.get("adjuntos"):
            partes = [p for p in (adjunto_para_modelo(x.get("id", "")) for x in m["adjuntos"]) if p]
            partes.append({"type": "text", "text": m.get("texto", "")})
            msgs.append({"role": rol, "content": partes})
        else:
            msgs.append({"role": rol, "content": m.get("texto", "")})
    pegar_contexto(msgs, "\n\n".join(variable))
    return msgs, a


def pegar_contexto(msgs, texto):
    """Pega el bloque variable al ÚLTIMO mensaje del usuario (así el principio del prompt no cambia y la caché sirve)."""
    if not texto:
        return
    bloque = "[Contexto automático de este mensaje, no lo repitas: " + texto + "]\n\n"
    for m in reversed(msgs):
        if m["role"] == "user":
            if isinstance(m["content"], list):
                m["content"] = [{"type": "text", "text": bloque}] + m["content"]
            else:
                m["content"] = bloque + (m["content"] or "")
            return
    msgs.append({"role": "user", "content": bloque})


def completar(h):
    cuerpo = leer_cuerpo(h)
    invitada = getattr(h, "rol", None) == "invitada"
    clave = "rapido" if invitada or cuerpo.get("canal") == "voz" else (cuerpo.get("modelo") or "rapido")  # Mac: lo hablado nunca sale a internet
    # 15/11: si llega una imagen y el modelo elegido no ve (el Pesado), este mensaje lo contesta el Diario, que sí ve.
    # cargar() descarga el otro y espera a la gráfica libre: nunca dos modelos a la vez.
    ult = next((m for m in reversed(cuerpo.get("mensajes", [])) if m.get("rol") == "user"), {})
    cambio_vision = False
    if any((x.get("tipo") == "imagen") for x in (ult.get("adjuntos") or [])):
        cfg = MODELOS.get(clave) or {}
        if not (cfg.get("mmproj") and cfg["mmproj"].exists()) and clave != "rapido" and clave not in CLAUDE:
            cambio_vision = _proc.get("modelo") != "rapido"; clave = "rapido"
    if not cargar(clave):
        msg = ("Falta la clave de la API de Claude: pégala en Ajustes → Modelo." if _proc.get("estado") == "sin_clave" else "La memoria del Mac va justa para cargar el modelo (necesita unos 23 GB libres). Cierra apps pesadas y vuelve a intentarlo."
               if _proc.get("estado") == "memoria_justa" else "El modelo local (Ollama, qwen-sony) no responde. Vuelve a intentarlo en un minuto.")
        return h.send(503, {"error": msg})
    for _ in range(600):  # hasta 5 min cargando
        if llama_listo():
            break
        if not puerto_vivo():
            return h.send(500, {"error": "El modelo (Ollama) no está encendido. Mira ~/IA/logs/ollama.log"})
        time.sleep(0.5)
    _proc["estado"] = "listo"; _proc["ultimo_uso"] = time.time()
    msgs, a = construir_mensajes(cuerpo, invitada)
    m_cfg = MODELOS.get(_proc.get("modelo") or clave) or {}
    if not es_claude() and not (m_cfg.get("mmproj") and m_cfg["mmproj"].exists()):  # 15/11: el Pesado no ve imágenes: se avisa en vez de dar error
        for mm in msgs:
            if isinstance(mm.get("content"), list):
                mm["content"] = [p if p.get("type") != "image_url" else {"type": "text", "text": "[el usuario ha adjuntado una imagen, pero este modelo no ve imágenes: dile que cambie al modelo Diario (o al modo Agente) para que la mires.]"} for p in mm["content"]]
    payload = {"messages": msgs, "stream": True, "temperature": a.get("temperatura", 0.7),
               "max_tokens": a.get("max_tokens", 4096),
               "chat_template_kwargs": {"enable_thinking": bool(a.get("razonamiento"))}}
    # 15/11: si el modelo está ocupado con otra tarea, Sony lo dice en vez de quedarse callada.
    h.send_response(200)
    h.send_header("Content-Type", "text/event-stream; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    def _evento(texto):
        h.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": texto}}]}, ensure_ascii=False) + "\n\n").encode()); h.wfile.flush()
    if cambio_vision:
        try:
            _evento("_👁 El Pesado no ve imágenes: he pasado al Diario para ver la foto._\n\n")
        except Exception:
            return
    if a.get("_cerebro"):  # «🧠 usé: …» bajo la respuesta
        try:
            h.wfile.write(("data: " + json.dumps({"cerebro": a["_cerebro"]}, ensure_ascii=False) + "\n\n").encode()); h.wfile.flush()
        except Exception:
            return
    if modelo_ocupado():
        try:
            _evento("_⏳ Un momento, estoy terminando otra tarea…_\n\n")
        except Exception:
            return
    try:
        r = abrir(payload, 900)
    except Exception as e:
        try:
            _evento(f"⚠️ No he podido responder: {e}" if isinstance(e, PermissionError) else f"⚠️ No he podido responder: el modelo no contesta ({type(e).__name__}). Vuelve a enviarlo en un momento.")
        except Exception:
            pass
        return
    try:
        for linea in r:
            h.wfile.write(linea); h.wfile.flush()
            _proc["ultimo_uso"] = time.time()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        r.close()
        try:  # aviso al móvil si no estabas mirando (texto genérico, sin el contenido)
            import push
            push.avisar("invitada" if invitada else "usuario", "Sony te ha respondido", tag="respuesta", solo_si_no_mira=True)
        except Exception:
            pass


def titulo(h):
    # Título corto a partir del primer mensaje (sin gastar el modelo).
    t = re.sub(r"\s+", " ", leer_cuerpo(h).get("texto", "")).strip()
    h.send(200, {"titulo": (t[:48] + "…") if len(t) > 48 else (t or "Chat nuevo")})


# ---------- voz (puente con el servicio local 127.0.0.1:8097) ----------
VOZ_PY = compat.IA / "sony" / "venv" / "bin" / "python"; VOZ_SRV = compat.IA / "sony" / "voz" / "voz.py"  # Mac: Whisper + Piper locales


def voz_viva():
    try:
        with socket.create_connection(("127.0.0.1", 8097), timeout=0.4):
            return True
    except OSError:
        return False


_voz_lock = threading.Lock()


def voz_arrancar():
    with _voz_lock:
        _voz_arrancar()


def _voz_arrancar():
    if ajustes().get("pausa_gpu") and not modo_cpu():
        raise RuntimeError(PAUSA_TXT)  # Whisper también usa la gráfica
    if not voz_viva() and VOZ_PY.exists():
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1", "VOZ_CPU": "1"} if modo_cpu() else None  # Whisper en el procesador
        with open(LOGS / "voz.err.log", "ab") as err:  # errores de voz.py aparte (voz.log es de voz.py)
            subprocess.Popen([str(VOZ_PY), "-I", str(VOZ_SRV), "--precargar"], cwd=str(VOZ_SRV.parent),
                             start_new_session=True, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err)
        for _ in range(240):
            if voz_viva():
                break
            time.sleep(0.5)


def voz_peticion(ruta, datos=None, cabeceras=None, timeout=60):
    voz_arrancar()
    req = urllib.request.Request("http://127.0.0.1:8097" + ruta, data=datos, headers=cabeceras or {},
                                 method="POST" if datos is not None else "GET")
    return urllib.request.urlopen(req, timeout=timeout)


def voz_proxy(h):
    ruta = urlparse(h.path).path[len("/api/voz"):]
    try:
        if h.command == "GET":
            with voz_peticion(ruta, timeout=30) as r:
                return h.send(200, r.read(), "application/json; charset=utf-8")
        try:
            n = int(h.headers.get("Content-Length", 0) or 0)
        except ValueError:
            n = -1
        if n < 0 or n > 4_000_000:  # máx. ~60 s de audio
            return h.send(413, {"error": "audio demasiado largo"})
        datos = h.rfile.read(n)
        cab = {"Content-Type": h.headers.get("Content-Type", "application/octet-stream")}
        for k in ("X-Formato", "X-Sesion"):
            if h.headers.get(k):
                cab[k] = h.headers[k]
        if ruta == "/hablar":
            d = json.loads(datos or b"{}")
            if not isinstance(d, dict):
                return h.send(400, {"error": "petición no válida"})
            d.setdefault("voz", (ajustes().get("voz") or {}).get("nombre") or "Davefx (España)")
            d["velocidad"] = (ajustes().get("voz") or {}).get("velocidad", 5)
            if getattr(h, "rol", None) == "invitada" or d.get("tono") not in ("cercano_f", "cercano_m"):
                d["tono"] = "profesional" if getattr(h, "rol", None) == "invitada" or d.get("tono") == "profesional" else None
            datos = json.dumps(d).encode()
        r = voz_peticion(ruta, datos, cab, timeout=300)
    except urllib.error.HTTPError as e:
        return h.send(e.code, e.read(), "application/json; charset=utf-8")
    except Exception as e:
        return h.send(502, {"error": f"Servicio de voz no disponible: {e}"})
    h.send_response(200)
    h.send_header("Content-Type", r.headers.get("Content-Type", "application/octet-stream"))
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    try:
        while True:
            t = r.read(4096)
            if not t:
                break
            h.wfile.write(t); h.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        r.close()


def liberar_api(h):
    """Botón ⏏: descarga el Qwen local y el buscador del cerebro para devolver la memoria al Mac."""
    try:
        import buscador
        buscador.parar_todo()
    except Exception:
        pass
    habia = bool(_proc["p"] and _proc["p"].poll() is None) or puerto_vivo()
    descargar(); _parar_todo_8080()
    h.send(200, {"ok": True, "texto": "Memoria liberada: he descargado el Qwen local." if habia else "No había ningún modelo local cargado."})


_VENTANA = {"t": 0.0}  # último latido de la ventana de Sony (lo usa el icono para no abrir dos ventanas)


def register(R):
    R[("POST", "/api/liberar")] = liberar_api
    R[("GET", "/api/sesion")] = lambda h: h.send(200, {"rol": "local"})
    R[("GET", "/api/ventana/latido")] = lambda h: (_VENTANA.__setitem__("t", time.time()), h.send(200, {"ok": True}))  # la ventana dice «sigo abierta»
    R[("POST", "/api/ventana/cerrada")] = lambda h: (_VENTANA.__setitem__("t", 0.0), h.send(200, {"ok": True}))  # al cerrar la ventana
    R[("GET", "/api/ventana/abierta")] = lambda h: h.send(200, {"abierta": time.time() - _VENTANA["t"] < 90})
    R[("POST", "/api/push/visible")] = lambda h: h.send(200, {"ok": True})
    R[("GET", "/api/voz/*")] = voz_proxy
    R[("POST", "/api/voz/*")] = voz_proxy
    pagina = lambda h: h.static("chat.html")
    R[("GET", "/chat")] = pagina
    R[("GET", "/api/chat/estado")] = lambda h: h.send(200, estado())
    R[("POST", "/api/chat/cargar")] = lambda h: h.send(200, {"ok": cargar("rapido" if getattr(h, "rol", None) == "invitada" else leer_cuerpo(h).get("modelo", "rapido")), **estado()})
    R[("POST", "/api/chat/descargar")] = lambda h: (descargar(), h.send(200, estado()))
    R[("POST", "/api/chat/completar")] = completar
    R[("POST", "/api/chat/titulo")] = titulo
    R[("GET", "/api/hilos")] = lista_hilos
    for m in ("GET", "POST", "DELETE"):
        R[(m, "/api/hilos/*")] = hilo
    R[("GET", "/api/buscar")] = buscar
    R[("GET", "/api/proyectos")] = proyectos; R[("POST", "/api/proyectos")] = proyectos
    R[("GET", "/api/programados")] = programados; R[("POST", "/api/programados")] = programados
    R[("GET", "/api/ajustes")] = ajustes_api; R[("POST", "/api/ajustes")] = ajustes_api
    R[("GET", "/api/datos")] = datos_api; R[("GET", "/api/exportar")] = exportar
    R[("GET", "/api/conectores")] = conectores
    R[("POST", "/api/adjuntos")] = subir
    R[("GET", "/api/biblioteca")] = biblioteca
    R[("GET", "/api/adjuntos/*")] = servir_adjunto
    threading.Thread(target=vigilante, daemon=True).start()
