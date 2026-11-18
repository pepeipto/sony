# Sony en el Mac (MacBook Pro M4 Max, 64 GB) — notas para adaptarla

Paquete hecho el 16-nov-2026 desde el PC del usuario. **No lleva ninguna clave, token, contraseña, .env, chat ni base de credenciales**: cada conector se vuelve a configurar en el Mac, y las claves las pone el usuario.

## Modelo «Diario»
- Hugging Face: `unsloth/Qwen3.8-27B-GGUF`
  - `Qwen3.8-27B-UD-Q5_K_M.gguf`: 18,5 GB, sha256 `e2771d4c10c6b77141552ea7a21631067271f17baf918f46a3cba78495f92e1e`
  - `mmproj-F16.gguf` (visión): 0,86 GB, sha256 `cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e`
- Parámetros de llama-server en el PC: `-ngl 999 -c 32768 -fa on --cache-type-k q8_0 --cache-type-v q8_0 --jinja --cache-reuse 256 --no-webui -np 1 --mmproj mmproj-F16.gguf --port 8080 --host 127.0.0.1`
  - Plantilla: la del propio GGUF (`--jinja`). Razonamiento apagado en el agente (`chat_template_kwargs: {enable_thinking: false}`).
  - En el Mac: llama.cpp con Metal (`brew install llama.cpp` o el binario oficial de GitHub). `-ngl 999` vale igual. Con 64 GB de memoria unificada caben el modelo (~19 GB) y 32k de contexto. Nota: llama.cpp desactiva `--cache-reuse` cuando hay mmproj.
- Otros modelos del PC (no van en el paquete): Pesado (`Qwen3.8-Flash-Next` IQ3_XXS), Nocturno (DeepSeek). Buscador del cerebro: `bge-m3-Q8_0.gguf` (embeddings) y `bge-reranker-v2-m3-Q8_0.gguf`.

## Qué hay en el zip
- `panel/`: la app (servidor Python en :8099, `servidor.py` + módulos), `static/` (interfaz), `manual_sony.md`, `REGLAS-DESARROLLO.md` y `comprobar-estado.py`. Sin chats, ajustes, permisos ni estados.
- `skills/`: las 49 skills (antes en `~/IA\hermes\skills`).
- `segundo-cerebro-sony/`: lecciones.md, capacidades.md, recetas/, tutorial.md, informe-entrenamiento.md y mejoras-propuestas.md. **No incluye** las prácticas (140 MB) ni el resto del segundo cerebro.
- `memoria-sony.json`: la memoria de Sony (datos del usuario y su familia, preferencias). Es privada: no la subas a ningún sitio.

## Partes específicas de Windows (hay que adaptarlas)
| Qué | Dónde | En el Mac |
|---|---|---|
| Rutas `~/IA\…`, `~/segundo-cerebro\…`, `~/proyectos-clase` | casi todos los .py (constantes al principio) | una carpeta base, p. ej. `~/IA` y `~/segundo-cerebro` |
| `llama-server.exe` y `~/IA\llamacpp` | chat.py, buscador.py | binario de llama.cpp para Metal |
| PowerShell (`powershell -Command …`) en `ejecutar`, liberar, cámaras, discos | agente.py, liberar.py, manos_extra.py, comprobar-estado.py | zsh/bash; revisar la lista negra `PROHIBIDO_CMD` (rutas de Windows, regedit, schtasks…) y hacer una para macOS (`sudo`, `launchctl`, `rm -rf /`, `~/Library/LaunchAgents`, `defaults write`…) |
| `nvidia-smi`, límite de 220 W, tarea «IA - limite GPU …», `vigilancia_gpu.py`, modo CPU | vigilancia_gpu.py, chat.py, estado_conectores.py | no aplica: quitar el módulo o cambiarlo por `powermetrics` / temperatura del Mac |
| Administrador de credenciales de Windows (`keyring` / `cred_leer`) | correo.py y conectores | Llavero de macOS (`keyring` ya lo soporta) |
| Excel/Word por COM (`oficina.py`) | oficina.py | no hay COM en el Mac: usar `openpyxl` / `python-docx` o AppleScript con Office para Mac |
| Ventanas sin consola (`creationflags=0x08000000`) | varios | quitar el parámetro |
| Electron «IA Sony» y acceso directo | (no va en el zip) | la app web funciona en el navegador en `http://127.0.0.1:8099` |
| Tailscale serve, SearXNG en Docker, go2rtc (cámaras), SAI, Govee | remoto.py, searxng_bajo_demanda.py, camaras.py, sai.py, govee.py | opcionales; las cámaras y el SAI son del PC de casa |

## Reglas que hay que mantener
- Nunca dos modelos cargados a la vez. Nada arranca solo con el sistema sin permiso del usuario.
- Las tarjetas de permiso las aprueba solo el usuario. `ejecutar` pide tarjeta siempre.
- Las claves nunca van en archivos, registros ni el chat.
