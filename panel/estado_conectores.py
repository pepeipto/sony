# Estado REAL de los conectores de Sony (15/11/2026). Nada de textos fijos.
# Cada comprobación es ligera y de SOLO LECTURA: no envía, no publica, no carga modelos ni usa la gráfica.
# Se comprueba al abrir Ajustes → Conectores, cada pocos minutos mientras está abierta, y al guardar una clave o usar un conector.
# El resultado se guarda en estado_conectores.json y Sony lo lee en su manual (agente.manual()).
import json, subprocess, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chat

F = Path(__file__).with_name("estado_conectores.json")
_lock = threading.Lock()
OK, ERR, NO = "ok", "error", "sin_configurar"


def _url(u, t=3):
    with urllib.request.urlopen(u, timeout=t) as r:
        return r.read()


def c_modelo():
    e = chat.estado()
    nombres = {"rapido": "Qwen 27B (local)", "haiku": "Claude Haiku 5.5 (API)", "sonnet": "Claude Sonnet 5.5 (API)"}
    if e.get("modelo"):
        return OK, f"{nombres.get(e['modelo'], e['modelo'])} cargado ({e.get('estado')})"
    return OK, "Ninguno cargado ahora: se carga solo cuando escribes"


def c_gpu():
    r = subprocess.run(["nvidia-smi", "--query-gpu=power.limit,memory.used,temperature.gpu", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, timeout=10, creationflags=0x08000000)
    if r.returncode != 0 or "lost" in r.stdout.lower():
        return ERR, "La gráfica no responde"
    lim, mem, t = [float(x) for x in r.stdout.strip().split(",")]
    import vigilancia_gpu
    return (OK if lim <= vigilancia_gpu.LIMITE_OBJETIVO_W + 10 else ERR), f"Límite {lim:.0f} W · {mem / 1024:.1f} GB de VRAM en uso · {t:.0f} °C"


def c_cerebro():
    import cerebro_rag
    if not cerebro_rag._m["estado"]:
        cerebro_rag._hacer_mapa()
    e = cerebro_rag._m["estado"]
    al_dia = e.get("indexadas", 0) >= e.get("notas", 0)
    return OK, (f"Activo · {e['notas']} notas ({e['hoy']} cambiadas hoy) · índice {'al día' if al_dia else 'actualizándose'} · "
                f"última nota {time.strftime('%d/%m %H:%M', time.localtime(e['ultima']))}")


def c_google():
    import google_con, correo
    cuentas = google_con.cuentas_g()
    if not cuentas:
        return NO, "Falta conectar tu cuenta de Google"
    for c in [x["id"] for x in correo.CUENTAS_INICIALES]:
        google_con.t_calendario_ver({"cuenta": c, "dias": 1})
    return OK, f"{len(cuentas)} cuentas: Gmail, Drive, Calendario y Contactos"


def c_correo():
    import correo
    cs = correo.cuentas()
    cs = cs if isinstance(cs, list) else []
    con = [c.get("nombre") for c in cs if c.get("conectada")]
    if not con:
        return NO, f"Ninguna cuenta conectada todavía ({len(cs)} preparadas: falta su contraseña en Ajustes → Conectores)"
    return OK, " · ".join(con)


def c_ionos():
    import correo
    r = correo.t_buscar({"cuenta": "proyecto", "texto": ""})
    if "error" in str(r).lower() or "no " in str(r)[:20].lower():
        return ERR, f"Correo support@ (IONOS): {str(r)[:80]}"
    return OK, "Correo del proyecto conectado"


def c_github():
    import github_con
    try:
        r = github_con.t_repos({})
    except PermissionError:
        return NO, "Falta pegar tu token de GitHub en Ajustes → Conectores"
    n = str(r).count("tu-usuario/")
    return (OK, f"tu-usuario · {n} repositorios") if n else (ERR, str(r)[:100])


def c_govee():
    import govee
    if not govee.clave():
        return NO, "Falta la clave de la API (Ajustes → Conectores → Govee)"
    ds = govee.dispositivos(True)
    loc = sum(1 for d in ds if d["local"])
    return OK, f"{len(ds)} luces ({', '.join(d['nombre'] for d in ds)}) · {loc} en local (LAN)"


def c_telegram():
    import telegram_con
    c = telegram_con.conf()
    if not telegram_con.token():
        return NO, "Falta el token del bot"
    if not c.get("usuario_id"):
        return NO, "Falta emparejar tu Telegram"
    if telegram_con._estado.get("error"):
        return ERR, telegram_con._estado["error"]
    return OK, "Bot emparejado y escuchando" if telegram_con._estado.get("vivo") else "Bot emparejado (conectando…)"


def c_sai():
    import sai
    d = sai.leer()
    if not d:
        return ERR, "No veo el SAI (¿cable USB?)"
    return OK, f"Phasak PH 9230 · {d['pct']} % · {'EN BATERÍA' if d['en_bateria'] else 'en red'}"


def c_web():
    return OK, "Búsqueda por DuckDuckGo (en el Mac no hay SearXNG) · siempre con tarjeta"


def c_imagenes():
    import imagenes
    m = imagenes.COMFY_DIR / "ComfyUI" / "models" / "checkpoints" / "flux1-schnell-fp8.safetensors"
    if not m.exists():
        return NO, "Falta el modelo FLUX"
    return OK, "FLUX listo bajo demanda (descarga el chat ~1 min mientras genera, con tarjeta)"


def c_voz():
    try:
        d = json.loads(_url("http://127.0.0.1:8097/estado"))
        return OK, f"Voz local: oídos Whisper {'cargado' if d.get('whisper') else 'se carga al usarlo'} · boca Piper {'cargada' if d.get('piper') else 'se carga al usarla'}"
    except Exception:
        return OK, "Apagada ahora: se enciende sola al pulsar el micrófono"


def c_redes():
    import redes
    hay = [v["nombre"] for r, v in redes.REDES.items() if redes._token(r)[1]]
    if not hay:
        return NO, "Ninguna red conectada (Ajustes → Redes): X, LinkedIn, Reddit…"
    return OK, "Conectadas: " + ", ".join(hay) + " · siempre con tarjeta"


def c_camaras():
    import camaras
    try:
        u, p = camaras.credenciales()
    except Exception:
        u, p = None, None
    if not p:
        return NO, "Falta la contraseña del equipo de cámaras (la tiene la empresa instaladora)"
    return OK, "Contraseña guardada (16 cámaras Dahua) · ver en el menú «Cámaras»"


def c_tuya():
    return NO, "Falta que inicies sesión en tu cuenta de Tuya"


def c_whatsapp():
    return NO, "No instalado (la vía oficial es de pago de Meta)"


COMPROBACIONES = [  # id, nombre, función · en el Mac solo lo que existe (sin gráfica, luces, SAI, Telegram, cámaras, voz ni imágenes)
    ("modelo", "Modelo de chat", c_modelo), ("cerebro", "Segundo cerebro", c_cerebro),
    ("google", "Google (Gmail, Drive, Calendario, Contactos)", c_google), ("correo", "Correo", c_correo),
    ("github", "GitHub", c_github), ("web", "Búsqueda web", c_web), ("redes", "Redes sociales", c_redes),
]


def _uno(item):
    cid, nombre, f = item
    t0 = time.time()
    try:
        est, det = f()
    except Exception as e:
        est, det = ERR, f"{type(e).__name__}: {str(e)[:120]}"
    return {"id": cid, "nombre": nombre, "estado": est, "detalle": det, "ms": round((time.time() - t0) * 1000)}


def comprobar(solo=None):
    with _lock:
        prev = chat.leer(F, {"conectores": [], "t": 0})
        items = [c for c in COMPROBACIONES if not solo or c[0] in solo]
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(_uno, items))
        hora = time.time()
        for r in res:
            r["t"] = hora
        actual = {c["id"]: c for c in prev.get("conectores", [])}
        actual.update({r["id"]: r for r in res})
        orden = [c[0] for c in COMPROBACIONES]
        datos = {"t": hora, "conectores": [actual[i] for i in orden if i in actual]}
        chat.escribir(F, datos)
        return datos


def leer(max_edad=180):
    d = chat.leer(F, {"conectores": [], "t": 0})
    if time.time() - d.get("t", 0) > max_edad:
        d = comprobar()
    return d


def resumen_para_sony():
    d = chat.leer(F, {"conectores": [], "t": 0})
    if not d["conectores"]:
        return ""
    sim = {OK: "✅", ERR: "⚠️", NO: "⏸"}
    return (f"ESTADO REAL DE TUS CONECTORES (comprobado a las {time.strftime('%H:%M', time.localtime(d['t']))}):\n" +
            "\n".join(f"{sim.get(c['estado'], '?')} {c['nombre']}: {c['detalle']}" for c in d["conectores"]))


def api(h):
    from urllib.parse import urlparse, parse_qs
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no permitido"})
    q = parse_qs(urlparse(h.path).query)
    h.send(200, comprobar(q["solo"][0].split(",") if q.get("solo") else None) if q.get("forzar") else leer())


def _vigilar():
    time.sleep(40)
    while True:
        try:
            comprobar()
        except Exception:
            pass
        time.sleep(600)  # cada 10 min en segundo plano (ligero, sin modelos), para que Sony siempre lea algo reciente


def register(R):
    R[("GET", "/api/conectores/estado")] = api
    threading.Thread(target=_vigilar, daemon=True, name="conectores").start()
