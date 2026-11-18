# Publicar en redes sociales del usuario, SOLO con la API oficial de cada red y en su propia cuenta.
# Nada de likes, follows, mensajes directos masivos, cuentas falsas ni raspar con navegador.
# Por defecto cada publicación pide tarjeta. El usuario puede activar él mismo «publicar sin preguntar» por red, con límite diario.
import json, time, urllib.parse, urllib.request
from pathlib import Path

import chat
import correo  # cred_guardar / cred_leer (Llavero de macOS)

F_CONF = Path(__file__).resolve().parent / "redes.json"
import compat
LOG = compat.LOGS / "redes.jsonl"
REDES = {
    "x": {"nombre": "X (Twitter)", "api": True, "max": 280},
    "linkedin": {"nombre": "LinkedIn", "api": True, "max": 3000},
    "reddit": {"nombre": "Reddit", "api": True, "max": 40000},
    "instagram": {"nombre": "Instagram", "api": False, "max": 2200},  # necesita imagen o vídeo alojado: de momento solo borradores
    "tiktok": {"nombre": "TikTok", "api": False, "max": 2200},        # necesita vídeo y app auditada: de momento solo borradores
}


def conf():
    c = chat.leer(F_CONF, {})
    for r in REDES:
        c.setdefault(r, {"sin_preguntar": False, "limite_dia": 3})
    return c


def _token(red):
    return correo.cred_leer(f"redes-{red}")


def publicadas_hoy(red):
    if not LOG.exists():
        return 0
    hoy = time.strftime("%Y-%m-%d")
    return sum(1 for l in LOG.read_text(encoding="utf-8").splitlines()
               if l.strip() and (d := json.loads(l)).get("red") == red and d.get("fecha", "").startswith(hoy) and d.get("ok"))


def sin_preguntar_ok(red):
    """True solo si el usuario activó «publicar sin preguntar» en esa red y no se ha pasado el límite de hoy."""
    c = conf().get(red) or {}
    return bool(c.get("sin_preguntar")) and publicadas_hoy(red) < int(c.get("limite_dia") or 0)


def _registrar(**d):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), **d}, ensure_ascii=False) + "\n")


def _pedir(url, datos=None, cab=None, form=False):
    cuerpo = None
    if datos is not None:
        cuerpo = urllib.parse.urlencode(datos).encode() if form else json.dumps(datos).encode()
    r = urllib.request.Request(url, data=cuerpo, headers={"Content-Type": "application/x-www-form-urlencoded" if form else "application/json", **(cab or {})})
    with urllib.request.urlopen(r, timeout=30) as resp:
        t = resp.read().decode() or "{}"
        return resp.status, json.loads(t) if t.strip().startswith(("{", "[")) else {"texto": t}


def _publicar_api(red, texto, titulo, subreddit, usuario, tok):
    if red == "x":  # API v2, token de usuario OAuth 2.0 con permiso tweet.write
        _, j = _pedir("https://api.x.com/2/tweets", {"text": texto}, {"Authorization": f"Bearer {tok}"})
        tid = (j.get("data") or {}).get("id")
        return f"https://x.com/i/web/status/{tid}" if tid else str(j)[:200]
    if red == "linkedin":  # API de Posts, permiso w_member_social; usuario = id de persona (sub de /v2/userinfo)
        cab = {"Authorization": f"Bearer {tok}", "LinkedIn-Version": "202510", "X-Restli-Protocol-Version": "2.0.0"}
        _pedir("https://api.linkedin.com/rest/posts", {"author": f"urn:li:person:{usuario}", "commentary": texto, "visibility": "PUBLIC",
               "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
               "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}, cab)
        return "publicado en tu perfil de LinkedIn"
    if red == "reddit":  # API oficial, app tipo «script» de su propia cuenta
        if not subreddit or not titulo:
            raise ValueError("Para Reddit hacen falta el subreddit y el título.")
        cab = {"Authorization": f"bearer {tok}", "User-Agent": f"windows:ia-sony:1.0 (by /u/{usuario or 'usuario'})"}
        _, j = _pedir("https://oauth.reddit.com/api/submit", {"sr": subreddit.removeprefix("r/"), "kind": "self", "title": titulo,
                                                              "text": texto, "api_type": "json"}, cab, form=True)
        err = (j.get("json") or {}).get("errors")
        if err:
            raise RuntimeError(f"Reddit respondió: {err}")
        return ((j.get("json") or {}).get("data") or {}).get("url", "publicado en Reddit")
    raise ValueError("Red sin API de publicación conectada.")


def t_publicar(a):
    red = (a.get("red") or "").strip().lower().replace("twitter", "x")
    if red not in REDES:
        return f"Red desconocida. Disponibles: {', '.join(REDES)}."
    texto = (a.get("texto") or "").strip()
    if not texto:
        return "Falta el texto de la publicación."
    if len(texto) > REDES[red]["max"]:
        return f"El texto es demasiado largo para {REDES[red]['nombre']} (máximo {REDES[red]['max']} caracteres)."
    if not REDES[red]["api"]:
        _registrar(red=red, ok=False, modo="borrador", texto=texto[:500])
        return f"{REDES[red]['nombre']} aún no publica sola (necesita imagen/vídeo y app aprobada). Te dejo el texto como borrador:\n\n{texto}"
    usuario, tok = _token(red)
    if not tok:
        return f"{REDES[red]['nombre']} no está conectada. El usuario tiene que pegar su token en Conectores → Redes sociales."
    modo = "sin_preguntar" if sin_preguntar_ok(red) else "con_tarjeta"
    try:
        res = _publicar_api(red, texto, a.get("titulo"), a.get("subreddit"), usuario, tok)
        _registrar(red=red, ok=True, modo=modo, texto=texto[:1000], resultado=str(res)[:300], subreddit=a.get("subreddit"))
        return f"Publicado en {REDES[red]['nombre']}: {res}"
    except urllib.error.HTTPError as e:
        _registrar(red=red, ok=False, modo=modo, texto=texto[:500], error=f"HTTP {e.code}")
        return f"{REDES[red]['nombre']} respondió con error {e.code}. Puede que el token haya caducado: vuelve a conectarla."
    except Exception as e:
        _registrar(red=red, ok=False, modo=modo, texto=texto[:500], error=str(e)[:200])
        return f"No se pudo publicar: {e}"


def detalle(args):
    red = (args.get("red") or "").lower()
    c = conf().get(red, {})
    extra = f"\nSubreddit: r/{args.get('subreddit')}\nTítulo: {args.get('titulo')}" if red == "reddit" else ""
    return (f"Publicar en {REDES.get(red, {}).get('nombre', red)} (tu cuenta, API oficial){extra}\n\n{args.get('texto', '')}\n\n"
            f"Hoy llevas {publicadas_hoy(red)} · límite sin preguntar: {c.get('limite_dia', 3)} ({'activado' if c.get('sin_preguntar') else 'desactivado'})")


HERRAMIENTAS = {
    "redes_publicar": (t_publicar, True, "Publicar en una red social",
                       {"red": "string", "texto": "string", "titulo": "string", "subreddit": "string"},
                       "Publica en una red social del usuario con la API oficial (x, linkedin, reddit; instagram y tiktok solo borrador). "
                       "Solo si el usuario lo pide. Para Reddit indica subreddit y título y respeta sus normas de autopromoción (di que es tu producto). "
                       "Nunca likes, follows, mensajes directos ni publicar lo mismo en muchos sitios."),
}


# ---------- API para Ajustes y Conectores ----------
def api_estado(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    c = conf()
    h.send(200, [{"id": r, "nombre": v["nombre"], "api": v["api"], "conectada": bool(_token(r)[1]),
                  "sin_preguntar": c[r]["sin_preguntar"], "limite_dia": c[r]["limite_dia"], "hoy": publicadas_hoy(r)} for r, v in REDES.items()])


def api_config(h):
    # Solo desde el propio PC (no desde el móvil) y solo el usuario: es él quien decide sobre sus cuentas.
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se cambia desde el PC."})
    d = chat.leer_cuerpo(h); c = conf(); r = d.get("red")
    if r not in REDES:
        return h.send(400, {"error": "red desconocida"})
    if "sin_preguntar" in d:
        c[r]["sin_preguntar"] = bool(d["sin_preguntar"]) and REDES[r]["api"]
    if "limite_dia" in d:
        c[r]["limite_dia"] = max(0, min(10, int(d["limite_dia"])))
    chat.escribir(F_CONF, c); _registrar(red=r, ok=True, modo="ajuste", cambio={k: c[r][k] for k in ("sin_preguntar", "limite_dia")})
    h.send(200, c[r])


def api_token(h):
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se cambia desde el PC."})
    d = chat.leer_cuerpo(h); r = d.get("red")
    if r not in REDES or not REDES[r]["api"]:
        return h.send(400, {"error": "red sin API de publicación"})
    if d.get("borrar"):
        correo.cred_borrar(f"redes-{r}"); return h.send(200, {"ok": True})
    tok = (d.get("token") or "").strip()
    if len(tok) < 10:
        return h.send(400, {"error": "Token vacío o demasiado corto"})
    correo.cred_guardar(f"redes-{r}", (d.get("usuario") or "").strip() or r, tok)
    h.send(200, {"ok": True})


def api_registro(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    lineas = LOG.read_text(encoding="utf-8").splitlines()[-50:] if LOG.exists() else []
    h.send(200, [json.loads(l) for l in reversed(lineas) if l.strip()])


def register(R):
    R[("GET", "/api/redes/estado")] = api_estado
    R[("POST", "/api/redes/config")] = api_config
    R[("POST", "/api/redes/token")] = api_token
    R[("GET", "/api/redes/registro")] = api_registro
