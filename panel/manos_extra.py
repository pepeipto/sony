# Manos ligeras de Sony (15/11/2026): recordatorios, el tiempo y liberar la gráfica.
# Todo lo que tiene efecto pide tarjeta (perm True). El tiempo es solo lectura (Open-Meteo, sin clave).
import datetime as dt, json, secrets, threading, time, urllib.parse, urllib.request
import privado

import programador

CODIGOS = {0: "despejado", 1: "casi despejado", 2: "nubes y claros", 3: "nublado", 45: "niebla", 48: "niebla", 51: "llovizna débil",
           53: "llovizna", 55: "llovizna fuerte", 61: "lluvia débil", 63: "lluvia", 65: "lluvia fuerte", 71: "nieve débil", 73: "nieve",
           75: "nieve fuerte", 80: "chubascos débiles", 81: "chubascos", 82: "chubascos fuertes", 95: "tormenta", 96: "tormenta con granizo", 99: "tormenta con granizo"}


def _sistema_recordatorio(t, est):  # tipo de tarea nuevo para el programador: solo avisa, sin modelo
    programador.notificar("⏰ " + t.get("nombre", "Recordatorio"), t.get("prompt", ""))
    return "hecho (aviso enviado)"


programador.SISTEMA["recordatorio"] = _sistema_recordatorio


def t_recordatorio(a):
    texto = (a.get("texto") or "").strip()
    fecha, hora = (a.get("fecha") or "").strip(), (a.get("hora") or "").strip()
    try:
        cuando = dt.datetime.fromisoformat(f"{fecha}T{hora}")
    except Exception:
        return "Fecha u hora no válidas: usa fecha AAAA-MM-DD y hora HH:MM."
    if cuando < dt.datetime.now():
        return "Esa hora ya ha pasado."
    if not texto:
        return "Falta el texto del recordatorio."
    with programador._lock:
        ts = programador.tareas()
        ts.append({"id": secrets.token_hex(5), "nombre": texto[:60], "tipo": "recordatorio", "repeticion": "una", "fecha": fecha, "hora": hora,
                   "prompt": texto, "pausada": False, "creada": time.time(), "pedida_por": "Sony (chat)"})
        programador.guardar_tareas(ts)
    return f"Recordatorio creado para el {cuando:%d/%m/%Y a las %H:%M}: «{texto}». Avisará en el PC, en el móvil y por Telegram. Se ve en «Programados»."


def t_tiempo(a):
    ciudad = (a.get("ciudad") or "").strip() or privado.get("ciudad", "Madrid")  # ciudad por defecto: en privado.json
    g = json.loads(urllib.request.urlopen("https://geocoding-api.open-meteo.com/v1/search?count=1&language=es&name=" + urllib.parse.quote(ciudad), timeout=15).read())
    if not g.get("results"):
        return f"No encuentro la ciudad «{ciudad}»."
    c = g["results"][0]
    q = urllib.parse.urlencode({"latitude": c["latitude"], "longitude": c["longitude"], "timezone": "auto", "forecast_days": 7,
                                "current": "temperature_2m,weather_code,wind_speed_10m",
                                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
    d = json.loads(urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=15).read())
    cur, dl = d["current"], d["daily"]
    lineas = [f"{c['name']} ({c.get('admin1', '')}): ahora {cur['temperature_2m']:.0f} °C, {CODIGOS.get(cur['weather_code'], 'variable')}, viento {cur['wind_speed_10m']:.0f} km/h."]
    for i, dia in enumerate(dl["time"]):
        f_d = dt.date.fromisoformat(dia)  # 15/11: con el día de la semana (el modelo se equivocaba contando)
        nom = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][f_d.weekday()]
        lineas.append(f"- {nom} {f_d.day}/{f_d.month}: {CODIGOS.get(dl['weather_code'][i], 'variable')}, {dl['temperature_2m_min'][i]:.0f}–{dl['temperature_2m_max'][i]:.0f} °C, lluvia {dl['precipitation_probability_max'][i]} %")
    return "\n".join(lineas)


def t_liberar(a):
    import liberar
    threading.Timer(15, liberar.liberar).start()  # después de terminar esta respuesta
    return "En 15 segundos descargo el modelo de chat y la voz para liberar la gráfica y la RAM. Se vuelve a cargar solo cuando me escribas."


def t_recordar(a):  # 15/11: «recuerda que…» → se guarda en Ajustes → Memoria (Sony lo tiene presente siempre)
    import chat
    dato = (a.get("dato") or "").strip()
    if not dato:
        return "¿Qué quieres que recuerde?"
    aj = chat.ajustes(); mem = list(aj.get("memoria") or [])
    if a.get("olvidar"):
        antes = len(mem); mem = [x for x in mem if dato.lower() not in x.lower()]
        aj["memoria"] = mem; chat.escribir(chat.F_AJ, {k: v for k, v in aj.items()})
        return f"Olvidado ({antes - len(mem)} dato/s quitado/s de la memoria)." if antes != len(mem) else "No encontré ese dato en la memoria."
    mem.append(dato); aj["memoria"] = mem; chat.escribir(chat.F_AJ, aj)
    return f"Guardado en la memoria: «{dato}». Lo tendré siempre presente (se ve en Ajustes → Memoria)."


def t_discos(a):  # 15/11: solo lectura, sin tarjeta (antes necesitaba «ejecutar»)
    import shutil, string
    lineas = []
    for l in string.ascii_uppercase:
        try:
            u = shutil.disk_usage(f"{l}:\\")
        except Exception:
            continue
        pct = 100 * u.free / u.total
        lineas.append(f"- {l}: {u.free / 2**30:.0f} GB libres de {u.total / 2**30:.0f} GB ({pct:.0f} % libre)" + ("  ⚠️ menos del 15 %" if pct < 15 else ""))
    return "\n".join(lineas) or "No encuentro discos."


HERRAMIENTAS = {
    "discos": (t_discos, False, "Ver el espacio de los discos", {}, "Espacio libre y total de cada disco del PC (C:, D:, E:…). Solo lectura."),
    "recordatorio_crear": (t_recordatorio, True, "Crear un recordatorio", {"texto": "string", "fecha": "string", "hora": "string"},
                           "Crea un recordatorio que avisa al usuario (PC, móvil y Telegram) a una hora. fecha AAAA-MM-DD, hora HH:MM (hora de España)."),
    "tiempo": (t_tiempo, False, "Ver el tiempo", {"ciudad": "string"},
               "El tiempo actual y de los próximos 7 días en una ciudad (Open-Meteo). Si el usuario no dice ciudad, usa la ciudad que tenga guardada."),
    "recordar": (t_recordar, True, "Guardar o quitar un dato de la memoria de Sony", {"dato": "string", "olvidar": "boolean"},
                 "Guarda una preferencia o dato del usuario en su memoria permanente (Ajustes → Memoria). olvidar=true lo quita. Úsala cuando diga «recuerda que…» u «olvida que…»."),
    "liberar_grafica": (t_liberar, True, "Liberar la gráfica (descargar el modelo)", {},
                        "Descarga el modelo de chat y la voz para dejar libre la gráfica (por ejemplo antes de jugar). Lo mismo que el botón ⏏."),
}
