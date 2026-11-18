---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

> **Regla de Sony:** esta skill se usa con las herramientas y permisos de Sony (skill_leer, archivo_leer/escribir, ejecutar en la terminal zsh del Mac). Donde diga «Skill tool» usa skill_leer; donde diga subagentes, hazlo tú en serie. Instalar paquetes, ejecutar scripts, enviar, publicar o borrar algo pide SIEMPRE tarjeta al usuario. Nada de contraseñas ni claves.
> **Estado:** pendiente de prueba en los 3 modelos (Diario, Pesado y Nocturno).


Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows) - not the current workspace.

Include a "suggested skills" section in the document, naming which skills the next agent should read with skill_leer.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.
