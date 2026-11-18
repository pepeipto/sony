# Motor «Claude (API)» para Sony: traduce el formato OpenAI que ya usa el panel (mensajes, herramientas, imágenes)
# al SDK oficial de Anthropic. La clave vive SOLO en el Llavero de macOS («anthropic-key»), nunca en archivos ni logs.
# - Tope de gasto mensual (por defecto 25 $): al llegar, se para y se avisa. El gasto es una estimación local;
#   la cifra real está en la consola de Anthropic.
# - Sin temperatura (los modelos 5.5 la rechazan). Razonamiento apagado salvo que se active en Ajustes.
# - Si Claude rechaza una petición por seguridad, el servidor reintenta con el modelo de respaldo (fallbacks).
import io, json, re, sys, time, urllib.error
from pathlib import Path

import compat
import llavero

for _p in (compat.IA / "sony" / "venv" / "lib").glob("python3*/site-packages"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

BASE = Path(__file__).resolve().parent
F_GASTO = BASE / "gasto-claude.json"
LOG = compat.LOGS / "claude-api.jsonl"
CLAVE_ID = "anthropic-key"

# $ por millón de tokens (entrada, salida, lectura de caché, escritura de caché 5 min)
MODELOS = {
    "claude-sonnet-5-5": {"nombre": "Claude Sonnet 5.5", "in": 2.0, "out": 10.0, "cr": 0.10, "cw": 2.5, "fallbacks": True},
    "claude-opus-5-5": {"nombre": "Claude Opus 5.5", "in": 4.0, "out": 20.0, "cr": 0.20, "cw": 5.0, "fallbacks": True},
    "claude-haiku-5-5": {"nombre": "Claude Haiku 5.5", "in": 0.10, "out": 0.50, "cr": 0.01, "cw": 0.125, "fallbacks": False},
}
DEFECTO = "claude-sonnet-5-5"
TOPE_DEF = 25.0
BETA_FALLBACK = "server-side-fallback-2026-07-01"
_estado = {"nivel": {}}  # por modelo: primera variante de petición que la API acepta (resistencia a cambios de la API)


def _precio(modelo):
    """Precio del modelo; si es un identificador nuevo (cambiado en ajustes), se usa el de su familia."""
    if modelo in MODELOS:
        return MODELOS[modelo]
    for fam, base in (("haiku", "claude-haiku-5-5"), ("opus", "claude-opus-5-5")):
        if fam in modelo:
            return MODELOS[base]
    return MODELOS["claude-sonnet-5-5"]


# ---------- ajustes, clave y gasto ----------
def _aj():
    import chat
    return chat.ajustes()


def modelo_id():
    m = _aj().get("claude_modelo", DEFECTO)
    return m if m in MODELOS else DEFECTO


def hay_clave():
    try:
        return bool(llavero.cred_leer(CLAVE_ID)[1])
    except Exception:
        return False


def _clave():
    return llavero.cred_leer(CLAVE_ID)[1]


def tope():
    try:
        return float(_aj().get("claude_tope_usd", TOPE_DEF))
    except Exception:
        return TOPE_DEF


def gasto():
    mes = time.strftime("%Y-%m")
    try:
        g = json.loads(F_GASTO.read_text())
    except Exception:
        g = {}
    if g.get("mes") != mes:
        g = {"mes": mes, "usd": 0.0, "llamadas": 0}
    return g


def _sumar(modelo, uso):
    p = _precio(modelo)
    ent = getattr(uso, "input_tokens", 0) or 0
    sal = getattr(uso, "output_tokens", 0) or 0
    cr = getattr(uso, "cache_read_input_tokens", 0) or 0
    cw = getattr(uso, "cache_creation_input_tokens", 0) or 0
    det = getattr(uso, "cache_creation", None)  # desglose: las escrituras de 1 hora cuestan 2x la entrada; las de 5 minutos, 1,25x
    cw1h = (getattr(det, "ephemeral_1h_input_tokens", 0) or 0) if det is not None else 0
    cw1h = min(cw1h, cw)
    usd = (ent * p["in"] + sal * p["out"] + cr * p["cr"] + (cw - cw1h) * p["cw"] + cw1h * p["in"] * 2) / 1e6
    g = gasto(); g["usd"] = round(g["usd"] + usd, 6); g["llamadas"] = g.get("llamadas", 0) + 1
    F_GASTO.write_text(json.dumps(g));
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:  # solo cifras: nunca el contenido de la conversación
            f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "modelo": modelo, "in": ent, "out": sal, "cache_leida": cr,
                                "cache_escrita": cw, "usd": round(usd, 6)}) + "\n")
    except Exception:
        pass
    return usd


def resumen():
    g = gasto()
    return {"clave": hay_clave(), "modelo": modelo_id(), "tope_usd": tope(), "gasto_usd": round(g["usd"], 3), "mes": g["mes"],
            "llamadas": g.get("llamadas", 0), "modelos": [{"id": k, "nombre": v["nombre"], "in": v["in"], "out": v["out"]} for k, v in MODELOS.items()]}


# ---------- traducción OpenAI -> Anthropic ----------
def _texto(c):
    if isinstance(c, str):
        return c
    return "".join(p.get("text", "") for p in (c or []) if isinstance(p, dict) and p.get("type") == "text")


_DATA = re.compile(r"^data:(image/[A-Za-z0-9.+-]+);base64,(.*)$", re.S)


def _partes_usuario(c):
    if isinstance(c, str):
        return [{"type": "text", "text": c}] if c else []
    out = []
    for p in c or []:
        if p.get("type") == "text" and p.get("text"):
            out.append({"type": "text", "text": p["text"]})
        elif p.get("type") == "image_url":
            url = (p.get("image_url") or {}).get("url", "")
            m = _DATA.match(url)
            if m:
                mt = m.group(1).replace("image/jpg", "image/jpeg")
                out.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": m.group(2)}})
            elif url.startswith("https://"):
                out.append({"type": "image", "source": {"type": "url", "url": url}})
    return out


def _unir(out, rol, bloques):
    if not bloques:
        return
    if out and out[-1]["role"] == rol:
        out[-1]["content"].extend(bloques)
    else:
        out.append({"role": rol, "content": list(bloques)})


def a_anthropic(msgs):
    sistema, out = [], []
    ids, vacios, n_id = {}, [], 0  # los ids de herramienta deben ser únicos y válidos aunque vengan de otro modelo (llama-server)
    for m in msgs:
        rol = m.get("role")
        if rol == "system":
            t = _texto(m.get("content"))
            if t:
                sistema.append(t)
        elif rol == "assistant":
            b = []
            t = _texto(m.get("content")).strip()
            if t:
                b.append({"type": "text", "text": t})
            for tc in m.get("tool_calls") or []:
                n_id += 1; orig = tc.get("id") or ""
                nuevo = re.sub(r"[^A-Za-z0-9_-]", "_", orig)[:60] or f"toolu_{n_id}"
                if nuevo in ids.values(): nuevo = f"{nuevo}_{n_id}"
                if orig: ids[orig] = nuevo
                else: vacios.append(nuevo)
                tc = {**tc, "id": nuevo}
                f = tc.get("function") or {}
                try:
                    args = json.loads(f.get("arguments") or "{}")
                except Exception:
                    args = {}
                b.append({"type": "tool_use", "id": tc.get("id"), "name": f.get("name"), "input": args if isinstance(args, dict) else {}})
            _unir(out, "assistant", b or [{"type": "text", "text": "(sin texto)"}])
        elif rol == "tool":
            tid = ids.get(m.get("tool_call_id") or "") or (vacios.pop(0) if vacios else (m.get("tool_call_id") or "toolu_x"))
            _unir(out, "user", [{"type": "tool_result", "tool_use_id": tid, "content": _texto(m.get("content")) or "(vacío)"}])
        else:
            _unir(out, "user", _partes_usuario(m.get("content")))
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "Hola"}]})
    return "\n\n".join(sistema), out


def _herramientas(tools):
    res = []
    for t in tools or []:
        f = t.get("function") or {}
        res.append({"name": f["name"], "description": f.get("description", ""), "input_schema": f.get("parameters") or {"type": "object", "properties": {}}})
    return res


def _peticion(payload, modelo=None):
    modelo = modelo or modelo_id()
    a = _aj()
    sistema, msgs = a_anthropic(payload.get("messages", []))
    tools = _herramientas(payload.get("tools"))
    esfuerzo = a.get("claude_esfuerzo_agente", "medium") if tools else a.get("claude_esfuerzo_chat", "low")
    pet = {"model": modelo, "max_tokens": int(payload.get("max_tokens") or 4096), "messages": msgs,
           "output_config": {"effort": esfuerzo}, "cache_control": {"type": "ephemeral"}}
    # Caché: las herramientas y el sistema son estables entre mensajes y conversaciones; se guardan 1 hora con su propio punto de corte.
    # Sin esto, cada mensaje nuevo volvía a pagar el prompt entero (~21.000 tokens). La conversación usa la caché automática de 5 minutos.
    if sistema:
        pet["system"] = [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]
    if tools:
        tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral", "ttl": "1h"}}
        pet["tools"] = tools
    razona = bool(a.get("razonamiento"))
    if not razona:  # apagar el razonamiento: cada modelo 5.5 lo pide distinto; Opus no se puede apagar (esfuerzo bajo)
        if "sonnet" in modelo:
            pet["thinking"] = {"type": "between_tools"}
        elif "haiku" in modelo:
            pet["thinking"] = {"type": "disabled"}
    return modelo, pet


def _cliente():
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("Falta el SDK de Anthropic (~/IA/sony/venv).")
    k = _clave()
    if not k:
        raise PermissionError("Falta la clave de la API: pégala en Ajustes → Modelo.")
    return anthropic, anthropic.Anthropic(api_key=k, timeout=600.0, max_retries=2)


def _comprobar_tope():
    g, t = gasto(), tope()
    if t and g["usd"] >= t:
        raise PermissionError(f"Has llegado al tope mensual de Claude ({t:g} $, gastados {g['usd']:.2f} $). Súbelo en Ajustes → Modelo o usa el modelo local.")


def _variantes(modelo, pet):
    """Formas de pedir lo mismo, de la más completa a la más simple. Si la API cambia y rechaza una (error 400), se prueba la siguiente
    y se recuerda cuál funciona. Así un cambio de parámetros en la API no deja a Sony sin responder."""
    v = []
    if "haiku" not in modelo:  # respaldo del servidor ante rechazos de seguridad (beta)
        v.append((True, {**pet, "betas": [BETA_FALLBACK], "fallbacks": "default"}))
    v.append((False, pet))
    simple = {k: x for k, x in pet.items() if k not in ("thinking", "output_config")}
    if isinstance(simple.get("system"), list):
        simple["system"] = [{**b, "cache_control": {"type": "ephemeral"}} for b in simple["system"]]
    if simple.get("tools"):
        simple["tools"] = [{k: x for k, x in t.items() if k != "cache_control"} for t in simple["tools"]]
    v.append((False, simple))
    minimo = {k: x for k, x in simple.items() if k != "cache_control"}
    if isinstance(minimo.get("system"), list):
        minimo["system"] = "\n\n".join(b["text"] for b in minimo["system"])
    v.append((False, minimo))
    return v


def _retirado(modelo):
    return PermissionError(f"el modelo «{modelo}» ya no está disponible en la API de Claude; cambia su identificador en ajustes.json (claude_ids)")


def _http_error(e):
    cuerpo = json.dumps({"error": {"message": str(getattr(e, "message", e))}}).encode()
    return urllib.error.HTTPError("claude-api", getattr(e, "status_code", 500) or 500, str(e), {}, io.BytesIO(cuerpo))


# ---------- llamadas ----------
class _Resp:
    def __init__(self, datos): self._d = json.dumps(datos, ensure_ascii=False).encode()
    def read(self): return self._d
    def close(self): pass


def _a_openai(msg):
    texto, llamadas = "", []
    for b in msg.content:
        if b.type == "text":
            texto += b.text
        elif b.type == "tool_use":
            llamadas.append({"id": b.id, "type": "function", "function": {"name": b.name, "arguments": json.dumps(b.input, ensure_ascii=False)}})
    if msg.stop_reason == "refusal":
        cat = getattr(getattr(msg, "stop_details", None), "category", None)
        texto += f"\n\n⚠️ Claude ha rechazado esta petición por seguridad{f' ({cat})' if cat else ''}."
    m = {"role": "assistant", "content": texto or None}
    if llamadas:
        m["tool_calls"] = llamadas
    return {"choices": [{"message": m, "finish_reason": "tool_calls" if llamadas else "stop"}]}


def completar(payload, modelo=None):
    _comprobar_tope()
    anthropic, cli = _cliente()
    modelo, pet = _peticion(payload, modelo)
    vs = _variantes(modelo, pet); ini = min(_estado["nivel"].get(modelo, 0), len(vs) - 1)
    try:
        for n in range(ini, len(vs)):
            beta, kw = vs[n]
            try:
                msg = (cli.beta.messages if beta else cli.messages).create(**kw)
                _estado["nivel"][modelo] = n
                break
            except anthropic.BadRequestError:
                if n == len(vs) - 1:
                    raise
        _sumar(modelo, msg.usage)
        return _Resp(_a_openai(msg))
    except anthropic.NotFoundError:
        raise _retirado(modelo)
    except anthropic.APIStatusError as e:
        raise _http_error(e)


class _Flujo:
    """Iterable de líneas SSE en formato OpenAI, como las que da llama-server."""
    def __init__(self, cli, anthropic, modelo, pet):
        self.cli, self.anthropic, self.modelo, self.pet = cli, anthropic, modelo, pet

    def _evento(self, texto):
        return ("data: " + json.dumps({"choices": [{"delta": {"content": texto}}]}, ensure_ascii=False) + "\n\n").encode()

    def __iter__(self):
        vs = _variantes(self.modelo, self.pet); ini = min(_estado["nivel"].get(self.modelo, 0), len(vs) - 1); emitido = False
        for n in range(ini, len(vs)):
            beta, kw = vs[n]
            api = self.cli.beta.messages if beta else self.cli.messages
            try:
                with api.stream(**kw) as st:
                    for t in st.text_stream:
                        emitido = True
                        yield self._evento(t)
                    final = st.get_final_message()
                _estado["nivel"][self.modelo] = n
                _sumar(self.modelo, final.usage)
                if final.stop_reason == "refusal":
                    yield self._evento("\n\n⚠️ Claude ha rechazado esta petición por seguridad.")
                break
            except self.anthropic.BadRequestError as e:
                if not emitido and n < len(vs) - 1:
                    continue
                yield self._evento(f"⚠️ La API de Claude ha rechazado la petición: {getattr(e, 'message', e)}")
                break
            except self.anthropic.NotFoundError:
                yield self._evento(f"⚠️ El modelo «{self.modelo}» ya no está disponible en la API de Claude. Cambia su identificador en ajustes.json (claude_ids) o usa otro modelo.")
                break
            except self.anthropic.APIStatusError as e:
                yield self._evento(f"⚠️ Error de la API de Claude ({e.status_code}): {getattr(e, 'message', e)}")
                break
            except Exception as e:
                yield self._evento(f"⚠️ No he podido conectar con Claude ({type(e).__name__}). Revisa internet o usa el modelo local.")
                break
        yield b"data: [DONE]\n\n"

    def close(self): pass


def flujo(payload, modelo=None):
    _comprobar_tope()
    anthropic, cli = _cliente()
    modelo, pet = _peticion(payload, modelo)
    return _Flujo(cli, anthropic, modelo, pet)


def abrir(payload, timeout=600, modelo=None):
    return flujo(payload, modelo) if payload.get("stream") else completar(payload, modelo)


# ---------- rutas ----------
def api_config(h):
    import chat
    if h.command == "GET":
        return h.send(200, resumen())
    d = chat.leer_cuerpo(h)
    try:
        if d.get("borrar_clave"):
            llavero.cred_borrar(CLAVE_ID)
        k = (d.get("clave") or "").strip()
        if k:
            if not k.startswith("sk-ant-") or len(k) < 30:
                return h.send(400, {"error": "Esa no parece una clave de Anthropic (empieza por sk-ant-)."})
            llavero.cred_guardar(CLAVE_ID, "anthropic", k)
        cambios = {}
        if d.get("modelo") in MODELOS:
            cambios["claude_modelo"] = d["modelo"]
        if "tope_usd" in d:
            cambios["claude_tope_usd"] = max(0.0, float(d["tope_usd"]))
        if cambios:
            a = chat.ajustes(); a.update(cambios); chat.escribir(chat.F_AJ, a)
    except Exception as e:
        return h.send(500, {"error": f"{type(e).__name__}"})  # nunca devolver ni registrar la clave
    h.send(200, resumen())


def register(R):
    R[("GET", "/api/claude/config")] = api_config
    R[("POST", "/api/claude/config")] = api_config
