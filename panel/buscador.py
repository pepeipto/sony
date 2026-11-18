# Buscador semántico del segundo cerebro: embeddings (bge-m3) + reordenado (bge-reranker-v2-m3).
# Todo en el PROCESADOR (-ngl 0): 0 MB de VRAM, para no quitar nada a los modelos de la gráfica.
import json, math, re, socket, subprocess, threading, time, urllib.request
from pathlib import Path

import chat

import compat
CEREBRO = compat.CEREBRO
DIR = Path(__file__).resolve().parent / "buscador"; DIR.mkdir(exist_ok=True)
F_INDICE = DIR / "indice.json"
MOD = compat.MODELOS / "buscador"
LLAMA = compat.LLAMA
SERV = {
    "emb": {"puerto": 8091, "args": ["-m", str(MOD / "bge-m3-Q8_0.gguf"), "--embedding", "--pooling", "cls", "-c", "8192", "-ub", "8192", "-b", "8192"]},
    "rer": {"puerto": 8092, "args": ["-m", str(MOD / "bge-reranker-v2-m3-Q8_0.gguf"), "--reranking", "-c", "8192", "-ub", "8192", "-b", "8192"]},
}
HILOS = "8"  # deja la mitad del procesador libre
_proc, _uso, _lock = {}, {"t": 0.0}, threading.Lock()
_indice = {"datos": None}


def vivo(p):
    try:
        with socket.create_connection(("127.0.0.1", p), timeout=0.3):
            return True
    except OSError:
        return False


OLLAMA = "http://127.0.0.1:11434"; MODELO_EMB = "bge-m3-sony"  # Mac Studio: embeddings con Ollama (compartido)


def arrancar(k):
    """En el Mac no se lanza ningún llama-server: los embeddings los da Ollama. El reordenador (reranker) no está disponible."""
    _uso["t"] = time.time()


def parar_todo():
    with _lock:
        for k, p in list(_proc.items()):
            if p and p.poll() is None:
                p.terminate()
            _proc.pop(k, None)


def vigilante():
    while True:
        time.sleep(60)
        if _proc and time.time() - _uso["t"] > 600:  # 10 min sin uso: se apagan
            parar_todo()


def post(puerto, ruta, datos, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{puerto}{ruta}", data=json.dumps(datos).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / n, 5) for x in v]


def embeber(textos):
    out = []
    for i in range(0, len(textos), 16):
        req = urllib.request.Request(OLLAMA + "/api/embed", data=json.dumps({"model": MODELO_EMB, "input": textos[i:i + 16]}).encode(),
                                     headers={"Content-Type": "application/json"})
        out += [norm(v) for v in json.loads(urllib.request.urlopen(req, timeout=600).read())["embeddings"]]
        _uso["t"] = time.time()
    return out


def trozos(f):
    t = f.read_text(encoding="utf-8", errors="replace")
    titulo = re.search(r'^titulo:\s*"?(.*?)"?\s*$', t, re.M)
    titulo = titulo.group(1) if titulo else f.stem
    cuerpo = re.sub(r"^---.*?---\s*", "", t, flags=re.S)
    partes, actual = [], ""
    for linea in cuerpo.splitlines(True):
        if (linea.startswith("#") and len(actual) > 400) or len(actual) > 1400:
            partes.append(actual); actual = ""
        actual += linea
    if actual.strip():
        partes.append(actual)
    return titulo, [f"{titulo}\n{p.strip()}"[:1800] for p in partes if p.strip()]


def notas():
    return [f for f in CEREBRO.rglob("*.md") if "/_fuentes/" not in str(f) and "/_herramientas/" not in str(f)]


def indexar():
    idx = _indice["datos"] or chat.leer(F_INDICE, {"archivos": {}})
    actuales = {str(f.relative_to(CEREBRO)): f for f in notas()}
    cambios = 0
    for rel in list(idx["archivos"]):
        if rel not in actuales:
            del idx["archivos"][rel]; cambios += 1
    pendientes = [(rel, f) for rel, f in actuales.items()
                  if idx["archivos"].get(rel, {}).get("mtime") != f.stat().st_mtime]
    for n, (rel, f) in enumerate(pendientes):
        titulo, ts = trozos(f)
        vecs = embeber(ts) if ts else []
        idx["archivos"][rel] = {"mtime": f.stat().st_mtime, "titulo": titulo, "trozos": ts, "vec": vecs}
        cambios += 1
        if n % 100 == 99:
            chat.escribir(F_INDICE, idx)
    if cambios:
        chat.escribir(F_INDICE, idx)
    _indice["datos"] = idx
    return len(actuales), len(pendientes)


def buscar(texto, n=6):
    indexar()
    q = embeber([texto])[0]
    cand = []
    for rel, d in _indice["datos"]["archivos"].items():
        for t, v in zip(d["trozos"], d["vec"]):
            cand.append((sum(a * b for a, b in zip(q, v)), rel, d["titulo"], t))
    cand.sort(reverse=True); cand = cand[:15]
    try:
        raise RuntimeError("sin reordenador en el Mac")  # se usa el orden por similitud
        r = post(SERV["rer"]["puerto"], "/v1/rerank", {"query": texto, "documents": [c[3] for c in cand], "top_n": n})
        orden = [(x["relevance_score"], cand[x["index"]]) for x in r["results"]]
    except Exception:
        orden = [(c[0], c) for c in cand[:n]]
    _uso["t"] = time.time()
    return [{"nota": c[1], "titulo": c[2], "puntuacion": round(s, 3), "fragmento": c[3][:500]} for s, c in orden[:n]]


def t_cerebro_buscar(a):
    res = buscar(a["texto"])
    return "\n\n".join(f"[{r['nota']}] {r['titulo']} (relevancia {r['puntuacion']})\n{r['fragmento']}" for r in res) or "Nada relevante."


def api_buscar(h):
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(h.path).query).get("q", [""])[0]
    h.send(200, buscar(q) if q else [])


def api_indexar(h):
    t0 = time.time(); total, nuevos = indexar()
    h.send(200, {"notas": total, "indexadas_ahora": nuevos, "segundos": round(time.time() - t0, 1)})


def register(R):
    R[("GET", "/api/cerebro/buscar")] = api_buscar
    R[("POST", "/api/cerebro/indexar")] = api_indexar
    threading.Thread(target=vigilante, daemon=True).start()
