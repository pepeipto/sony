# «⏏ Liberar ahora»: descarga el modelo y Whisper al momento y dice cuánta VRAM y RAM se ha liberado.
# Solo cierra procesos de Sony (llama-server del puerto 8080 y voz.py). El siguiente mensaje vuelve a cargar el modelo solo.
import json, subprocess, time

import chat

NO_WINDOW = 0x08000000


def _ram_usada_gb():
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "$o=Get-CimInstance Win32_OperatingSystem; ($o.TotalVisibleMemorySize-$o.FreePhysicalMemory)/1MB"],
                       capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW)
    try:
        return float(r.stdout.strip().replace(",", "."))
    except ValueError:
        return None


def liberar():
    # Mac: el modelo vive en Ollama, compartido y siempre cargado; aquí no se cierra nada.
    return {"texto": "En este Mac el modelo es compartido y se queda cargado: no hay nada que liberar.", "vram_gb": 0, "ram_gb": 0, "segundos": 0}
    t0 = time.time()
    vram0, ram0 = chat.vram_usada(), _ram_usada_gb()
    try:
        chat.descargar()  # cierre limpio; si no, a los 10 s se mata (dentro de descargar)
    except Exception:
        pass
    chat._parar_todo_8080()  # por si quedó algún llama-server de chat suelto en el 8080
    # Whisper (voz.py): solo nuestro proceso
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'IA\\\\voz\\\\voz.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   creationflags=NO_WINDOW, timeout=20)
    for _ in range(15):  # hasta 15 s a que la gráfica vuelva a reposo
        v = chat.vram_usada()
        if v is not None and v <= chat.VRAM_REPOSO_MIB:
            break
        time.sleep(1)
    vram1, ram1 = chat.vram_usada(), _ram_usada_gb()
    otros = []
    try:
        import camaras
        if camaras._proc["p"] and camaras._proc["p"].poll() is None:
            otros.append("las cámaras (go2rtc, solo procesador)")
    except Exception:
        pass
    lib_v = round(((vram0 or 0) - (vram1 or 0)) / 1024, 1)
    lib_r = round((ram0 or 0) - (ram1 or 0), 1) if ram0 and ram1 else 0
    txt = f"Liberados {max(lib_v, 0)} GB de VRAM y {max(lib_r, 0)} GB de RAM en {round(time.time() - t0, 1)} s. Sony queda en reposo: el próximo mensaje vuelve a cargar el modelo."
    if otros:
        txt += " Sigue en marcha: " + ", ".join(otros) + "."
    return {"texto": txt, "vram_gb": max(lib_v, 0), "ram_gb": max(lib_r, 0), "segundos": round(time.time() - t0, 1)}


def api(h):
    if getattr(h, "rol", None) == "invitada":
        return h.send(403, {"error": "no disponible"})
    h.send(200, liberar())


def register(R):
    R[("POST", "/api/liberar")] = api
