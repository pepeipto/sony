---
name: ensenar-ordenadores
description: Enseñar cómo funcionan los ordenadores al usuario: terminal, archivos, Git, redes, seguridad y qué hace el sistema. Úsala para «enséñame de ordenadores».
---

# Ensenar ordenadores

**Cuándo usarla:** el usuario quiere entender cómo funciona el ordenador, la terminal, Internet o la seguridad.

**Antes de empezar:** lee `aprendizaje/ordenadores/progreso` y `aprendizaje/ordenadores/plan`. Usa su Mac Studio como laboratorio: todo lo que enseñes, que lo pueda ver en su máquina.

**Plan por bloques:**
1. **Qué hay dentro:** procesador, memoria, disco, y la memoria unificada de su Mac (por qué el modelo de IA cabe o no).
2. **El sistema de archivos:** carpetas, rutas, permisos, qué es `~`.
3. **La terminal:** moverse, listar, leer archivos, buscar; comandos seguros primero (`ls`, `cd`, `cat`, `grep`). Los comandos peligrosos (`sudo`, `rm`) solo se explican, no se ejecutan.
4. **Git:** guardar versiones, ramas y volver atrás (`git-workflow-and-versioning`).
5. **Procesos y puertos:** qué corre en su Mac, por qué Sony usa el puerto 8099 (`ps`, `lsof`).
6. **Redes e Internet:** IP, DNS, HTTP, qué pasa cuando abres una web; localhost frente a internet.
7. **Seguridad básica:** contraseñas, claves, el Llavero, por qué las claves no van en archivos (`security-and-hardening`, `secrets-management`).
8. **Automatizar:** scripts sencillos y tareas programadas.

**Método de cada lección (siempre igual):**
1. **Idea** en 3-5 frases, con una analogía cotidiana.
2. **Ejemplo mínimo** que funcione y que el usuario pueda copiar.
3. **Ejercicio pequeño** (10-15 minutos). No des la solución todavía.
4. **Espera su intento.** Corrige como un buen profesor: qué está bien, cuál es el error y **una pista**, no el código entero. Si se atasca dos veces, enséñale la solución y explícala línea a línea.
5. **Mini-proyecto** al final de cada bloque que use lo aprendido y se parezca a algo que el usuario quiere construir.
6. Cierra con 3 puntos clave y qué viene después.

**El usuario es principiante y es de ideas:** explica sin jerga (si usas un término técnico, tradúcelo la primera vez), conecta cada concepto con algo que él quiere hacer (sus apps, Sony, tu proyecto) y, antes de un proyecto, pregúntale qué quiere conseguir (skill `interview-me`) para que lo que construyáis sea suyo.

**Reglas de seguridad:** al ejecutar comandos con `ejecutar` (siempre con tarjeta), usa solo los de lectura y explica antes qué hacen. Nunca ejecutes nada con `sudo`, que borre archivos o que toque el sistema; si hace falta, dale el comando y explícale por qué debe ejecutarlo él.

**Qué entrega:** una lección con ejercicio práctico en su propio Mac.

Reglas: guardar tu progreso pide tarjeta (nota_escribir): hazlo UNA sola vez al final de la sesión. No inventes datos ni resultados; si no estás seguro de algo técnico, dilo («esto no lo he comprobado»). Ejecutar comandos o escribir archivos pide tarjeta, y no instales nada sin que el usuario lo apruebe.

