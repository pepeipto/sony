---
name: find-skills
description: Buscar skills nuevas en skills.sh cuando el usuario pregunta «¿hay alguna skill para…?», «busca una skill de…» o quiere que Sony aprenda a hacer algo nuevo. Sony busca y recomienda; instalar lo hace el usuario.
---

# Buscar skills nuevas (find-skills)

Adaptada para Sony a partir de la skill «find-skills» de vercel-labs (licencia en ../LICENSE-find-skills.txt).

**Cuándo usarla:**
- El usuario pregunta «¿hay una skill para X?», «busca una skill de X» o «¿puedes aprender a hacer X?».
- Una tarea se repite y ninguna skill del índice encaja (mira antes el índice: puede que ya exista).

**Qué es:** skills.sh es un catálogo público de skills para agentes. Se busca con la herramienta de línea de comandos `npx skills`, que ya funciona en este Mac.

## Pasos

1. **Entiende qué necesita el usuario:** el tema (redes, vídeo, ventas…) y la tarea concreta. Traduce la búsqueda a 2-3 palabras en inglés, porque el catálogo está en inglés. Ejemplos:
   - «algo para escribir ganchos de vídeos» → `hook writer`
   - «ayuda con LinkedIn» → `linkedin post`
   - «hacer miniaturas de YouTube» → `youtube thumbnail`

2. **Busca** con la herramienta `ejecutar` (pide tarjeta):
   ```
   npx -y skills find <palabras>
   ```
   Si no sale nada útil, prueba con sinónimos (por ejemplo `social media`, `content`, `copywriting`).

3. **Filtra antes de recomendar.** No recomiendes nada solo por salir en la búsqueda:
   - Prefiere las que tienen **1.000 instalaciones o más**. Desconfía de las de menos de 100.
   - Prefiere autores conocidos (`anthropics`, `vercel-labs`, `microsoft`) o repositorios con muchas estrellas en GitHub.
   - Si puedes, lee su página en skills.sh con `web_leer` para ver qué hace de verdad.

4. **Presenta al usuario 1-3 opciones**, cada una con:
   - nombre y qué hace, en español y en una frase;
   - instalaciones y autor;
   - el enlace de skills.sh;
   - el comando para instalarla (paso 5).

5. **Instalar lo hace el usuario, no tú.** Tu terminal tiene prohibido modificar Sony (`~/IA/sony`), y es a propósito. Dale este comando para que lo pegue él en la Terminal del Mac:
   ```
   ~/IA/sony/instalar-skill.sh dueño/repositorio@nombre-skill
   ```
   El script descarga la skill, le enseña su contenido y los scripts que trae, le pide confirmación y la añade al índice como «pendiente de prueba». Nunca uses `npx skills add` tú misma.

6. **Si no hay ninguna buena**, dilo claramente y ofrece hacer la tarea con lo que ya sabes. Si es algo que el usuario hará a menudo, ofrece escribir una skill propia y guardarla como nota en el segundo cerebro (skill `guardar-en-segundo-cerebro`) para que el usuario la convierta en skill.

## Después de instalar
- La skill nueva aparece en tu índice en «Externas», marcada «pendiente de prueba». Léela con `skill_leer` antes de usarla.
- Las externas suelen estar en inglés: aplícalas en español y con tus herramientas.
- Si trae scripts, no los ejecutes sin que el usuario los haya revisado, y siempre con tarjeta.

**Qué entrega:** 1-3 skills recomendadas con datos de calidad y el comando de instalación, o un «no hay ninguna buena» claro.

Reglas: buscar está permitido (con tarjeta, porque usa la terminal). Instalar solo lo hace el usuario con el script. Nunca `-y` en una instalación, nunca contraseñas ni tokens.
