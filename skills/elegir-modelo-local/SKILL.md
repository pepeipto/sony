---
name: elegir-modelo-local
description: Elegir un modelo local para el Mac del usuario. Hay que decidir si un modelo cabe y cómo cargarlo en el Mac Studio M4 Max con 36 GB de memoria unificada.
---

# Elegir un modelo local para el Mac del usuario

**Cuándo usarla:** Hay que decidir si un modelo cabe y cómo cargarlo en el Mac Studio (M4 Max, 36 GB de memoria unificada, llama.cpp con Metal).

**Pasos:**
1. Mirar parámetros totales y activos (denso o MoE) y la cuantización disponible (Q4_K_M, Q5_K_M, IQ3_XXS…).
2. Calcular: tamaño del archivo + caché de contexto (KV, más pequeña con q8_0) ≈ memoria necesaria. En Apple Silicon la memoria es una sola (no hay VRAM aparte).
3. Dejar margen para macOS y las apps: no pasar de ~22 GB para el modelo. El Qwen 27B Q5_K_M actual ocupa ~20 GB y deja ~31 % libre.
4. Solo un modelo cargado a la vez.
5. Comparar con lo medido en este Mac: Qwen 27B Q5_K_M ≈ 16 tok/s al generar y ≈ 42 tok/s al leer el prompt; carga en 18 s.
6. Si no cabe o va lento, valorar Claude Haiku o Sonnet por API (de pago, sin usar memoria del Mac).

**Qué entrega:** veredicto (cabe/no cabe), cuantización recomendada, comando de llama-server y estimación de memoria y tok/s.

Reglas: nada de instalar, descargar modelos, enviar, publicar, pagar ni manejar contraseñas sin tarjeta de permiso del usuario.
