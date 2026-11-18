---
name: disenar-sistema-ia
description: Diseñar un sistema de IA (agente o RAG). Hay que montar un asistente, un agente con herramientas o un buscador sobre documentos.
---

# Diseñar un sistema de IA (agente o RAG)

**Cuándo usarla:** Hay que montar un asistente, un agente con herramientas o un buscador sobre documentos.

**Pasos:**
1. Aclarar el objetivo, los usuarios, los datos de origen y las acciones que puede hacer (y cuáles necesitan permiso).
2. Elegir piezas: modelo (diario/pesado/nocturno o nube), recuperación (chunking + embeddings + reranker), herramientas, memoria.
3. Dibujar el flujo paso a paso (diagrama en texto) y dónde van los guardrails (inyección de prompts, secretos, permisos).
4. Estimar coste y recursos: memoria (en el Mac es unificada, 36 GB), latencia, coste de API si se usa Claude, y qué corre en CPU.
5. Proponer cómo evaluarlo (casos de prueba y métricas) y un plan de construcción en fases.

**Qué entrega:** documento de diseño corto con diagrama, piezas, riesgos, recursos y fases.

Reglas: nada de enviar, publicar, pagar ni manejar contraseñas; todo eso pide tarjeta de permiso al usuario.

Estado: pendiente de prueba en los 3 modelos (Diario, Pesado y Nocturno).
