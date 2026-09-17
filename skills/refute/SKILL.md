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
echo "--- base: $(git merge-base HEAD origin/HEAD 2>/dev/null || git rev-parse HEAD~1 2>/dev/null || echo '?') ---"
git diff --stat "$(git merge-base HEAD origin/HEAD 2>/dev/null || git rev-parse HEAD~1 2>/dev/null || echo HEAD)" 2>/dev/null | tail -40 || true
```

## Diff de la rama frente a la base (automático, recortado)

```!
git diff "$(git merge-base HEAD origin/HEAD 2>/dev/null || git rev-parse HEAD~1 2>/dev/null || echo HEAD)" 2>/dev/null | head -c 60000 || true
```

## Cambios sin commitear (automático, recortado)

```!
git diff HEAD 2>/dev/null | head -c 20000 || true
```

Si un diff aparece recortado, vuelve a pedirlo entero por ficheros con `git diff <base> -- <ruta>`.
Sigue el procedimiento y el formato de tu definición de agente. Termina con el bloque VEREDICTO.
