# Comprobación de que la app de Sony dice la VERDAD (15/11/2026). Pasar al final de cada cambio:
#   python ~/IA\panel\comprobar-estado.py
# 1) Busca textos viejos en las páginas y el código de la interfaz.
# 2) Pide las APIs de estado en vivo y avisa de estados falsos o desactualizados.
# Solo lectura: no carga modelos, no envía nada, no cambia nada.
import json, re, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8099"
VIEJOS = [  # (patrón, motivo)
    (r"[Ll]legar[áa]n? con Hermes", "texto de cuando no había skills"),
    (r"[Pp]r[óo]ximamente", "promesa vieja"),
    (r"se instalar[áa] m[áa]s adelante", "ya está instalado"),
    (r"se conectar[áa] (a la IA )?cuando", "ya está conectado"),
    (r"cuando est[ée] instalado", "ya está instalado"),
    (r"estado\">pendiente<|k: 'pendiente'", "estado fijo «pendiente»"),
    (r"href=\"/nebulosa\"|nebulosa-elite", "la nebulosa se retiró (solo queda la Galaxia)"),
    (r"todav[íi]a no se puede leer su texto", "los PDF ya se leen"),
]
EXCLUIR = ("nebulosa.py", "nebulosa3d.js", "nebulosa.js", "nebulosa3d.html", "nebulosa.html", "temas-vista-previa.html")
fallos, avisos = [], []


def revisar_textos():
    for f in list((BASE / "static").glob("*.html")) + list((BASE / "static").glob("*.js")) + list(BASE.glob("*.py")):
        if f.name in EXCLUIR or f.name == Path(__file__).name:
            continue
        for n, linea in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pat, motivo in VIEJOS:
                if re.search(pat, linea):
                    fallos.append(f"{f.name}:{n} · {motivo} · «{linea.strip()[:90]}»")


def get(ruta, t=60):
    with urllib.request.urlopen(URL + ruta, timeout=t) as r:
        return json.loads(r.read())


def revisar_apis():
    try:
        c = get("/api/conectores/estado?forzar=1", 90)
    except Exception as e:
        return fallos.append(f"API de conectores no responde: {e}")
    if time.time() - c["t"] > 300:
        fallos.append("El estado de los conectores tiene más de 5 minutos")
    for x in c["conectores"]:
        marca = {"ok": "✅", "error": "⚠️", "sin_configurar": "⏸"}.get(x["estado"], "?")
        print(f"   {marca} {x['nombre']}: {x['detalle']}")
        if x["estado"] == "error":
            avisos.append(f"Conector con error: {x['nombre']} · {x['detalle']}")
        if "pendiente" in x["detalle"].lower():
            fallos.append(f"Conector con texto «pendiente»: {x['nombre']}")
    viejo = get("/api/conectores")
    if any(v.get("estado") == "pendiente" for v in viejo):
        fallos.append("/api/conectores (antiguo) sigue devolviendo «pendiente»")
    cer = get("/api/cerebro/estado")
    print(f"   🧠 Segundo cerebro: {cer['notas']} notas · {cer['hoy']} cambiadas en 24 h · índice {'al día' if cer['al_dia'] else 'NO al día'}")
    if not cer["al_dia"]:
        avisos.append("El índice del segundo cerebro no está al día (se pone al día solo en ~30 s)")
    sk = get("/api/skills")
    print(f"   🧩 Skills: {sk['activas']} activas de {sk['total']} · modo automático {'encendido' if sk['auto'] else 'apagado'}")
    if sk["total"] < 1:
        fallos.append("La pestaña Skills no encuentra skills")


def revisar_filtro():
    import sys; sys.path.insert(0, str(BASE))
    import agente
    prueba = "Hola</parameter>\n</function>\n</tool_call>\nfin <|im_end|>"
    salida = agente.limpiar_texto_interno(prueba)
    if any(m in salida for m in ("</tool_call>", "</function>", "</parameter>", "<|im_end|>")):
        fallos.append("El filtro de marcas internas deja pasar texto interno: " + repr(salida))


def revisar_afirmaciones():  # 15/11: la guardia «lo dice pero no lo hizo» detecta carpetas inventadas
    import agente, time
    msgs = [{"role": "user", "content": "trabaja en E:/segundo-cerebro/sony/practicas"}]
    if not agente.comprobar_afirmaciones("Capturas en `web-ejemplo/capturas-que-no-existen-xyz/`.", msgs, time.time()):
        fallos.append("La guardia de afirmaciones falsas no detecta una carpeta inventada")


def revisar_manual():
    m = (BASE / "manual_sony.md").read_text(encoding="utf-8")
    for palabra in ("imagen_crear", "tiempo", "recordatorio_crear", "sai_estado", "web_buscar", "skill_leer"):
        if palabra not in m:
            fallos.append(f"El manual de Sony no menciona «{palabra}»")
    cap = Path(r"~/segundo-cerebro\sony\capacidades.md")
    if not cap.exists():
        fallos.append("Falta ~/segundo-cerebro\\sony\\capacidades.md")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Comprobando que la app de Sony dice la verdad…")
    revisar_textos(); revisar_apis(); revisar_manual(); revisar_filtro(); revisar_afirmaciones()
    for a in avisos:
        print("  AVISO ·", a)
    for f in fallos:
        print("  FALLO ·", f)
    print("OK: todo al día." if not fallos else f"{len(fallos)} cosas desactualizadas.")
    sys.exit(1 if fallos else 0)
