# «Corrector Claude»: Claude Opus 5.5 (API de Anthropic) corrige lo que ha construido el Pesado en la carpeta de un proyecto.
# - Corrige, no repasa: primero seguridad (secretos, inyecciones, permisos, XSS, dependencias peligrosas), luego lo que rompe. Nada de estilo.
# - Cada corrección es un commit aparte («Corrección Claude: …») + nota en DIARIO.md: se puede deshacer con git revert.
# - Solo dentro de la carpeta del proyecto. Nunca se envían .env, claves ni archivos de secretos (y lo que parezca una clave se tapa).
# - Tope de gasto diario (3 € por defecto) y registro en ~/IA\logs\claude-api.jsonl. La clave vive en el Administrador de credenciales.
# - No usa la gráfica.
import json, re, subprocess, threading, time
from pathlib import Path

import chat
import correo

MODELO = "claude-opus-5-5"
PRECIO_USD = {"in": 4.0, "out": 20.0, "cache_read": 0.4, "cache_write": 5.0}  # por millón de tokens
USD_A_EUR = 0.92
LOG = __import__("compat").LOGS / "claude-api.jsonl"
F_CONF = Path(__file__).resolve().parent / "corrector.json"
NO_WINDOW = 0x08000000
MAX_ARCHIVO = 120_000      # bytes por archivo que se envía
MAX_TOTAL = 400_000        # bytes en total por corrección
_lock = threading.Lock()

SECRETO_NOMBRE = re.compile(r"(\.env(\.|$)|password|contrase|credential|secret|\.kdbx$|\.pem$|\.key$|id_rsa|wallet|cookies|\.p12$|\.pfx$)", re.I)
PARECE_CLAVE = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[abp]-[A-Za-z0-9-]{10,}|"
                          r"AIza[0-9A-Za-z_\-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|"
                          r"(?i:(api[_-]?key|secret|token|password|passwd|contrase[nñ]a)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]))")
TEXTO = {".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".py", ".php", ".sql", ".md", ".txt", ".yml", ".yaml",
         ".toml", ".ini", ".cfg", ".sh", ".ps1", ".bat", ".java", ".cs", ".go", ".rb", ".vue", ".svelte", ".xml", ".svg", ".gitignore"}

SISTEMA = """Eres el «Corrector» del equipo del usuario. Otro modelo (Qwen, el «Pesado») ha diseñado o construido el código que te paso.
Tu trabajo es CORREGIR, no repasar ni opinar:
1. Primero, errores de SEGURIDAD: secretos en el código, inyección (SQL, comandos, plantillas), XSS, CSRF, permisos o autenticación mal hechos, rutas que escapan de la carpeta, dependencias peligrosas o inexistentes, datos personales expuestos.
2. Después, errores que ROMPEN: código que no funciona, excepciones seguras, imports o rutas mal escritas, lógica claramente equivocada.
3. Nada más. No cambies estilo, nombres ni formato. No reescribas lo que funciona. No añadas funciones nuevas.
Si no hay nada que corregir, devuelve la lista de cambios vacía.
Para cada archivo que cambies, devuelve su CONTENIDO COMPLETO corregido (no un parche) y un motivo corto en español.
Solo puedes tocar los archivos que te paso. No pidas instalar nada.
Los valores tapados como [CLAVE OCULTA] son secretos reales: no los inventes; si un secreto está escrito en el código, muévelo a una variable de entorno.
Escribe el resumen y los motivos en español sencillo, para que el usuario pueda explicarlo en clase."""

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["resumen", "cambios"],
           "properties": {
               "resumen": {"type": "string"},
               "cambios": {"type": "array", "items": {
                   "type": "object", "additionalProperties": False, "required": ["ruta", "tipo", "motivo", "contenido"],
                   "properties": {"ruta": {"type": "string"}, "tipo": {"type": "string", "enum": ["seguridad", "error", "otro"]},
                                  "motivo": {"type": "string"}, "contenido": {"type": "string"}}}}}}


def conf():
    c = chat.leer(F_CONF, {})
    c.setdefault("tope_eur_dia", 3.0); c.setdefault("auto_tras_pesado", True)
    c.setdefault("activo", False)  # 15/11: El usuario sigue con DeepSeek; el corrector queda APAGADO (sin botones ni llamadas)
    return c


def clave():
    return correo.cred_leer("anthropic-key")[1]


def gastado_hoy_eur():
    if not LOG.exists():
        return 0.0
    hoy = time.strftime("%Y-%m-%d")
    return round(sum(json.loads(l).get("eur", 0) for l in LOG.read_text(encoding="utf-8").splitlines()
                     if l.strip() and l.startswith('{"fecha": "' + hoy)), 4)


def _registrar(**d):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), **d}, ensure_ascii=False) + "\n")


def _git(carpeta, *a):
    r = subprocess.run(["git", *a], cwd=carpeta, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=60, creationflags=NO_WINDOW)
    return r.returncode, r.stdout


def _tapar(texto, guardados=None):
    """Tapa lo que parece una clave con [CLAVE OCULTA n]; el original se queda solo en el PC (guardados)."""
    def rep(m):
        if guardados is None:
            return "[CLAVE OCULTA]"
        guardados.append(m.group(0)); return f"[CLAVE OCULTA {len(guardados)}]"
    return PARECE_CLAVE.sub(rep, texto)


def _destapar(texto, guardados):
    return re.sub(r"\[CLAVE OCULTA (\d+)\]", lambda m: guardados[int(m.group(1)) - 1] if 0 < int(m.group(1)) <= len(guardados) else m.group(0), texto)


def preparar(carpeta, base=None):
    """Diff y archivos tocados desde `base` (o desde la última corrección de Claude / el primer commit)."""
    carpeta = Path(carpeta).resolve()
    if not (carpeta / ".git").exists():
        raise RuntimeError("La carpeta del proyecto no es un repositorio git.")
    if not base:
        _, log = _git(carpeta, "log", "--format=%H %s", "-n", "200")
        lineas = [l.split(" ", 1) for l in log.splitlines() if l.strip()]
        base = next((h for h, s in lineas if s.startswith("Corrección Claude")), None) or (lineas[-1][0] if lineas else None)
    _, nombres = _git(carpeta, "diff", "--name-only", base) if base else (0, "")
    _, nuevos = _git(carpeta, "ls-files", "--others", "--exclude-standard")
    rutas = sorted({r.strip() for r in (nombres + "\n" + nuevos).splitlines() if r.strip()})
    archivos, omitidos, total, guardados = {}, [], 0, []
    for r in rutas:
        p = (carpeta / r).resolve()
        if carpeta not in p.parents or not p.is_file() or ".git" in p.relative_to(carpeta).parts:
            continue
        if SECRETO_NOMBRE.search(p.name):
            omitidos.append(f"{r} (puede tener secretos: no sale del PC)"); continue
        if p.suffix.lower() not in TEXTO and p.name not in (".gitignore", "Dockerfile"):
            omitidos.append(f"{r} (no es texto)"); continue
        if p.stat().st_size > MAX_ARCHIVO or total + p.stat().st_size > MAX_TOTAL:
            omitidos.append(f"{r} (demasiado grande)"); continue
        if r in ("DIARIO.md",):
            continue
        archivos[r] = _tapar(p.read_text(encoding="utf-8", errors="replace"), guardados); total += p.stat().st_size
    diff = ""
    if base:
        _, diff = _git(carpeta, "diff", "--no-color", "-U3", base, "--", *archivos.keys()) if archivos else (0, "")
    return {"carpeta": carpeta, "base": base, "archivos": archivos, "omitidos": omitidos, "diff": _tapar(diff)[:150_000], "guardados": guardados}


def estimar_eur(prep):
    tokens_in = (len(SISTEMA) + len(prep["diff"]) + sum(len(t) for t in prep["archivos"].values())) / 3.2
    tokens_out = sum(len(t) for t in prep["archivos"].values()) / 3.2 * 0.6 + 4000  # peor caso: reescribe la mitad + pensamiento
    return round((tokens_in * PRECIO_USD["in"] + tokens_out * PRECIO_USD["out"]) / 1e6 * USD_A_EUR, 3)


def _coste_eur(usage):
    u = usage
    usd = ((getattr(u, "input_tokens", 0) or 0) * PRECIO_USD["in"] + (getattr(u, "output_tokens", 0) or 0) * PRECIO_USD["out"]
           + (getattr(u, "cache_read_input_tokens", 0) or 0) * PRECIO_USD["cache_read"]
           + (getattr(u, "cache_creation_input_tokens", 0) or 0) * PRECIO_USD["cache_write"]) / 1e6
    return round(usd * USD_A_EUR, 4)


def llamar_claude(prep, motivo="manual"):
    import anthropic
    k = clave()
    if not k:
        raise RuntimeError("Falta la clave de Anthropic: pégala en Ajustes → Conectores → Claude (API).")
    contenido = ("Archivos del proyecto que ha tocado el Pesado (contenido actual):\n\n"
                 + "\n\n".join(f'<archivo ruta="{r}">\n{t}\n</archivo>' for r, t in prep["archivos"].items())
                 + (f"\n\nDiff desde la última revisión:\n<diff>\n{prep['diff']}\n</diff>" if prep["diff"] else ""))
    client = anthropic.Anthropic(api_key=k, max_retries=2, timeout=900)
    with client.beta.messages.stream(
        model=MODELO, max_tokens=64000, system=SISTEMA,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",  # si el modelo rechaza, el servidor usa uno de respaldo
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": contenido}],
    ) as stream:
        msg = stream.get_final_message()
    eur = _coste_eur(msg.usage)
    _registrar(uso="corrector", motivo=motivo, modelo=msg.model, entrada=msg.usage.input_tokens, salida=msg.usage.output_tokens,
               eur=eur, stop=msg.stop_reason, carpeta=str(prep["carpeta"]))
    if msg.stop_reason == "refusal":
        raise RuntimeError("Claude no ha querido corregir esto (rechazo de seguridad).")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("La corrección no cabía en una respuesta: divide el trabajo en partes más pequeñas.")
    texto = next((b.text for b in msg.content if b.type == "text"), "")
    return json.loads(texto), eur


def aplicar(prep, res, eur):
    carpeta = prep["carpeta"]; hechos = []
    for c in res.get("cambios", []):
        r = c["ruta"].replace("\\", "/").lstrip("/")
        p = (carpeta / r).resolve()
        if carpeta not in p.parents or r not in prep["archivos"] or SECRETO_NOMBRE.search(p.name) or ".git" in p.relative_to(carpeta).parts:
            continue  # solo archivos que se le enviaron, dentro de la carpeta
        original = p.read_text(encoding="utf-8", errors="replace")
        nuevo = _destapar(c["contenido"], prep.get("guardados", []))  # los secretos se vuelven a poner aquí, en el PC
        if "[CLAVE OCULTA" in nuevo:  # un marcador que no sabemos restaurar: mejor no tocar ese archivo
            continue
        if nuevo.strip() == original.strip():
            continue
        p.write_text(nuevo, encoding="utf-8"); hechos.append({"ruta": r, "tipo": c["tipo"], "motivo": c["motivo"]})
    if not hechos:
        return hechos, None
    diario = carpeta / "DIARIO.md"
    if diario.exists():
        with diario.open("a", encoding="utf-8") as f:
            f.write(f"\n## {time.strftime('%d/%m/%Y %H:%M')} · Corrección Claude\n\n{res.get('resumen', '').strip()}\n\n"
                    + "\n".join(f"- **{h['ruta']}** ({h['tipo']}): {h['motivo']}" for h in hechos)
                    + f"\n\n_Coste: {eur:.3f} €. Se puede deshacer con `git revert` de este commit._\n")
    _git(carpeta, "add", "--", *[h["ruta"] for h in hechos], *(["DIARIO.md"] if diario.exists() else []))
    titulo = (res.get("resumen") or "correcciones").strip().splitlines()[0][:60]
    code, _ = _git(carpeta, "commit", "-m", f"Corrección Claude: {titulo}", "-m",
                   "\n".join(f"- {h['ruta']} ({h['tipo']}): {h['motivo']}" for h in hechos))
    _, sha = _git(carpeta, "rev-parse", "--short", "HEAD")
    return hechos, sha.strip() if code == 0 else None


def corregir(carpeta, motivo="manual", base=None):
    """Devuelve un texto para el usuario. Respeta el tope diario."""
    if not conf().get("activo"):
        return "🔧 Corrector Claude: está desactivado."
    with _lock:
        prep = preparar(carpeta, base)
        if not prep["archivos"]:
            return "🔧 Corrector Claude: no hay archivos nuevos o cambiados que corregir."
        est = estimar_eur(prep); gastado = gastado_hoy_eur(); tope = conf()["tope_eur_dia"]
        if gastado + est > tope:
            _registrar(uso="corrector", motivo=motivo, eur=0, bloqueado=f"tope diario: llevas {gastado:.2f} € y costaría ~{est:.2f} €")
            return (f"🔧 Corrector Claude: no lo lanzo porque pasaría el tope de {tope:.2f} €/día "
                    f"(hoy llevas {gastado:.2f} € y esto costaría unos {est:.2f} €). Puedes subir el tope en Ajustes → Conectores.")
        res, eur = llamar_claude(prep, motivo)
        hechos, sha = aplicar(prep, res, eur)
        pie = f"\n\n(Coste: {eur:.3f} € · hoy: {gastado_hoy_eur():.2f} € de {tope:.2f} €)"
        if prep["omitidos"]:
            pie += "\nNo enviados a la nube: " + "; ".join(prep["omitidos"][:6])
        if not hechos:
            return "🔧 Corrector Claude: revisado, no había nada que corregir." + pie
        return (f"🔧 Corrector Claude — commit {sha or '(sin commit)'}: {res.get('resumen', '').strip()}\n"
                + "\n".join(f"• {h['ruta']} ({h['tipo']}): {h['motivo']}" for h in hechos) + pie)


# ---------- API ----------
def _solo_usuario(h):
    if getattr(h, "rol", None) == "invitada":
        h.send(403, {"error": "no permitido"}); return False
    return True


def api_corregir(h):
    if not _solo_usuario(h):
        return
    if not conf().get("activo"):
        return h.send(403, {"error": "El Corrector Claude está desactivado."})
    d = chat.leer_cuerpo(h)
    proy = next((p for p in chat.leer(chat.F_PROY, []) if p.get("id") == d.get("proyecto")), None)
    if not proy or not proy.get("carpeta"):
        return h.send(400, {"error": "Este proyecto no tiene carpeta: el corrector solo trabaja dentro de la carpeta de un proyecto."})
    try:
        h.send(200, {"texto": corregir(proy["carpeta"], "botón")})
    except Exception as e:
        h.send(500, {"error": str(e)[:300]})


def api_estado(h):
    if not _solo_usuario(h):
        return
    c = conf()
    h.send(200, {"activo": bool(c.get("activo")), "clave": bool(clave()), "hoy_eur": gastado_hoy_eur(), "tope_eur_dia": c["tope_eur_dia"], "auto_tras_pesado": c["auto_tras_pesado"],
                 "modelo": MODELO})


def api_config(h):
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se cambia desde el PC."})
    d = chat.leer_cuerpo(h); c = conf()
    if "clave" in d:
        k = (d["clave"] or "").strip()
        if not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", k):
            return h.send(400, {"error": "Eso no parece una clave de API de Anthropic (empieza por sk-ant-)."})
        correo.cred_guardar("anthropic-key", "anthropic", k)
    if d.get("borrar_clave"):
        correo.cred_borrar("anthropic-key")
    if "tope_eur_dia" in d:
        c["tope_eur_dia"] = max(0.0, min(20.0, float(d["tope_eur_dia"])))
    if "auto_tras_pesado" in d:
        c["auto_tras_pesado"] = bool(d["auto_tras_pesado"])
    chat.escribir(F_CONF, c); h.send(200, {"ok": True})


def claude_code_exe():
    """El Claude Code que trae la app de Claude (la versión más nueva)."""
    base = Path.home() / "AppData" / "Local" / "Claude-Data"
    exes = sorted(base.glob("claude_*/claude-code/*/*/claude.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    return exes[0] if exes else None


def api_abrir_claude_code(h):
    # Abre una terminal con Claude Code en la carpeta del proyecto, para que el usuario lo use él (uso normal de su plan).
    # No se le manda nada automáticamente.
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se abre en el PC."})
    d = chat.leer_cuerpo(h)
    proy = next((p for p in chat.leer(chat.F_PROY, []) if p.get("id") == d.get("proyecto")), None)
    exe = claude_code_exe()
    if not proy or not proy.get("carpeta") or not Path(proy["carpeta"]).is_dir():
        return h.send(400, {"error": "El proyecto no tiene carpeta."})
    if not exe:
        return h.send(404, {"error": "No encuentro Claude Code: abre la app de Claude y usa la pestaña Code."})
    subprocess.Popen(["cmd.exe", "/c", "start", "Claude Code", "/D", proy["carpeta"], str(exe)], creationflags=NO_WINDOW)
    h.send(200, {"ok": True})


def register(R):
    R[("POST", "/api/corrector/abrir_claude_code")] = api_abrir_claude_code
    R[("POST", "/api/corrector/corregir")] = api_corregir
    R[("GET", "/api/corrector/estado")] = api_estado
    R[("POST", "/api/corrector/config")] = api_config
