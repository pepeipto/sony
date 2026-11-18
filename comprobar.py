# Comprobación de salud de Sony. Úsala cuando algo no vaya o tras actualizar macOS/Homebrew:
#     ~/IA/sony/comprobar.sh            (no gasta nada, no cambia nada)
#     ~/IA/sony/comprobar.sh --api      (además hace una llamada mínima a Claude: menos de 1 céntimo)
# Cada línea dice qué está bien (✅), qué conviene mirar (⚠️) y qué impide funcionar (❌), con el arreglo.
import json, os, shutil, subprocess, sys, time
from pathlib import Path

H = Path.home(); SONY = H / "IA/sony"; PANEL = SONY / "panel"; CEREBRO = H / "segundo-cerebro"
sys.path.insert(0, str(PANEL))
mal = avisos = 0


def ok(t): print("✅", t)
def aviso(t, arreglo=""):
    global avisos; avisos += 1; print("⚠️ ", t + (f"\n     → {arreglo}" if arreglo else ""))
def error(t, arreglo=""):
    global mal; mal += 1; print("❌", t + (f"\n     → {arreglo}" if arreglo else ""))


print(f"Comprobación de Sony · {time.strftime('%d/%m/%Y %H:%M')}\n")

# 1. Python y librerías
print("— Programa —")
ok(f"Python {sys.version.split()[0]} ({sys.executable})")
for lib, uso in (("anthropic", "hablar con Claude"), ("numpy", "el buscador del segundo cerebro"), ("pypdf", "leer PDF")):
    try:
        m = __import__(lib); ok(f"Librería {lib} {getattr(m, '__version__', '')} ({uso})")
    except Exception as e:
        error(f"No carga la librería {lib} ({uso}): {type(e).__name__}", f"~/IA/sony/venv/bin/pip install {lib}")
try:
    import compat, chat, agente, claude_api, skills_panel, buscador
    R = {}
    fallan = []
    for mod in ("chat", "correo", "buscador", "google_con", "github_con", "agente", "programador", "claude_api", "redes", "skills_panel", "diario", "nebulosa", "cerebro_rag", "estado_conectores", "video"):
        try:
            __import__(mod)
        except Exception as e:
            fallan.append(f"{mod} ({type(e).__name__}: {str(e)[:60]})")
    (error("Módulos del panel que no cargan: " + ", ".join(fallan), "restaura la copia de ~/IA/sony/copias o del USB") if fallan else ok("Los 15 módulos del panel cargan"))
except Exception as e:
    error(f"El panel no carga: {type(e).__name__}: {e}", "restaura la copia de ~/IA/sony/copias o del USB"); print(f"\nResultado: {mal} errores"); sys.exit(1)

# 2. Lo que Sony lee siempre
print("\n— Lo que Sony lee en cada mensaje —")
lec = agente.lecciones(); n_lec = lec.count("\n- ")
(ok(f"{n_lec} lecciones cargadas") if n_lec >= 5 else error("Las lecciones no se cargan", f"revisa {CEREBRO}/sony/lecciones.md"))
(ok("Manual de capacidades cargado") if len(agente.manual()) > 500 else error("Falta el manual", f"revisa {PANEL}/manual_sony.md"))
ls = skills_panel.lista(); carp = {p.parent.name for p in compat.SKILLS.rglob("SKILL.md")}
sin = [s["nombre"] for s in ls if s["nombre"] not in carp]
(ok(f"{len(ls)} skills en el índice, todas con su carpeta") if not sin else aviso(f"Skills del índice sin carpeta: {', '.join(sin[:6])}", "bórralas de skills/INDICE.md o reinstálalas"))
fijo = len(agente.SISTEMA_AGENTE + agente.manual() + lec + agente.indice_skills())
(ok(f"Texto fijo de Sony: {fijo} caracteres") if fijo < 30000 else aviso(f"El texto fijo de Sony es muy largo ({fijo} caracteres): el Qwen local irá lento", "desactiva skills que no uses en Ajustes → Skills"))

# 3. Modelo local
print("\n— Modelo local (Qwen) —")
(ok(f"llama-server instalado ({compat.LLAMA})") if compat.LLAMA.exists() else error("Falta llama-server", "brew install llama.cpp"))
for k, m in chat.MODELOS.items():
    for campo in ("gguf", "mmproj"):
        f = m.get(campo)
        if f:
            (ok(f"{f.name} ({f.stat().st_size / 1e9:.1f} GB)") if f.exists() else error(f"Falta el archivo del modelo {f.name}", f"vuelve a descargarlo a {f.parent}"))
tot, disp = compat.memoria()
(ok(f"Memoria: {tot:.0f} GB, {disp:.0f} GB disponibles ahora") if disp >= chat.NECESITA_GB else aviso(f"Memoria disponible ahora: {disp:.0f} GB (el Qwen necesita unos {chat.NECESITA_GB:.0f})", "cierra apps pesadas antes de usar el Qwen; Haiku y Sonnet no usan memoria"))

# 4. Claude por API
print("\n— Claude por API —")
if claude_api.hay_clave():
    g = claude_api.gasto(); t = claude_api.tope()
    ok("Hay clave de la API en el Llavero")
    (ok(f"Gasto de {g['mes']}: {g['usd']:.2f} $ de {t:g} $ de tope") if not t or g["usd"] < t * 0.8 else aviso(f"Gasto de {g['mes']}: {g['usd']:.2f} $ de {t:g} $ (cerca del tope)", "súbelo en Ajustes → Modelo si lo necesitas"))
    if "--api" in sys.argv:
        for k in chat.CLAUDE:
            try:
                r = json.loads(claude_api.completar({"messages": [{"role": "user", "content": "Responde solo: ok"}], "max_tokens": 16}, chat.claude_id(k)).read())
                ok(f"{chat.claude_id(k)} responde: {r['choices'][0]['message']['content'][:20]!r}")
            except Exception as e:
                error(f"{chat.claude_id(k)} no responde: {str(e)[:150]}", "si dice que el modelo ya no existe, pon el nuevo en panel/ajustes.json → \"claude_ids\"")
    else:
        print("   (para probar la conexión real: ~/IA/sony/comprobar.sh --api)")
else:
    aviso("No hay clave de la API de Claude: Haiku, Sonnet y Automático no funcionan (el Qwen local sí)", "pégala en Ajustes → Modelo")

# 5. Segundo cerebro
print("\n— Segundo cerebro —")
if CEREBRO.exists():
    notas = [f for f in CEREBRO.rglob("*.md") if "/_fuentes/" not in str(f)]
    ok(f"{len(notas)} notas en {CEREBRO}")
    try:
        idx = json.loads((PANEL / "buscador/indice.json").read_text()).get("archivos", {})
        (ok(f"Índice de búsqueda al día ({len(idx)} notas)") if len(idx) >= len(notas) else aviso(f"El índice tiene {len(idx)} de {len(notas)} notas", "se pone al día solo al usar a Sony (puede tardar unos minutos)"))
    except Exception:
        aviso("No hay índice de búsqueda todavía", "se crea solo la primera vez que Sony busca (tarda unos minutos)")
    for f in ("bge-m3-Q8_0.gguf", "bge-reranker-v2-m3-Q8_0.gguf"):
        (ok(f"Modelo de búsqueda {f}") if (compat.MODELOS / "buscador" / f).exists() else error(f"Falta el modelo de búsqueda {f}", "vuelve a descargarlo a ~/IA/modelos/buscador"))
else:
    error("No existe el segundo cerebro", f"restaura {CEREBRO} desde la copia del USB")

# 6. Sistema
print("\n— Mac —")
libre = shutil.disk_usage(str(H)).free / 1e9
(ok(f"Disco: {libre:.0f} GB libres") if libre > 15 else aviso(f"Quedan {libre:.0f} GB de disco", "libera espacio"))
(ok("Google Chrome instalado") if Path("/Applications/Google Chrome.app").exists() else error("Falta Google Chrome (la ventana de Sony lo usa)", "instálalo desde google.com/chrome"))
(ok("App «IA Sony» en su sitio") if (H / "Applications/IA Sony.app/Contents/MacOS/ia-sony").exists() else error("Falta la app «IA Sony»", "restáurala desde la copia"))
grandes = [f"{f.name} ({f.stat().st_size / 1e6:.0f} MB)" for f in (H / "IA/logs").glob("*") if f.is_file() and f.stat().st_size > 20e6]
(aviso("Logs grandes: " + ", ".join(grandes), "se rotan solos al abrir Sony") if grandes else ok("Logs con tamaño normal"))

# 7. Copia de seguridad
print("\n— Copia de seguridad —")
r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/local.usuario.sony-copia"], capture_output=True, text=True)
(ok("Tarea de copia semanal cargada (sábados 04:00)") if r.returncode == 0 else aviso("La tarea de copia semanal no está cargada", "launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.usuario.sony-copia.plist"))
log = H / "IA/logs/copia-seguridad.log"
ultima = next((l for l in reversed(log.read_text().splitlines()) if " OK: " in l), None) if log.exists() else None
if ultima:
    dias = (time.time() - time.mktime(time.strptime(ultima[:19], "%Y-%m-%d %H:%M:%S"))) / 86400
    (ok(f"Última copia hace {dias:.0f} días ({ultima.split('OK: ')[1]})") if dias < 9 else aviso(f"La última copia buena es de hace {dias:.0f} días", "conecta el USB ESD-USB y ejecuta ~/IA/sony/copia-seguridad.sh"))
else:
    aviso("Todavía no hay ninguna copia de seguridad hecha", "conecta el USB y ejecuta ~/IA/sony/copia-seguridad.sh")

print(f"\nResultado: {mal} errores, {avisos} avisos." + (" Todo en orden." if not mal and not avisos else ""))
try:
    buscador.parar_todo()
except Exception:
    pass
sys.stdout.flush()
os._exit(1 if mal else 0)
