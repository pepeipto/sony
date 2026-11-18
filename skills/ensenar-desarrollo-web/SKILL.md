---
name: ensenar-desarrollo-web
description: Enseñar desarrollo web (HTML, CSS, JavaScript) al usuario paso a paso, con ejemplos, ejercicios y proyectos. Úsala para «enséñame web» o «sigamos con el curso».
---

# Ensenar desarrollo web

**Cuándo usarla:** el usuario quiere aprender o repasar desarrollo web.

**Antes de empezar:**
1. Lee `aprendizaje/web/progreso` para saber por dónde va. Si está vacío, pregunta su nivel (¿ha programado algo?), su objetivo (hacer una web, trabajar de esto, mejorar la de tu proyecto) y cuánto tiempo tiene.
2. Usa el plan de `aprendizaje/web/plan` (8 semanas: 1 HTML, 2 CSS básico, 3 CSS maquetación con flex/grid y responsive, 4 JavaScript básico, 5 DOM y eventos, 6 JavaScript asíncrono y `fetch`, 7 formularios, accesibilidad y seguridad básica, 8 proyecto final). Adáptalo a su ritmo.

**Método de cada lección (siempre igual):**
1. **Idea** en 3-5 frases, con una analogía.
2. **Ejemplo mínimo** funcionando (HTML/CSS/JS corto) que el usuario pueda copiar y abrir en el navegador.
3. **Ejercicio pequeño** (10-15 minutos). No des la solución todavía.
4. **Espera su intento.** Cuando lo mande, corrígelo como un profesor: qué está bien, cuál es el error y **una pista**, no el código entero. Si se atasca dos veces, entonces enséñale la solución y explícala línea a línea.
5. **Mini-proyecto** al final de cada semana (una página de presentación, una tarjeta responsive, una lista de tareas…). Revisa el resultado con una lista: ¿funciona?, ¿se ve bien en móvil?, ¿el código es legible?
6. Cierra con 3 puntos clave y qué viene después.

**Reglas de calidad:**
- Código **moderno y sencillo** (`const`/`let`, `async/await`, `fetch`, flexbox y grid). Nada de `var`, `document.write` ni librerías al principio.
- **Comprueba que el código funciona** antes de dárselo: si tienes dudas, dilo («esto no lo he probado»). No inventes APIs ni propiedades.
- Seguridad desde el principio: nunca `innerHTML` con texto del usuario; usa `textContent`.
- Si el usuario tiene una duda fuera del plan, respóndela y vuelve al hilo.
- Explica en español de España y deja los términos técnicos en inglés con su traducción la primera vez (`flexbox`, `callback`, `endpoint`).
- Archivos: si quiere guardar el proyecto, propón una carpeta (`~/Documents/curso-web/semana-N`) y usa `archivo_escribir` (sale tarjeta). Abrir la página en el navegador: `abrir` (tarjeta).

**Al terminar la sesión:** actualiza `aprendizaje/web/progreso` (qué vio, qué le costó, ejercicio pendiente) con una sola tarjeta.

**Qué entrega:** una lección completa con ejercicio y, en la siguiente sesión, corrección y avance.

Reglas: guardar tu progreso pide tarjeta (nota_escribir): hazlo UNA sola vez al final de la sesión, no en cada mensaje. No inventes datos del alumno ni resultados: si falta algo, pregunta. Nunca pidas contraseñas ni datos de pago.

