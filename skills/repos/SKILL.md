---
name: repos
description: Estado de todos los repos de una vez y qué hay pendiente en cada uno (git, PR, CI, issues y pendientes de conversaciones recientes). Úsalo cuando el usuario pida "qué tengo pendiente", "revisa todos los repos", "estado de mis proyectos" o al empezar una jornada.
user-invocable: true
argument-hint: [--days N] [--root carpeta] [--no-fetch]
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/status.py *)
---

# /repos: qué hay pendiente en cada repo

Todo lo que sigue lo genera `scripts/status.py`, determinista y de solo lectura (su único efecto
es `git fetch`). No vuelvas a ejecutar `git` ni `gh` por tu cuenta para lo que ya está aquí.

## Estado (automático)

```!
python "${CLAUDE_SKILL_DIR}/scripts/status.py" $ARGUMENTS || true
```

## Qué hacer con esto

1. **Resumen primero, en llano**: una línea por repo con lo que de verdad bloquea o se pudre
   (PR en rojo o parado, CI de main en rojo, commits sin push, ramas fusionadas acumuladas,
   issues abiertos). Un repo con "nada pendiente" se nombra y ya.
2. **Los issues abiertos son la lista de pendientes fiable.** Las "líneas de pendientes en
   sesiones" son una heurística sobre el último mensaje de cada hilo reciente: puede haber ruido
   ("pendiente de ti", "queda por probar en el iPad"). Léelas, quédate con las que son tareas de
   verdad y que no tienen issue, y propón convertirlas en issues (`gh issue create` en el repo que
   toque, con el contexto). No las crees sin que el usuario lo confirme.
3. **Propón, no ejecutes.** Las acciones (podar ramas con `/repo-hygiene`, relanzar un PR
   parado, cerrar un draft viejo, bajar los commits de `origin`) se listan por repo; cada una se
   hace en su repo, en su sesión, no desde aquí.
4. Si un repo dice "gh no disponible", dilo: las secciones de GitHub de ese repo faltan, no
   están vacías.
