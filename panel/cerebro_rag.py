# Recuperación automática del segundo cerebro (RAG) para Sony — 15/11/2026.
# En cada mensaje del usuario (nunca de la invitada) se buscan las notas más relevantes y se meten, recortadas, en el contexto.
# - Índice: el de buscador.py (bge-m3 en el PROCESADOR, 0 MB de VRAM), cargado en RAM como matriz numpy + BM25 por palabras.
# - Búsqueda híbrida (vector + BM25, fusión por rangos). Objetivo < 300 ms. Sin reranker (sube a ~1 s en CPU).
# - Actualización incremental: un hilo del propio panel mira cada 30 s si alguna nota ha cambiado y reindexa SOLO esas.
#   Nada de tareas programadas ni de arranque con Windows. Al guardar una nota desde Sony se reindexa al momento.
import math, re, threading, time, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import buscador, chat

CEREBRO = buscador.CEREBRO
_m = {"version": None, "mat": None, "meta": [], "bm25": None, "mapa": "", "estado": {}, "t_ultima": 0.0}
_lock = threading.Lock()
PALABRA = re.compile(r"[a-záéíóúüñ0-9]{3,}", re.I)
VACIAS = set("que los las del por para con una uno unos unas como mas más pero sus este esta esto estos estas ese esa eso hay muy sin sobre entre cuando donde porque también tambien the and for with you are está están ser son fue era han has hace".split())


def _tok(t):
    return [w for w in PALABRA.findall(t.lower()) if w not in VACIAS]


def _construir():
    """Pasa el índice de disco a estructuras rápidas en RAM (matriz normalizada + BM25)."""
    idx = buscador._indice["datos"] or chat.leer(buscador.F_INDICE, {"archivos": {}})
    buscador._indice["datos"] = idx
    meta, vecs, docs = [], [], []
    for rel, d in idx["archivos"].items():
        for t, v in zip(d["trozos"], d["vec"]):
            meta.append((rel, d["titulo"], t)); vecs.append(v); docs.append(_tok(t))
    mat = np.asarray(vecs, dtype=np.float32) if vecs else np.zeros((0, 1024), np.float32)
    df = Counter(w for d in docs for w in set(d)); N = max(len(docs), 1)
    idf = {w: math.log(1 + (N - n + 0.5) / (n + 0.5)) for w, n in df.items()}
    post = defaultdict(list); largos = np.array([len(d) for d in docs] or [1], dtype=np.float32)
    for i, d in enumerate(docs):
        for w, c in Counter(d).items():
            post[w].append((i, c))
    with _lock:
        _m.update(mat=mat, meta=meta, bm25={"idf": idf, "post": post, "largos": largos, "media": float(largos.mean())}, version=len(meta))
    _hacer_mapa()


def _hacer_mapa():
    todas = [f for f in CEREBRO.rglob("*.md")]
    principales = [f for f in todas if "/_fuentes/" not in str(f) and "/_herramientas/" not in str(f)]
    c = Counter(f.relative_to(CEREBRO).parts[0] if len(f.relative_to(CEREBRO).parts) > 1 else "(raíz)" for f in principales)
    ultima = max((f.stat().st_mtime for f in principales), default=0)
    hoy = sum(1 for f in principales if time.time() - f.stat().st_mtime < 86400)
    lineas = [f"MAPA DE TU SEGUNDO CEREBRO (~/segundo-cerebro): {len(principales)} notas · última actualización {time.strftime('%d/%m %H:%M', time.localtime(ultima))}."]
    lineas += [f"- {k}: {n} notas" for k, n in c.most_common(14)]
    lineas.append("Las notas relevantes para cada mensaje te llegan solas abajo; si no bastan, busca más con cerebro_buscar o notas_leer.")
    with _lock:
        _m["mapa"] = "\n".join(lineas)
        _m["estado"] = {"notas": len(principales), "fuentes": len(todas) - len(principales), "indexadas": len((buscador._indice["datos"] or chat.leer(buscador.F_INDICE, {"archivos": {}}))["archivos"]),
                        "trozos": len(_m["meta"]), "ultima": ultima, "hoy": hoy, "temas": dict(c.most_common()), "comprobado": time.time()}


def _bm25(q, top=20):
    b = _m["bm25"]; k1, bb = 1.5, 0.75
    pts = defaultdict(float)
    for w in set(_tok(q)):
        idf = b["idf"].get(w)
        if not idf:
            continue
        for i, c in b["post"][w]:
            L = b["largos"][i]
            pts[i] += idf * c * (k1 + 1) / (c + k1 * (1 - bb + bb * L / b["media"]))
    return [i for i, _ in sorted(pts.items(), key=lambda x: -x[1])[:top]]


def _vector(q, top=20):
    v = buscador.embeber([q[:2000]])[0]  # Mac: embeddings con Ollama (bge-m3-sony)
    v = np.asarray(v, dtype=np.float32); v /= (np.linalg.norm(v) or 1.0)
    buscador._uso["t"] = time.time()
    s = _m["mat"] @ v
    orden = list(np.argsort(-s)[:top])
    _m["ult_puntos"] = {int(i): float(s[i]) for i in orden}
    return orden


def recuperar(texto, notas=4, caracteres=450):
    """Devuelve (texto_para_el_contexto, lista_de_notas_usadas, ms)."""
    t0 = time.perf_counter()
    if _m["mat"] is None:
        _construir()
    if not _m["meta"] or len(texto.strip()) < 4:
        return "", [], 0
    try:
        vec = _vector(texto)
    except Exception:
        vec = []
    lex = _bm25(texto)
    rrf = defaultdict(float)
    for lista in (vec, lex):
        for r, i in enumerate(lista):
            rrf[int(i)] += 1 / (60 + r)
    vistas, usadas, partes = set(), [], []
    puntos = _m.get("ult_puntos", {}) if vec else {}
    ambos = set(int(i) for i in vec) & set(int(i) for i in lex[:10])
    for i, _ in sorted(rrf.items(), key=lambda x: -x[1]):
        if vec and puntos.get(i, 0) < 0.48 and i not in ambos:  # umbral: si no se parece de verdad, no se mete (evita ruido)
            continue
        rel, titulo, trozo = _m["meta"][i]
        if rel in vistas:
            continue
        # Las ~1.200 fichas de skills ya las tiene Sony en su índice: solo entran si de verdad encajan mucho (evita ruido).
        if rel.startswith("skills") and "skill" not in texto.lower() and puntos.get(i, 0) < 0.62:
            continue
        vistas.add(rel)
        cuerpo = re.sub(r"\s+", " ", trozo.split("\n", 1)[-1]).strip()[:caracteres]
        partes.append(f"[{rel}] {titulo}: {cuerpo}")
        usadas.append({"ruta": rel.replace("\\", "/"), "titulo": titulo})
        if len(usadas) >= notas:
            break
    ms = round((time.perf_counter() - t0) * 1000)
    if not partes:
        return "", [], ms
    txt = ("NOTAS DE TU SEGUNDO CEREBRO RELEVANTES PARA ESTE MENSAJE (úsalas primero; si sacas un dato de una, cita su ruta entre corchetes; "
           "si no tienen que ver, ignóralas):\n" + "\n".join(partes))
    return txt, usadas, ms


def mapa():
    if not _m["mapa"]:
        _hacer_mapa()
    return _m["mapa"]


def mapa_estable():
    """Mapa sin hora ni contadores que cambien a cada nota (para no romper la caché del prompt): temas y tamaño aproximado."""
    if not _m["estado"]:
        _hacer_mapa()
    e = _m["estado"]
    temas = ", ".join(f"{k} (~{(n // 10) * 10 or n})" for k, n in list(e.get("temas", {}).items())[:14])
    return (f"TU SEGUNDO CEREBRO (~/segundo-cerebro, ~{(e.get('notas', 0) // 100) * 100} notas). Temas: {temas}. "
            "En cada mensaje te llegan solas las notas relevantes; si no bastan, busca con cerebro_buscar o notas_leer.")


def reindexar_nota(ruta=None):
    """Tras guardar una nota: reindexa lo que haya cambiado (solo esas) y rehace las estructuras."""
    total, nuevas = buscador.indexar()
    if nuevas or _m["mat"] is None:
        _construir()
    else:
        _hacer_mapa()
    _m["t_ultima"] = time.time()
    return total, nuevas


def _vigilar():
    time.sleep(20)
    try:
        _construir()
    except Exception as e:
        chat_log = getattr(chat, "log", None)
    while True:
        try:
            firma = max((f.stat().st_mtime for f in buscador.notas()), default=0)
            if firma > _m.get("firma", 0):
                reindexar_nota()  # también al arrancar: así entran las notas creadas con el panel apagado
                _m["firma"] = firma
        except Exception:
            pass
        time.sleep(30)


def api_estado(h):
    if not _m["estado"]:
        _hacer_mapa()
    e = dict(_m["estado"]); e["al_dia"] = e.get("indexadas", 0) >= e.get("notas", 0)
    h.send(200, e)


def api_nota(h):  # ver una nota en texto (para el «🧠 usé: …»). Solo dentro de ~/segundo-cerebro.
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "No disponible"})
    ruta = urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query).get("ruta", [""])[0]
    f = (CEREBRO / ruta).resolve()
    if CEREBRO.resolve() not in f.parents or f.suffix != ".md" or not f.exists():
        return h.send(404, {"error": "no existe"})
    h.send(200, f.read_text(encoding="utf-8", errors="replace"), "text/plain; charset=utf-8")


def register(R):
    R[("GET", "/api/cerebro/estado")] = api_estado
    R[("GET", "/api/cerebro/nota")] = api_nota
    threading.Thread(target=_vigilar, daemon=True, name="cerebro-vigilancia").start()
