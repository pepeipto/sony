---
name: montar-video-corto
description: Montar un vídeo corto vertical (TikTok/Reels/Shorts) con los vídeos e imágenes del usuario. «Hazme un corto con mis vídeos», «monta un TikTok de…», «recorta este vídeo».
---

# Montar un vídeo corto

**Cuándo usarla:** el usuario quiere un vídeo vertical a partir de sus vídeos ya grabados o publicados (están en `~/Movies/videos-tiktok/originales`).

**Herramientas:** `video_lista` (qué hay), `video_transcribir` (qué se dice y en qué segundo), `video_montar` (hace el vídeo; pide tarjeta). Guarda en `~/Movies/videos-tiktok/montajes`. **Nunca publica.**

## Pasos
1. `video_lista`. Si está vacío, explícale al usuario cómo pasar los vídeos: AirDrop desde el móvil a esa carpeta (mejor los originales, sin marca de agua) o en TikTok «Compartir → Guardar vídeo». No uses webs de descarga de TikTok.
2. **Pregunta antes de montar** (2 preguntas con opciones): de qué va el corto (tema o mensaje) y cuánto dura (15, 30 o 60 s). Lee `redes/guia-de-voz`.
3. Si hace falta saber qué se dice, `video_transcribir` del vídeo (la primera vez tarda unos minutos).
4. **Propón el guion de montaje** en una tabla: escena, archivo, desde–hasta, texto en pantalla. Estructura de `conocimiento/creacion-de-video/estructura-de-un-video-corto`: gancho en 1-3 s, un solo mensaje, cierre con pregunta. Textos cortos (máx. 8-10 palabras), 1 emoji como mucho.
5. Cuando el usuario diga que sí, `video_montar` con:
   - `nombre`: corto y sin espacios raros (p. ej. `tilt-error-30s`).
   - `escenas`: lista JSON, por ejemplo
     `[{"archivo": "partida1.mp4", "desde": "0:03", "hasta": "0:06", "texto": "Esto te hace perder más que el rival"}, {"archivo": "partida1.mp4", "desde": "0:41", "hasta": "0:50", "texto": "Mira el minimapa cada 5 s", "posicion": "abajo"}, {"archivo": "logo.png", "duracion": 2, "texto": "¿Y a vosotros os pasa?", "posicion": "centro"}]`
6. Dile dónde está el vídeo y que lo revise. Ofrece ajustar (cambiar trozos, textos o duración) y el caption con 3-5 hashtags.

## Reglas
- Si sale tu proyecto, solo hechos de `proyectos/coach-lol-ia` y añade «Solo Windows» y «no respaldado por Riot Games» en el caption o comentario fijado.
- No uses vídeos de otras personas ni música con derechos.
- Los vídeos horizontales salen sobre un fondo desenfocado; si es posible, usa vídeos verticales.
- Todavía no pone música ni subtítulos automáticos palabra a palabra: si el usuario los quiere, los añade en CapCut, o pon el texto clave en `texto`.
