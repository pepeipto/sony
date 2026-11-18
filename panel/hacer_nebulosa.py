# Construye el grafo de la nebulosa del segundo cerebro (solo lectura de ~/segundo-cerebro).
# Python 3.12 stdlib. Uso directo:  python hacer_nebulosa.py   -> imprime estadisticas.
#
# ORDEN_FIJO: orden estable de las constelaciones. Cada tema toma el tono de su posicion en
# PALETA (12 tonos). Los temas que no esten aqui van detras (orden alfabetico) y toman el
# siguiente tono libre. Para "congelar" un tema nuevo, anadelo al final de esta lista.
import hashlib, math, os, re, time
from pathlib import Path

import compat
RAIZ = compat.CEREBRO
EXCLUIR = {"_fuentes", "_herramientas"}

ORDEN_FIJO = [
    "indice", "decisiones", "hardware", "modelos", "software", "proyectos",
    "skills", "problemas", "negocio", "personas-y-preferencias",
]

# 12 tonos moderados (suaves, poco saturados) pensados para fondo oscuro.
PALETA = [
    "#d9a184",  # terracota suave
    "#d6bf8a",  # arena
    "#9fc08f",  # salvia
    "#8fb0d0",  # azul niebla
    "#ae9fd2",  # lavanda
    "#d49cb0",  # rosa polvo
    "#86c0b6",  # turquesa apagado
    "#c9b06e",  # ocre claro
    "#b994b8",  # malva
    "#b9bd7e",  # oliva claro
    "#84a7bd",  # acero
    "#dca08f",  # coral apagado
]

NOMBRES = {
    "indice": "Índice", "decisiones": "Decisiones", "hardware": "Hardware", "modelos": "Modelos",
    "software": "Software", "proyectos": "Proyectos", "skills": "Skills", "problemas": "Problemas",
    "negocio": "Negocio", "personas-y-preferencias": "Personas y preferencias",
}

RE_WIKI = re.compile(r"\[\[([^\]\|#\n]+)(?:#[^\]\|\n]*)?(?:\|[^\]\n]*)?\]\]")
GOLDEN = math.pi * (3 - math.sqrt(5))


# ---------------------------------------------------------------- lectura de notas
def _valor(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        partes = [p.strip() for p in re.findall(r'"[^"]*"|\'[^\']*\'|[^,]+', v[1:-1])]
        return [_valor(p) for p in partes if p.strip()]
    return v


def frontmatter(texto):
    """YAML simple: clave: valor, listas [a, b] o con guiones. Devuelve (dict, cuerpo)."""
    if not texto.startswith("---"):
        return {}, texto
    fin = texto.find("\n---", 3)
    if fin < 0:
        return {}, texto
    cab, cuerpo = texto[3:fin], texto[fin + 4:]
    cuerpo = cuerpo.split("\n", 1)[1] if "\n" in cuerpo else ""
    datos, clave = {}, None
    for linea in cab.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", linea)
        if m:
            clave = m.group(1).lower()
            datos[clave] = _valor(m.group(2)) if m.group(2).strip() else []
        elif clave and linea.strip().startswith("- "):
            if not isinstance(datos.get(clave), list):
                datos[clave] = []
            datos[clave].append(_valor(linea.strip()[2:]))
    return datos, cuerpo


def _lista(v):
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return [s.strip() for s in str(v).split(",") if s.strip()] if v else []


def archivos():
    for base, dirs, files in os.walk(RAIZ):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUIR and not d.startswith("."))
        for f in sorted(files):
            if f.lower().endswith(".md"):
                yield Path(base) / f


def firma():
    n, mt = 0, 0.0
    for p in archivos():
        n += 1
        try:
            mt = max(mt, p.stat().st_mtime)
        except OSError:
            pass
    return (n, mt)


def extracto(cuerpo, titulo, max_lineas=10, max_chars=900):
    out, total, en_codigo = [], 0, False
    for linea in cuerpo.splitlines():
        s = linea.rstrip()
        if s.strip().startswith("```"):
            en_codigo = not en_codigo
            continue
        if not s.strip():
            continue
        limpio = s.lstrip("# ").strip() if s.lstrip().startswith("#") else s.strip()
        if not out and limpio == titulo:
            continue
        limpio = RE_WIKI.sub(lambda m: m.group(1).strip(), limpio)
        out.append(limpio[:300])
        total += len(limpio)
        if len(out) >= max_lineas or total >= max_chars:
            break
    return out


# ---------------------------------------------------------------- utilidades de layout
def rnd(*claves):
    h = hashlib.blake2b("|".join(map(str, claves)).encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / 2 ** 64


def empaquetar(radios, gap=8.0, iters=400):
    """Empaqueta circulos (en orden dado) alrededor del origen. Determinista."""
    n = len(radios)
    if n == 0:
        return [], 0.0
    if n == 1:
        return [(0.0, 0.0)], radios[0]
    escala = max(radios) * 1.2
    pos = []
    for i in range(n):
        d = 0 if i == 0 else escala * math.sqrt(i) * 1.1
        pos.append([d * math.cos(i * GOLDEN), d * math.sin(i * GOLDEN)])
    for it in range(iters):
        for i in range(n):  # atraccion suave al centro
            f = 0.04 * (1 - it / iters)
            pos[i][0] -= pos[i][0] * f
            pos[i][1] -= pos[i][1] * f
        for i in range(n):
            for j in range(i + 1, n):
                dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                d = math.hypot(dx, dy) or 1e-6
                m = radios[i] + radios[j] + gap
                if d < m:
                    emp = (m - d) / 2
                    ux, uy = dx / d, dy / d
                    wi = radios[j] / (radios[i] + radios[j])
                    wj = 1 - wi
                    pos[i][0] -= ux * emp * 2 * wi; pos[i][1] -= uy * emp * 2 * wi
                    pos[j][0] += ux * emp * 2 * wj; pos[j][1] += uy * emp * 2 * wj
    # centrar
    cx = sum(p[0] for p in pos) / n; cy = sum(p[1] for p in pos) / n
    pos = [(p[0] - cx, p[1] - cy) for p in pos]
    R = max(math.hypot(*p) + r for p, r in zip(pos, radios))
    return pos, R


# ---------------------------------------------------------------- construccion
def construir():
    t0 = time.time()
    notas, por_nombre, usados = [], {}, set()
    for p in archivos():
        try:
            texto = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        fm, cuerpo = frontmatter(texto)
        rel = p.relative_to(RAIZ)
        carpetas = rel.parts[:-1]
        tema = str(fm.get("tema") or (carpetas[0] if carpetas else "raiz")).strip().lower() or "raiz"
        titulo = str(fm.get("titulo") or "").strip()
        if not titulo:
            m = re.search(r"^#\s+(.+)$", cuerpo, re.M)
            titulo = m.group(1).strip() if m else p.stem
        sub = carpetas[1] if len(carpetas) > 1 else ""
        nota = {
            "id": p.stem, "titulo": titulo, "tema": tema, "tipo": str(fm.get("tipo") or ""),
            "tags": _lista(fm.get("tags")), "aliases": _lista(fm.get("aliases")),
            "ruta": str(rel).replace("\\", "/"), "sub": sub,
            "_m": int(p.stat().st_mtime),
            "_enl": [m.group(1).strip() for m in RE_WIKI.finditer(cuerpo)],
            "_ext": extracto(cuerpo, titulo),
        }
        # ids unicos aunque se repita el nombre de archivo en otra carpeta
        base_id, k = nota["id"], 2
        while nota["id"] in usados:
            nota["id"] = f"{base_id}~{k}"; k += 1
        usados.add(nota["id"])
        notas.append(nota)
        por_nombre.setdefault(p.stem.lower(), len(notas) - 1)
    for i, n in enumerate(notas):  # alias despues: el nombre de archivo tiene prioridad
        for a in n["aliases"]:
            por_nombre.setdefault(a.strip().lower(), i)

    aristas, vistos = [], set()
    vecinos = [set() for _ in notas]
    rotos = 0
    for i, n in enumerate(notas):
        for destino in n["_enl"]:
            j = por_nombre.get(destino.lower())
            if j is None:
                j = por_nombre.get(destino.lower().rsplit("/", 1)[-1])
            if j is None:
                rotos += 1; continue
            if j == i:
                continue
            clave = (min(i, j), max(i, j))
            if clave not in vistos:
                vistos.add(clave); aristas.append([i, j])
            vecinos[i].add(j); vecinos[j].add(i)

    # temas en orden fijo + nuevos detras
    presentes = {n["tema"] for n in notas}
    orden = [t for t in ORDEN_FIJO if t in presentes] + sorted(presentes - set(ORDEN_FIJO))
    todos = ORDEN_FIJO + sorted(presentes - set(ORDEN_FIJO))
    temas = []
    for t in orden:
        idx = todos.index(t)
        temas.append({"id": t, "nombre": NOMBRES.get(t, t.replace("-", " ").capitalize()),
                      "color": PALETA[idx % len(PALETA)], "n": sum(1 for n in notas if n["tema"] == t)})
    tidx = {t["id"]: k for k, t in enumerate(temas)}

    grado = [len(v) for v in vecinos]
    layout_nebulosa(notas, temas, grado)
    layout_espiral(notas, temas, grado)

    nodos = []
    for i, n in enumerate(notas):
        nodos.append({"id": n["id"], "t": n["titulo"], "c": tidx[n["tema"]], "g": grado[i],
                      "x": round(n["_x"], 1), "y": round(n["_y"], 1),
                      "sx": round(n["_sx"], 1), "sy": round(n["_sy"], 1), "s": n["sub"], "m": n.get("_m", 0)})
    for t in temas:
        t["halos"] = t.pop("_halos", [])
        t["cx"], t["cy"] = round(t.pop("_cx"), 1), round(t.pop("_cy"), 1)
        t["r"] = round(t.pop("_r"), 1)
    detalles = {n["id"]: {"titulo": n["titulo"], "tipo": n["tipo"], "tema": n["tema"], "tags": n["tags"],
                          "aliases": n["aliases"], "ruta": n["ruta"], "extracto": n["_ext"],
                          "vecinos": sorted(vecinos[i], key=lambda j: -grado[j])}
                for i, n in enumerate(notas)}
    grafo = {"nodos": nodos, "aristas": aristas, "temas": temas,
             "stats": {"notas": len(nodos), "enlaces": len(aristas), "temas": len(temas),
                       "rotos": rotos, "ms": int((time.time() - t0) * 1000), "generado": int(time.time())}}
    return grafo, detalles


def layout_nebulosa(notas, temas, grado):
    PASO = 11.0
    for t in temas:
        miembros = [i for i, n in enumerate(notas) if n["tema"] == t["id"]]
        grupos = {}
        for i in miembros:
            grupos.setdefault(notas[i]["sub"], []).append(i)
        claves = sorted(grupos, key=lambda k: (-len(grupos[k]), k))
        radios = [PASO * math.sqrt(len(grupos[k])) * 1.05 + 10 for k in claves]
        pos, R = empaquetar(radios, gap=PASO * 1.4)
        t["_grupos"] = [(k, grupos[k], p, r) for k, p, r in zip(claves, pos, radios)]
        t["_R"] = R
    centros, _ = empaquetar([t["_R"] + 30 for t in temas], gap=60)
    for t, (cx, cy) in zip(temas, centros):
        t["_cx"], t["_cy"], t["_r"] = cx, cy, t["_R"]
        halos = []
        for k, miembros, (gx, gy), r in t.pop("_grupos"):
            miembros.sort(key=lambda i: (-grado[i], notas[i]["id"]))
            gx += cx; gy += cy
            rot = rnd(t["id"], k) * math.tau
            for m, i in enumerate(miembros):
                d = PASO * math.sqrt(m + 0.6) * (0.85 + 0.3 * rnd(notas[i]["id"], "d"))
                a = m * GOLDEN + rot + (rnd(notas[i]["id"], "a") - 0.5) * 0.5
                notas[i]["_x"] = gx + d * math.cos(a)
                notas[i]["_y"] = gy + d * math.sin(a)
            halos.append([round(gx, 1), round(gy, 1), round(r * 1.5 + 20, 1), len(miembros)])
        t["_halos"] = halos
        del t["_R"]


def layout_espiral(notas, temas, grado):
    # Los temas, en orden fijo, se colocan seguidos a lo largo de BRAZOS brazos: cada tema
    # ocupa un tramo contiguo (los grandes se reparten entre varios brazos). Los temas
    # pequenos reciben un tramo minimo para que se vean como un cumulo propio.
    BRAZOS, MINIMO, B = 4, 40, 0.30
    cola = []  # (tema, indices de nota, peso)
    for t in temas:
        miembros = sorted((i for i, n in enumerate(notas) if n["tema"] == t["id"]),
                          key=lambda i: (-grado[i], notas[i]["id"]))
        cola.append((t, miembros, max(len(miembros), MINIMO)))
    total = sum(p for _, _, p in cola) or 1
    por_brazo = total / BRAZOS
    TH0, THMAX = 0.5, 2.15 * math.pi
    acum = 0.0
    for t, miembros, peso in cola:
        n = len(miembros)
        anclas = []
        for m, i in enumerate(miembros):
            g = acum + (m + 0.5) / max(n, 1) * peso  # posicion global en la cola
            brazo = min(BRAZOS - 1, int(g // por_brazo))
            f = (g - brazo * por_brazo) / por_brazo  # 0..1 dentro del brazo
            th = TH0 + f * THMAX
            r = 70 * math.exp(B * th)
            ancho = 8 + r * 0.075
            g1 = rnd(notas[i]["id"], "e1"); g2 = rnd(notas[i]["id"], "e2")
            disp = math.sqrt(-2 * math.log(max(g1, 1e-9))) * math.cos(math.tau * g2)
            ang = brazo / BRAZOS * math.tau + th
            rr = r + disp * ancho
            x = rr * math.cos(ang) + (rnd(notas[i]["id"], "jx") - .5) * ancho * .7
            y = rr * math.sin(ang) + (rnd(notas[i]["id"], "jy") - .5) * ancho * .7
            notas[i]["_sx"], notas[i]["_sy"] = x, y
            if m == n // 2:
                anclas = [round(x, 1), round(y, 1)]
        t["ancla"] = anclas
        acum += peso


if __name__ == "__main__":
    g, _ = construir()
    print(g["stats"])
    for t in g["temas"]:
        print(f'  {t["color"]}  {t["n"]:5d}  {t["id"]}')
