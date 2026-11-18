---
name: publicar-en-redes
description: Publicar un post en las redes del usuario con tarjeta por cada post. Úsala cuando el usuario diga «publica», «sube» o «pon esto en X/LinkedIn/Reddit».
---

# Publicar en redes

**Cuándo usarla:** el usuario pide publicar algo en una o varias redes.

**Pasos:**
1. Lee `notas_leer redes/guia-de-voz` y `redes/reglas-por-red`. Si la guía tiene «(completar)», pregunta lo mínimo en vez de adivinar el tono.
2. Si el tema es un proyecto, lee su nota en `proyectos/`.
3. Escribe una versión por red y respeta el máximo de cada una (X 280, LinkedIn 3000, Reddit con título y subreddit).
4. Enséñale el texto al usuario y di en qué red irá cada uno.
5. Llama a `redes_publicar` (red, texto; en Reddit también titulo y subreddit). Aparecerá la tarjeta: El usuario aprueba o deniega. Si deniega, no insistas ni busques otro camino.
6. Si publica, añade una línea a `redes/publicados.md` con `nota_escribir` (lee antes el contenido y añade al final, sin borrar lo anterior).
7. Instagram y TikTok no publican solas: da el texto como borrador y dile al usuario que lo suba él.

**Qué entrega:** el post publicado (o el borrador) y la línea anotada en el registro.

Reglas: publicar siempre pasa por la herramienta `redes_publicar`, que pide tarjeta al usuario por CADA post. Nunca publiques sin tarjeta, nunca manejes contraseñas ni tokens, y no inventes cifras, citas ni resultados.
