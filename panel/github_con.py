# Conector de GitHub para Sony (usuario tu-usuario). Token de acceso detallado (fine-grained) que pega el usuario;
# se guarda cifrado en el Administrador de credenciales de Windows y nunca se escribe en archivos ni registros.
import base64, json, urllib.parse, urllib.request

import chat
import correo

API = "https://api.github.com"


def token():
    return correo.cred_leer("github-token")[1]


def gh(metodo, ruta, datos=None):
    t = token()
    if not t:
        raise PermissionError("GitHub no está conectado. El usuario tiene que pegar su token en Ajustes → Conectores → GitHub.")
    req = urllib.request.Request(API + ruta, data=None if datos is None else json.dumps(datos).encode(), method=metodo,
                                 headers={"Authorization": "Bearer " + t, "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Sony-IA-de-el usuario"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
    return json.loads(b) if b else {}


def t_repos(a):
    r = gh("GET", "/user/repos?per_page=50&sort=updated")
    return "\n".join(f"{x['full_name']} · {'privado' if x['private'] else 'público'} · {x.get('description') or ''}" for x in r) or "Sin repos."


def t_leer(a):
    ruta = urllib.parse.quote(a.get("ruta", "").lstrip("/"))
    r = gh("GET", f"/repos/{a['repo']}/contents/{ruta}" + (f"?ref={urllib.parse.quote(a['rama'])}" if a.get("rama") else ""))
    if isinstance(r, list):
        return "\n".join(("📁 " if x["type"] == "dir" else "📄 ") + x["path"] for x in r)
    if r.get("encoding") == "base64":
        return base64.b64decode(r["content"]).decode("utf-8", "replace")[:15000]
    return "No se puede leer como texto."


def t_issues(a):
    r = gh("GET", f"/repos/{a['repo']}/issues?state={a.get('estado') or 'open'}&per_page=30")
    return "\n".join(f"#{x['number']} {'[PR] ' if 'pull_request' in x else ''}{x['title']} · {x['user']['login']}" for x in r) or "Nada abierto."


def t_issue_leer(a):  # 15/11: detalle de una issue/PR (solo lectura)
    n = int(str(a.get("numero")).lstrip("#"))
    x = gh("GET", f"/repos/{a['repo']}/issues/{n}")
    com = gh("GET", f"/repos/{a['repo']}/issues/{n}/comments?per_page=10")
    out = f"#{x['number']} {x['title']} · {x['state']} · {x['user']['login']} · {x['created_at'][:10]}\n\n{(x.get('body') or '(sin texto)')[:6000]}"
    for c in com:
        out += f"\n\n— {c['user']['login']} ({c['created_at'][:10]}): {(c.get('body') or '')[:1500]}"
    return out


def t_crear_issue(a):
    r = gh("POST", f"/repos/{a['repo']}/issues", {"title": a["titulo"], "body": a.get("texto", "")})
    return f"Issue creada: #{r['number']} {r['html_url']}"


def t_comentar(a):
    r = gh("POST", f"/repos/{a['repo']}/issues/{a['numero']}/comments", {"body": a["texto"]})
    return f"Comentario publicado: {r['html_url']}"


HERRAMIENTAS = {
    "github_repos": (t_repos, False, "Ver tus repositorios de GitHub", {}, "Lista los repositorios de GitHub del usuario."),
    "github_leer": (t_leer, False, "Leer un archivo o carpeta de GitHub", {"repo": "string", "ruta": "string", "rama": "string"},
                    "Lee un archivo o lista una carpeta de un repo (repo = usuario/nombre)."),
    "github_issues": (t_issues, False, "Ver issues y PRs", {"repo": "string", "estado": "string"}, "Lista issues y pull requests de un repo."),
    "github_issue_leer": (t_issue_leer, False, "Leer una issue o PR", {"repo": "string", "numero": "integer"}, "Lee el texto completo y los comentarios de una issue o PR (repo = usuario/nombre, numero = 116). Úsala en vez de ejecutar o la web."),
    "github_crear_issue": (t_crear_issue, True, "Crear una issue en GitHub", {"repo": "string", "titulo": "string", "texto": "string"}, "Crea una issue nueva."),
    "github_comentar": (t_comentar, True, "Publicar un comentario en GitHub", {"repo": "string", "numero": "integer", "texto": "string"},
                        "Publica un comentario en una issue o PR."),
}


def api_estado(h):
    t = token()
    if not t:
        return h.send(200, {"conectado": False})
    try:
        u = gh("GET", "/user")
        return h.send(200, {"conectado": True, "usuario": u.get("login")})
    except Exception as e:
        return h.send(200, {"conectado": False, "error": f"El token no funciona: {e}"})


def api_token(h):
    d = chat.leer_cuerpo(h); t = (d.get("token") or "").strip()
    if not t.startswith(("github_pat_", "ghp_")):
        return h.send(400, {"error": "Eso no parece un token de GitHub (empieza por github_pat_)."})
    correo.cred_guardar("github-token", "github", t)
    try:
        u = gh("GET", "/user")
    except Exception:
        correo.cred_borrar("github-token")
        return h.send(200, {"ok": False, "mensaje": "GitHub ha rechazado el token."})
    h.send(200, {"ok": True, "mensaje": f"GitHub conectado como {u.get('login')}"})


# ---------- inicio de sesión con el navegador (flujo de dispositivo oficial de GitHub CLI) ----------
import os, re, subprocess, threading
from pathlib import Path
import shutil, webbrowser
GH = shutil.which("gh") or "/opt/homebrew/bin/gh"
_disp = {"estado": "inactivo", "codigo": None, "mensaje": ""}


def _login_dispositivo():
    env = {**os.environ, "GH_NO_UPDATE_NOTIFIER": "1", "GH_BROWSER": "open"}
    p = subprocess.Popen([GH, "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    try:
        for linea in p.stdout:
            m = re.search(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b", linea)
            if m and not _disp["codigo"]:
                _disp.update(codigo=m.group(1), estado="esperando")
                webbrowser.open("https://github.com/login/device")
                try:
                    p.stdin.write("\n"); p.stdin.flush()
                except Exception:
                    pass
        p.wait(timeout=900)
    except Exception:
        p.kill()
    tok = subprocess.run([GH, "auth", "token", "--hostname", "github.com"], capture_output=True, text=True).stdout.strip()
    if tok:
        correo.cred_guardar("github-token", "github", tok)
        try:
            _disp.update(estado="listo", mensaje=f"GitHub conectado como {gh('GET', '/user').get('login')}")
        except Exception:
            _disp.update(estado="listo", mensaje="GitHub conectado")
    else:
        _disp.update(estado="error", mensaje="No se completó la autorización en GitHub.")
    _disp["codigo"] = None


def api_dispositivo(h):
    if h.command == "POST":
        if _disp["estado"] != "esperando":
            _disp.update(estado="iniciando", codigo=None, mensaje="")
            threading.Thread(target=_login_dispositivo, daemon=True).start()
        for _ in range(60):
            if _disp["codigo"] or _disp["estado"] in ("error", "listo"):
                break
            __import__("time").sleep(0.25)
    h.send(200, dict(_disp))


def api_desconectar(h):
    correo.cred_borrar("github-token"); h.send(200, {"ok": True})


def register(R):
    R[("GET", "/api/github/estado")] = api_estado
    R[("POST", "/api/github/token")] = api_token
    R[("POST", "/api/github/desconectar")] = api_desconectar
    R[("POST", "/api/github/dispositivo")] = api_dispositivo
    R[("GET", "/api/github/dispositivo")] = api_dispositivo
