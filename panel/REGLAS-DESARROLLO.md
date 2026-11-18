# Reglas de desarrollo de Sony (IA Sony)

Escrito el 15/11/2026 a petición del usuario: «no puede ser que estemos mucho más avanzados y nos estemos dejando puntos sin actualizar al día».

## La regla principal
**Cada cambio en Sony actualiza A LA VEZ estas tres cosas:**
1. **La interfaz** (chat.js, chat.html, panel, móvil, Telegram): nada de textos fijos que digan «pendiente», «próximamente» o «llegará con…». El estado se lee **en vivo** siempre que se pueda.
2. **El manual de capacidades** de Sony: `~/IA\panel\manual_sony.md` (resumen que va en su contexto) y `~/segundo-cerebro\sony\capacidades.md` (detalle).
3. **La memoria**: el segundo cerebro (`~/segundo-cerebro\sony\…`) y, si cambia algo que Claude debe recordar, su memoria.

## Estados en vivo (nunca a mano)
| Qué | De dónde sale |
|---|---|
| Conectores (Google, GitHub, Govee, Telegram, SAI, web, imágenes, voz, redes, cámaras, Tuya, IONOS, WhatsApp) | `estado_conectores.py` → `/api/conectores/estado` (y lo lee Sony en su manual) |
| Segundo cerebro (notas, cambios de hoy, índice) | `cerebro_rag.py` → `/api/cerebro/estado` |
| Skills (lista, activas, modo automático, prueba) | `skills_panel.py` → `/api/skills` (y el índice que ve Sony) |
| Modelo cargado, límite de la gráfica | `chat.estado()`, `nvidia-smi` |
| SAI | `sai.leer()` |

Si una función no existe todavía, la interfaz lo dice claro **y con qué falta** («⏸ Sin configurar: falta la contraseña de las cámaras»).

## Al terminar CADA cambio
```
python ~/IA\panel\comprobar-estado.py
```
Recorre las páginas y las APIs y avisa de textos viejos o estados falsos. Si sale algo en rojo, se arregla antes de dar el cambio por terminado.

## Siempre
- Nunca dos modelos a la vez; la gráfica limitada a 280 W (desde el 15/11; subir de 30 en 30 W con prueba vigilada); nada arranca con Windows.
- Tarjeta de permiso para enviar, publicar o borrar. Claude nunca aprueba tarjetas: solo el usuario.
- Copia de seguridad antes de tocar algo (`~/IA\panel\copias\…`).
- No hacer pruebas con el modelo mientras el usuario está escribiendo.
