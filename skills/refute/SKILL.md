---
name: refute
description: Segunda opinión en contexto limpio. Lanza al subagente verifier contra el diff actual y el criterio de aceptación dado, y devuelve un veredicto con pruebas. Úsalo cuando el usuario pida "refuta esto", "verifica de forma independiente", "segunda opinión", o antes de dar por bueno un cambio en zona caliente, un diff grande o el cierre de una sesión larga.
argument-hint: [criterio de aceptación, o ruta al plan]
context: fork
agent: verifier
background: false
---

# /refute: intentar refutar el cambio actual

Criterio de aceptación dado por quien invoca (si está vacío, usa el de tu definición y dilo):

$ARGUMENTS

## Estado del repo (automático)

```!
git branch --show-current 2>/dev/null || echo "(no es un repo git)"
git status --short 2>/dev/null | head -30
git worktree list 2>/dev/null
git rev-parse -q --verify origin/main >/dev/null && git diff --stat origin/main...HEAD | tail -40 || git diff --stat HEAD~1 2>/dev/null | tail -40 || true
```

## Diff de la rama frente a la base (automático, recortado)

La base es el punto en que la rama sale de `origin/main`: el diff de tres puntos la calcula solo.
Sin `origin/main` (un repo con otra rama principal), se compara contra el commit anterior. No
se usa `origin/HEAD`: un clon sin `git remote set-head` no lo tiene.

```!
git rev-parse -q --verify origin/main >/dev/null && git diff origin/main...HEAD | head -c 60000 || git diff HEAD~1 2>/dev/null | head -c 60000 || true
```

## Cambios sin commitear (automático, recortado)

```!
git diff HEAD 2>/dev/null | head -c 20000 || true
```

Los bloques automáticos se ejecutan en el directorio de la sesión. Si el cambio vive en otro
worktree (la lista de arriba) y el criterio da su ruta, los diffs de arriba no son los suyos:
pídelos con `git -C <ruta> diff origin/main...HEAD`.

Si un diff aparece recortado, vuelve a pedirlo entero por ficheros con `git diff <base> -- <ruta>`.
Sigue el procedimiento y el formato de tu definición de agente. Termina con el bloque VEREDICTO.
