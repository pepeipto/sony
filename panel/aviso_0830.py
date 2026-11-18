# Aviso único por Telegram a las 08:30 del 16/11/2026 con el resumen de la noche de entrenamiento de Sony (lo pidió el usuario).
# Se lanza una sola vez a mano (no arranca con Windows) y termina después de enviar el mensaje.
import json, re, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, r"~/IA\panel")
OBJ = datetime(2026, 11, 16, 8, 30)
while datetime.now() < OBJ:
    time.sleep(min(300, max(5, (OBJ - datetime.now()).total_seconds())))
INF = Path(r"~/segundo-cerebro\sony\informe-entrenamiento.md")
EST = (Path.home() / "IA" / "logs" / "estado.json")
t = INF.read_text(encoding="utf-8") if INF.exists() else ""
filas = [l for l in t.splitlines() if l.startswith("| ") and not l.startswith("| Ronda")]
rondas = sorted({l.split("|")[1].strip() for l in filas})
bien1 = sum(1 for l in filas if "| Bien |" in l); total = len(filas)
mal_sin = sum(1 for l in filas if "sin arreglar" in l)
aprende = re.findall(r"\| Mal, corregido \| ([^|]+) \|", t)[-3:]
try:
    e = json.loads(EST.read_text(encoding="utf-8"))
    gpu = f"pico {e['pico_w']:.0f} W, máx. {e['pico_t']:.0f} °C, " + (f"incidencias: {'; '.join(e['errores'][-2:])}" if e["errores"] else "sin errores")
except Exception:
    gpu = "sin datos de la noche"
web = Path(r"~/segundo-cerebro\sony\practicas\web-ejemplo\index.html")
msg = (f"🌙 Noche de entrenamiento de Sony\n"
       f"1) Rondas: {len(rondas)} ({', '.join(rondas[-4:])}).\n"
       f"2) Aciertos: {bien1} de {total} a la primera; {total - mal_sin} de {total} tras corregir.\n"
       f"3) Aprendido: {'; '.join(a.strip()[:70] for a in aprende) or '—'}.\n"
       f"4) Web de ejemplo: {'hecha → ' + str(web) if web.exists() else 'sin terminar (sigue hoy)'}.\n"
       f"5) Gráfica: se cayó a las 22:34 (a 280 W) y a las 00:51 (a 250 W, «GPU is lost»). El PC se reinició a las 00:59 y el entrenamiento con el procesador no llegó a arrancar. Para Juan: revisar el cable y el conector de corriente, la gráfica y la ranura.\n"
       f"Informe completo: {INF}")
import telegram_con
telegram_con.enviar(msg)
print("enviado", datetime.now())
