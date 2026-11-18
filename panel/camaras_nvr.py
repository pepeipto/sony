# Cámaras a través del grabador Dahua (16/11/2026): un solo usuario para todos los canales.
# - Solo lectura: vídeo por RTSP (subcanal de baja resolución) y fotos sueltas. NUNCA toca la configuración del grabador.
# - Foto: OpenCV (ya instalado, trae FFmpeg dentro) abre el subcanal, coge UN fotograma y cierra. Sin gráfica.
# - Usuario y contraseña: los del Administrador de credenciales («camaras»); nunca en archivos ni registros.
import time, urllib.parse
from pathlib import Path

import correo

import privado
NVR = privado.get("nvr_ip", "")  # IP del grabador: en privado.json
CANALES = 16  # el grabador numera los canales del 1 al 16 (se usan los que respondan)
FOTOS = Path(r"~/IA\imagen\camaras")


def _url(canal, sub=1):
    u, p = correo.cred_leer("camaras")
    if not p:
        return None
    return (f"rtsp://{urllib.parse.quote(u or 'admin', safe='')}:{urllib.parse.quote(p, safe='')}@{NVR}:554"
            f"/cam/realmonitor?channel={int(canal)}&subtype={sub}")


def foto(canal, sub=1, guardar=True):
    """Un fotograma del canal. Devuelve (ruta | None, mensaje). Un solo intento: si falla, no reintenta (para no bloquear la cuenta)."""
    import os
    os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")  # silencio: que la dirección con la contraseña no salga en ningún registro
    os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    import cv2
    url = _url(canal, sub)
    if not url:
        return None, "Falta el usuario y la contraseña de las cámaras (Ajustes → Cámaras)."
    t0 = time.time()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
    try:
        if not cap.isOpened():
            return None, f"El grabador no abrió el canal {canal} (usuario o contraseña incorrectos, o canal vacío)."
        ok, img = cap.read()
        if not ok or img is None:
            return None, f"El canal {canal} no dio imagen."
        if not guardar:
            return img, f"{img.shape[1]}×{img.shape[0]} en {time.time() - t0:.1f} s"
        FOTOS.mkdir(parents=True, exist_ok=True)
        ruta = FOTOS / f"canal{int(canal):02d}-{time.strftime('%Y%m%d-%H%M%S')}.jpg"
        cv2.imwrite(str(ruta), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return ruta, f"Foto del canal {canal} ({img.shape[1]}×{img.shape[0]}) en {time.time() - t0:.1f} s"
    finally:
        cap.release()
