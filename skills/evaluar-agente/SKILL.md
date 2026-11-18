---
name: evaluar-agente
description: Evaluar a Sony u otro agente o asistente tras un cambio. No es para evaluar al usuario (para eso, perfil-de-fortalezas).
---

# Evaluar un agente o un asistente

**Cuándo usarla:** Se quiere saber si Sony u otro agente funciona bien después de un cambio.

**Pasos:**
1. Definir 10-20 casos de prueba reales (tareas que debe hacer) y 5-10 de seguridad (que debe negar).
2. Para cada caso: resultado esperado, criterio de aprobado y herramientas que debería usar.
3. Ejecutar de uno en uno (un modelo cargado) y registrar: aprobado/fallo, pasos, tiempo y tokens.
4. Calcular % de aciertos, fallos típicos y comparar con la versión anterior.
5. Proponer arreglos (instrucciones, herramientas, reglas) y repetir solo los casos que fallaron.

**Qué entrega:** tabla de resultados con % de aciertos, fallos y arreglos propuestos.

Reglas: nada de enviar, publicar, pagar ni manejar contraseñas; todo eso pide tarjeta de permiso al usuario.

Estado: pendiente de prueba en los 3 modelos (Diario, Pesado y Nocturno).
