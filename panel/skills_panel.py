# Pestaña «Skills» de Ajustes (15/11/2026): lista real de ~/IA\hermes\skills, buscador, activar/desactivar y «Modo automático».
# - Modo automático (por defecto, encendido): Sony elige y lee sola la skill que encaje.
# - Apagado: Sony solo usa una skill cuando el usuario se lo pide.
# - Desactivada: no sale en el índice de Sony.
import re, urllib.parse
from pathlib import Path

import chat

import compat
SKILLS = compat.SKILLS
F = Path(__file__).with_name("skills_ajustes.json")


def conf():
    return chat.leer(F, {"auto": True, "desactivadas": []})


def lista():
    """Lee INDICE.md (nombre, para qué sirve, categoría, estado de prueba) y marca las desactivadas."""
    c = conf(); out = []; cat = "General"
    try:
        lineas = (SKILLS / "INDICE.md").read_text(encoding="utf-8").splitlines()
    except Exception:
        lineas = []
    for l in lineas:
        if l.startswith("## "):
            cat = l[3:].strip(); continue
        m = re.match(r"-\s+([a-z0-9-]+):\s*(.*)", l)
        if not m:
            continue
        nombre, desc = m.group(1), m.group(2).strip()
        pendiente = "[pendiente de prueba]" in desc or "pendiente" in cat.lower()
        out.append({"nombre": nombre, "desc": desc.replace("[pendiente de prueba]", "").strip(), "categoria": cat,
                    "prueba": "pendiente de prueba" if pendiente else "probada", "activa": nombre not in c["desactivadas"]})
    return out


def indice_para_sony():
    c = conf(); ls = [s for s in lista() if s["activa"]]
    cab = ("Modo automático ENCENDIDO: cuando una tarea encaje con una skill, léela tú sola con skill_leer y síguela (di en una línea cuál usas)."
           if c.get("auto", True) else
           "Modo automático APAGADO: usa una skill SOLO cuando el usuario te lo pida (por su nombre o su tema). Si crees que una ayudaría, propónsela en una línea.")
    grupos = {}
    for s in ls:
        d = re.sub(r"^(When|Use when|Use this skill when)( the user| you)? (wants?|needs?|asks?)( to| for)? ", "", s["desc"]).strip()  # recorta el arranque inglés: el índice va en cada mensaje
        grupos.setdefault(s["categoria"], []).append(f"- {s['nombre']}: {d[:105]}")
    return cab + "\n" + "\n".join(f"## {k}\n" + "\n".join(v) for k, v in grupos.items())


def api_lista(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    ls = lista(); c = conf()
    h.send(200, {"auto": c.get("auto", True), "total": len(ls), "activas": sum(s["activa"] for s in ls), "skills": ls})


def api_config(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    d = chat.leer_cuerpo(h); c = conf()
    if "auto" in d:
        c["auto"] = bool(d["auto"])
    if d.get("nombre"):
        n = re.sub(r"[^a-z0-9-]", "", d["nombre"].lower())
        des = set(c["desactivadas"])
        (des.discard if d.get("activa") else des.add)(n)
        c["desactivadas"] = sorted(des)
    chat.escribir(F, c)
    h.send(200, {"ok": True, **c})


def api_ver(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    n = re.sub(r"[^a-z0-9-]", "", urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query).get("nombre", [""])[0].lower())
    cand = [p for p in SKILLS.rglob("SKILL.md") if p.parent.name.lower() == n]
    if not cand:
        return h.send(404, {"error": "no existe"})
    h.send(200, cand[0].read_text(encoding="utf-8", errors="replace"), "text/plain; charset=utf-8")


def register(R):
    R[("GET", "/api/skills")] = api_lista
    R[("POST", "/api/skills/config")] = api_config
    R[("GET", "/api/skills/ver")] = api_ver
