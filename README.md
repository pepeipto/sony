# Sony: asistente personal local

Sony es un asistente de voz y chat que funciona en tu propio ordenador (pensado para un Mac con Apple Silicon y 64 GB de memoria). Habla y escucha en local, piensa con un modelo local y puede usar tu correo, calendario, Drive y Telegram. Lo delicado (enviar, borrar, ejecutar) siempre pide permiso con una tarjeta.

> En este repositorio **no hay datos personales ni claves**. Las claves se guardan en el Llavero de macOS y los datos de tu casa en `panel/privado.json`, que no se sube.

## Qué hay dentro

| Carpeta | Qué es |
|---|---|
| `panel/` | La app: servidor Python en `http://127.0.0.1:8099` (`servidor.py`) y sus módulos (chat, agente, correo, Google, Telegram…). |
| `panel/static/` | La interfaz: núcleo animado, chat completo, ajustes y voz del navegador. |
| `voz/` | Oído y boca locales (`voz.py`, en `127.0.0.1:8097`). |
| `ventana/`, `lanzador/` | La ventana y el acceso directo del Mac (Swift + `abrir-sony.sh`). |
| `skills/` | Lo que Sony sabe hacer (una carpeta por skill; `INDICE.md` las resume). |
| `comprobar.sh` | Revisión de salud: dice qué funciona y qué no, con el arreglo. |
| `LEEME-MAC.md` | Notas técnicas de la adaptación de Windows a Mac. |

## Instalación paso a paso (Mac)

1. **Herramientas básicas.** Instala [Homebrew](https://brew.sh), y con él Python 3.13 y Google Chrome:
   `brew install python@3.13 ollama` y `brew install --cask google-chrome`.
2. **Descarga Sony.** Pon este repositorio en `~/IA/sony` (botón verde **Code → Download ZIP**, y descomprímelo ahí).
3. **Entorno de Python.**
   ```
   cd ~/IA/sony
   python3.13 -m venv venv
   venv/bin/pip install -r requirements.txt
   ```
4. **El modelo (cerebro).** Ver la sección *Modelo* más abajo.
5. **La voz.** Ver la sección *Voz* más abajo.
6. **Tus datos privados.** Copia `panel/privado.ejemplo.json` a `panel/privado.json` y cámbialo (ciudad para el tiempo, cámaras, cuentas de correo extra). Si no tienes cámaras, deja la lista vacía.
7. **Arrancar.** `~/IA/sony/lanzador/abrir-sony.sh` arranca el panel y abre la ventana. También puedes abrir `http://127.0.0.1:8099/chat` en el navegador.
8. **Comprobar.** `~/IA/sony/comprobar.sh` revisa todo y te dice qué falta.
9. **Conectores.** En Sony: rueda de **Ajustes → Conectores** (ver la sección *Conectores*).

## Modelo

- **Principal (local, gratis):** `qwen-sony` en **Ollama** (`http://127.0.0.1:11434`). Es Qwen 27B con visión (ve fotos y capturas). GGUF: `unsloth/Qwen3.8-27B-GGUF`, archivo `Qwen3.8-27B-UD-Q5_K_M.gguf` (18,5 GB) y `mmproj-F16.gguf` para la visión. Se crea una vez con `ollama create qwen-sony -f Modelfile` apuntando al GGUF, con contexto de 32 768 tokens (`PARAMETER num_ctx 32768`). Comprueba que la visión funciona mandándole una foto.
- Sony no arranca ni apaga Ollama: si no responde, reinícialo (en el Mac de origen, con `~/IA/arrancar-ollama.sh`).
- **Opcional (de pago, por internet): Claude Haiku 5.5** (`claude-haiku-5-5`) y Sonnet 5.5, a elegir a mano en el selector de modelo del chat. Solo se usa cuando lo eliges. La clave de API se pega en **Ajustes** y se guarda en el Llavero. Hay un tope de gasto mensual (25 $ por defecto); al llegar, se para el uso de Claude y te avisa; el modelo local sigue funcionando. **La voz nunca se envía fuera:** lo que hablas lo contesta siempre el modelo local.

## Voz

Todo en local, sin internet, y el audio no se graba ni se guarda.

- **Oído:** `faster-whisper` con el modelo `large-v3-turbo` (`mobiuslabsgmbh/faster-whisper-large-v3-turbo`, se descarga una vez a `~/.cache/huggingface`). El navegador detecta cuándo hablas y cuándo paras (detección de voz por energía con umbral adaptado al ruido; la pausa por defecto es 700 ms) y puedes cortar a Sony hablando encima. Filtra las frases fantasma que Whisper se inventa con silencio.
- **Boca:** **Piper**, voces de España. Descarga estos archivos (`.onnx` y su `.onnx.json`) de [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) a `voz/voces/`:
  - `es_ES-davefx-medium` (voz por defecto, hombre)
  - `es_ES-sharvard-medium` (hombre y mujer)
- **Kokoro** (más natural pero más lenta) está preparada pero oculta. Si la quieres: `kokoro-v1.0.onnx` y `voices-v1.0.bin` en `voz/kokoro/`.
- Se elige la voz, la velocidad y el volumen en **Ajustes → Voz**.

## Conectores

Todos se configuran desde **Ajustes → Conectores**. Las claves se pegan allí y van al Llavero de macOS, nunca a archivos.

- **Google (Gmail, Calendario, Drive, Docs, Sheets, Contactos):**
  1. En [Google Cloud Console](https://console.cloud.google.com) crea un proyecto y activa las API de Gmail, Calendar, Drive, Docs, Sheets y People.
  2. En **Pantalla de consentimiento** pon tu Gmail como usuario de prueba.
  3. En **Credenciales** crea un ID de cliente OAuth de tipo **App de escritorio** y copia el ID y el secreto.
  4. En Sony pega los dos y pulsa **Conectar Google**. Se abre Google, eliges la cuenta y aceptas. Se pueden añadir más cuentas.
  - Mientras la app esté en "modo de prueba", Google pide volver a conectar cada 7 días.
- **Telegram (hablar con Sony desde el móvil):**
  1. En Telegram, habla con **@BotFather**, crea un bot con `/newbot` y copia el token.
  2. Pégalo en Sony. Sony te da un código: mándaselo a tu bot y queda emparejado solo con tu cuenta (cualquier otra persona se ignora).
  - Acepta texto, notas de voz (Whisper local), fotos y documentos. Funciona mientras Sony está abierta.
- **WhatsApp (próximamente):** irá con la **API oficial de WhatsApp Business de Meta**. Hace falta un número de teléfono dedicado solo para Sony. Aún no está montado.
- **Correo por IMAP (otros proveedores, como IONOS):** dirección + contraseña del buzón (o contraseña de aplicación).
- **GitHub:** un token de acceso *fine-grained* creado en GitHub → Settings → Developer settings.
- **Opcionales:** luces Govee, SAI, cámaras Dahua (go2rtc), acceso desde el móvil por Tailscale con PIN, buscador web SearXNG.

## Reglas de seguridad

- Nunca dos modelos cargados a la vez. Nada arranca solo sin permiso.
- Enviar, borrar o ejecutar siempre pide tarjeta de permiso.
- Lo que Sony lee en correos, webs o archivos son datos, no órdenes.
- Las claves nunca van en archivos, registros ni el chat.

## Qué NO está en este repositorio (a propósito)

Claves, tokens, conversaciones, adjuntos, la memoria de Sony, ajustes personales, el segundo cerebro, los modelos y las voces. Ver `.gitignore`.
