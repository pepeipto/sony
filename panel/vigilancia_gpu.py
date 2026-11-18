# Vigilancia de la RTX 4090 mientras hay un modelo en la gráfica (por las caídas «GPU is lost» del 15/11).
# Cada 5 s apunta potencia, temperatura, relojes y errores en ~/IA\logs\gpu-vigilancia.log.
# - Si la potencia pasa de 295 W (límite 280 W desde el 15/11, aprobado por el usuario): descarga el modelo.
# - Si la gráfica no responde, aparece «CUDA error» o Xid: pasa sola a modo CPU y avisa (chat, móvil y Telegram).
import subprocess, threading, time
from pathlib import Path

import chat

LOG = Path(r"~/IA\logs\gpu-vigilancia.log")
LOG_LLAMA = chat.LOGS / "llama-server-chat.log"
LIMITE_OBJETIVO_W = 220  # 16/11 07:30: lo pone la tarea de arranque «IA - limite GPU 220W» (tras la caída a 250 W)
LIMITE_W = 235  # 16/11: por encima de esto se descarga el modelo
NO_WINDOW = 0x08000000
estado = {"ultimo": None, "alerta": None}


def _escribir(linea):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + linea + "\n")


def leer_gpu():
    r = subprocess.run(["nvidia-smi", "--query-gpu=power.draw,power.limit,temperature.gpu,clocks.sm,memory.used,utilization.gpu",
                        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
    if r.returncode != 0 or "lost" in (r.stdout + r.stderr).lower():
        raise RuntimeError((r.stdout + r.stderr).strip()[:200] or f"nvidia-smi código {r.returncode}")
    p, lim, t, mhz, mem, util = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
    return {"w": float(p), "limite": float(lim), "temp": int(float(t)), "mhz": int(float(mhz)), "vram": int(float(mem)), "uso": int(float(util))}


def limite_ok(maximo=LIMITE_OBJETIVO_W + 10):
    try:
        return leer_gpu()["limite"] <= maximo
    except Exception:
        return False


def _a_modo_cpu(motivo):
    a = chat.ajustes(); a.update(pausa_gpu=True, modo_cpu=True); chat.escribir(chat.F_AJ, a)
    estado["alerta"] = motivo; _escribir("ALERTA → modo CPU: " + motivo)
    try:  # 16/11: el entrenamiento nocturno se para del todo y no se reanuda solo
        (Path.home() / "IA" / "logs" / "STOP").write_text("vigilancia: " + motivo, encoding="utf-8")
    except Exception:
        pass
    try:
        chat.descargar()
    except Exception:
        pass
    aviso = "⚠️ La gráfica ha dado un fallo y Sony ha pasado sola a modo CPU (más lenta). Lo revisamos."
    try:
        import telegram_con; telegram_con.enviar(aviso)
    except Exception:
        pass
    try:
        import push; push.avisar("usuario", "Sony ha pasado a modo CPU por un fallo de la gráfica", tag="gpu")
    except Exception:
        pass


def bucle():
    tam_log = LOG_LLAMA.stat().st_size if LOG_LLAMA.exists() else 0
    while True:
        time.sleep(5)
        p = chat._proc.get("p")
        en_gpu = p is not None and p.poll() is None and not chat._proc.get("cpu")
        if not en_gpu:
            # 16/11: si llama-server se cae por un error de CUDA, el proceso ya ha muerto: se mira el registro igualmente
            try:
                if LOG_LLAMA.exists() and LOG_LLAMA.stat().st_size > tam_log and not chat._proc.get("cpu"):
                    with LOG_LLAMA.open("rb") as f:
                        f.seek(tam_log); nuevo = f.read().decode("utf-8", "replace")
                    if any(c in nuevo for c in ("CUDA error", "GPU is lost", "Xid", "device lost")):
                        _a_modo_cpu("error de CUDA en llama-server (el modelo se cayó)")
            except Exception:
                pass
            tam_log = LOG_LLAMA.stat().st_size if LOG_LLAMA.exists() else 0
            continue
        try:
            g = leer_gpu(); estado["ultimo"] = g
            _escribir(f"{chat._proc.get('modelo')} {g['w']:.0f}W/{g['limite']:.0f}W {g['temp']}°C {g['mhz']}MHz vram={g['vram']}MiB uso={g['uso']}%")
            if g["w"] > LIMITE_W:
                _escribir(f"POTENCIA {g['w']:.0f} W > {LIMITE_W} W: se descarga el modelo"); chat.descargar()
        except Exception as e:
            _a_modo_cpu(f"nvidia-smi no responde: {e}"); continue
        try:  # errores nuevos en el registro de llama-server
            if LOG_LLAMA.exists() and LOG_LLAMA.stat().st_size > tam_log:
                with LOG_LLAMA.open("rb") as f:
                    f.seek(tam_log); nuevo = f.read().decode("utf-8", "replace")
                tam_log = LOG_LLAMA.stat().st_size
                for clave in ("CUDA error", "GPU is lost", "Xid", "device lost"):
                    if clave in nuevo:
                        _a_modo_cpu(f"«{clave}» en llama-server"); break
        except Exception:
            pass


def api_estado(h):
    h.send(200, {"ultimo": estado["ultimo"], "alerta": estado["alerta"], "limite_ok": limite_ok(), "modo_cpu": chat.modo_cpu()})


def api_modo(h):
    if getattr(h, "rol", None) or h.client_address[0] not in ("127.0.0.1", "::1"):
        return h.send(403, {"error": "Esto solo se cambia desde el PC."})
    d = chat.leer_cuerpo(h); a = chat.ajustes()
    cpu = bool(d.get("modo_cpu"))
    a.update(pausa_gpu=cpu, modo_cpu=cpu); chat.escribir(chat.F_AJ, a)
    chat.descargar(); estado["alerta"] = None
    _escribir("modo cambiado a " + ("CPU" if cpu else "GPU") + " desde Ajustes")
    h.send(200, {"modo_cpu": cpu})


def register(R):
    R[("GET", "/api/gpu/estado")] = api_estado
    R[("POST", "/api/gpu/modo")] = api_modo
    threading.Thread(target=bucle, daemon=True).start()
