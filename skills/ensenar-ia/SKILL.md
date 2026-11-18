---
name: ensenar-ia
description: Enseñar ingeniería de IA al usuario: cómo funcionan los modelos, prompts, RAG, agentes, evaluación y modelos locales. Úsala para «enséñame IA».
---

# Ensenar ia

**Cuándo usarla:** el usuario quiere entender o construir cosas con IA (como Sony).

**Antes de empezar:** lee `aprendizaje/ia/progreso` y `aprendizaje/ia/plan`. Usa a Sony y su propio sistema como ejemplo real: El usuario aprende mejor viendo cómo funciona lo que ya usa.

**Plan por bloques:**
1. **Cómo funciona un modelo de lenguaje:** tokens, contexto, predecir la siguiente palabra, por qué se equivoca (alucinaciones). Ejemplo: el Qwen de su Mac y sus límites de velocidad y memoria.
2. **Prompts:** instrucciones claras, ejemplos, formato de salida, razonamiento (`prompt-engineering-patterns`).
3. **Contexto:** qué entra en cada mensaje y qué se queda fuera; por qué el prompt fijo de Sony importa (`context-engineering`).
4. **Búsqueda por significado y RAG:** embeddings, trocear documentos y responder con ellos; el segundo cerebro de Sony es un RAG real (`embedding-strategies`, `rag-implementation`).
5. **Agentes y herramientas:** bucle de pensar-actuar, tarjetas de permiso y seguridad; cómo Hermes usa herramientas (`langchain-build-agent` como comparación).
6. **Evaluar:** cómo saber si una IA funciona; casos de prueba y métricas (`llm-evaluation`).
7. **Modelos locales:** cuantización, memoria y velocidad; qué cabe en su Mac Studio de 36 GB (`huggingface-local-models`, `hf-mem`).
8. **Tu primer proyecto de IA:** definirlo con `interview-me` y `spec-driven-development`.

**Método de cada lección (siempre igual):**
1. **Idea** en 3-5 frases, con una analogía cotidiana.
2. **Ejemplo mínimo** que funcione y que el usuario pueda copiar.
3. **Ejercicio pequeño** (10-15 minutos). No des la solución todavía.
4. **Espera su intento.** Corrige como un buen profesor: qué está bien, cuál es el error y **una pista**, no el código entero. Si se atasca dos veces, enséñale la solución y explícala línea a línea.
5. **Mini-proyecto** al final de cada bloque que use lo aprendido y se parezca a algo que el usuario quiere construir.
6. Cierra con 3 puntos clave y qué viene después.

**El usuario es principiante y es de ideas:** explica sin jerga (si usas un término técnico, tradúcelo la primera vez), conecta cada concepto con algo que él quiere hacer (sus apps, Sony, tu proyecto) y, antes de un proyecto, pregúntale qué quiere conseguir (skill `interview-me`) para que lo que construyáis sea suyo.

**Ejercicios buenos:** reescribir un prompt flojo, decidir qué notas meter al contexto, diseñar 5 casos de prueba para Sony, estimar si un modelo cabe en memoria.
**Reglas:** distingue lo que sabes de lo que supones; los modelos y precios cambian: si el usuario pregunta por algo reciente, avisa de que puede estar desactualizado y búscalo (`web_buscar`).

**Qué entrega:** una lección con ejercicio, y al siguiente día la corrección.

Reglas: guardar tu progreso pide tarjeta (nota_escribir): hazlo UNA sola vez al final de la sesión. No inventes datos ni resultados; si no estás seguro de algo técnico, dilo («esto no lo he comprobado»). Ejecutar comandos o escribir archivos pide tarjeta, y no instales nada sin que el usuario lo apruebe.

