# Diario de los últimos 7 días de Sony (15/11/2026).
# - Cada chat del usuario tiene un resumen corto (tema, decisiones, pendientes, fecha) en chats/_resumenes.json.
# - Se genera cuando el chat lleva ≥ 5 min sin actividad y SOLO si el modelo de chat YA está cargado y libre.
#   Nunca carga un modelo para esto ni interrumpe al usuario: si no hay modelo, queda en cola para la próxima vez.
# - Sony lleva siempre en contexto un «diario de 7 días» compacto (≤ 20 líneas). Lo más viejo sale del diario pero sigue buscable.
# - Los chats de la invitada (perfil «invitada», Telegram de invitada) NUNCA entran.
# - Herramientas: chat_leer (abre un chat completo) y chats_buscar (busca en todos los chats). Solo lectura.
import json, re, threading, time, urllib.request
from pathlib import Path

import chat

F = chat.CHATS / "_resumenes.json"
INACTIVO_S = 5 * 60
DIAS = 7
_lock = threading.Lock()


def resumenes():
    return chat.leer(F, {})


def _hilos_usuario():
    for f in chat.CHATS.glob("*.json"):
        if f.name.startswith("_"):
            continue  # _papelera, _tg_invitada_*, _resumenes…
        d = chat.leer(f, None)
        if not d or d.get("perfil") == "invitada" or not d.get("mensajes") or f.stem.startswith("tut"):
            continue  # ni la invitada ni los chats de prueba de Claude (tutorial, examen, entrenamiento)
        yield d


def _ultimo_t(d):
    return max([m.get("t", 0) or 0 for m in d["mensajes"]] + [d.get("actualizado", 0) or 0])


def diario_7d(excluir=None, lineas=18):
    r = resumenes(); ahora = time.time()
    items = [(v["fecha_t"], k, v) for k, v in r.items() if ahora - v.get("fecha_t", 0) < DIAS * 86400 and k != excluir
             and (chat.CHATS / f"{k}.json").exists()]  # Mac: un chat borrado (en la papelera) deja de contar
    if not items:
        return ""
    items.sort(reverse=True)
    out = ["DIARIO DE LOS ÚLTIMOS 7 DÍAS (resúmenes de tus chats con el usuario; para el detalle usa chat_leer con el id):"]
    for _, k, v in items[:lineas]:
        extra = []
        if v.get("decisiones"):
            extra.append("decidido: " + v["decisiones"])
        if v.get("pendientes"):
            extra.append("pendiente: " + v["pendientes"])
        out.append(f"- {time.strftime('%d/%m', time.localtime(v['fecha_t']))} «{v.get('titulo', '')[:50]}» [{k}]: {v.get('tema', '')}"
                   + (" · " + " · ".join(extra) if extra else ""))
    return "\n".join(out)[:3500]


def _resumir(d):
    """Pide el resumen al modelo YA cargado (no carga nada). Devuelve dict o None."""
    hist = []
    for m in d["mensajes"][-40:]:
        hist.append(f"{'Sony' if m.get('rol') == 'ia' else 'el usuario'}: {(m.get('texto') or '')[:600]}")
    prompt = ("Resume esta conversación entre el usuario y su asistente Sony en JSON con estas claves exactas: "
              '{"tema": "una frase", "decisiones": "lo que se decidió o hizo (corto, o vacío)", "pendientes": "lo que quedó por hacer (corto, o vacío)"}. '
              "En español, máximo 25 palabras por campo. Solo el JSON.\n\n" + "\n".join(hist))
    payload = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 220, "temperature": 0.2,
               "chat_template_kwargs": {"enable_thinking": False}}
    # 17/11: con Claude activo se resume con Haiku (barato); con el Qwen cargado, en local. Nunca carga un modelo para esto.
    txt = json.loads(chat.abrir(payload, 120, "haiku" if chat.es_claude() else None).read())["choices"][0]["message"]["content"] or ""
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else None


def pendientes_de_resumir():
    r = resumenes(); ahora = time.time(); cola = []
    for d in _hilos_usuario():
        ult = _ultimo_t(d)
        if ahora - ult > DIAS * 86400 or ahora - ult < INACTIVO_S:
            continue
        if r.get(d["id"], {}).get("hasta_t", 0) >= ult:
            continue
        cola.append(d)
    return cola


def _paso():
    """Un resumen como mucho por vuelta, y solo si el modelo está cargado, libre y el usuario no está escribiendo."""
    if not chat._proc.get("modelo") or not chat.llama_listo() or chat.modelo_ocupado():
        return "sin_modelo_o_ocupado"
    if time.time() - (chat._proc.get("ultimo_uso") or 0) < 120:
        return "usuario_activo"
    cola = pendientes_de_resumir()
    if not cola:
        return "nada"
    d = cola[0]
    res = _resumir(d)
    if not res:
        return "fallo"
    with _lock:
        r = resumenes()
        r[d["id"]] = {"titulo": d.get("titulo") or "Chat", "tema": str(res.get("tema", ""))[:200], "decisiones": str(res.get("decisiones", ""))[:200],
                      "pendientes": str(res.get("pendientes", ""))[:200], "fecha_t": _ultimo_t(d), "hasta_t": _ultimo_t(d), "hecho_t": time.time()}
        chat.escribir(F, r)
    return "hecho"


def _bucle():
    time.sleep(60)
    while True:
        try:
            _paso()
        except Exception:
            pass
        time.sleep(90)


# ---------- herramientas de Sony (solo lectura) ----------
def t_chat_leer(a):
    hid = re.sub(r"[^a-z0-9_-]", "", (a.get("id") or "").lower())
    d = chat.leer(chat.CHATS / f"{hid}.json", None) if hid else None
    if not d and a.get("titulo"):
        q = a["titulo"].lower()
        d = next((x for x in _hilos_usuario() if q in (x.get("titulo") or "").lower()), None)
    if not d or d.get("perfil") == "invitada":
        return "No encuentro ese chat."
    ms = d["mensajes"][-40:]
    return f"Chat «{d.get('titulo')}» ({len(d['mensajes'])} mensajes; últimos {len(ms)}):\n" + "\n".join(
        f"{'Sony' if m.get('rol') == 'ia' else 'el usuario'}{' 📌' if m.get('fijado') else ''}: {(m.get('texto') or '')[:700]}" for m in ms)


def t_chats_buscar(a):
    q = (a.get("texto") or "").lower().strip()
    if not q:
        return "¿Qué busco?"
    res = []
    for d in sorted(_hilos_usuario(), key=_ultimo_t, reverse=True):
        for m in d["mensajes"]:
            if q in (m.get("texto") or "").lower():
                i = m["texto"].lower().index(q)
                res.append(f"[{d['id']}] «{d.get('titulo')}» {time.strftime('%d/%m', time.localtime(m.get('t', 0) or 0))}: …{m['texto'][max(0, i - 80):i + 120]}…")
                break
        if len(res) >= 10:
            break
    return "\n".join(res) or "No aparece en ningún chat."


HERRAMIENTAS = {
    "chat_leer": (t_chat_leer, False, "Abrir un chat anterior", {"id": "string", "titulo": "string"},
                  "Lee un chat anterior del usuario (por su id del diario o parte del título) para ver el detalle."),
    "chats_buscar": (t_chats_buscar, False, "Buscar en los chats anteriores", {"texto": "string"},
                     "Busca una palabra o frase en todos los chats del usuario (también los de hace más de 7 días)."),
}


# ---------- Ajustes → Memoria ----------
def api_lista(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    r = resumenes()
    h.send(200, {"resumenes": sorted([{"id": k, **v} for k, v in r.items()], key=lambda x: -x["fecha_t"]),
                 "en_cola": len(pendientes_de_resumir())})


def api_borrar(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    hid = chat.leer_cuerpo(h).get("id")
    with _lock:
        r = resumenes(); r.pop(hid, None); chat.escribir(F, r)
    h.send(200, {"ok": True})


def register(R):
    R[("GET", "/api/diario")] = api_lista
    R[("POST", "/api/diario/borrar")] = api_borrar
    threading.Thread(target=_bucle, daemon=True, name="diario").start()
