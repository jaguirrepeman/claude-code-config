---
name: repo-hygiene
description: Higiene del repo actual. Lista ramas locales y remotas ya fusionadas y worktrees huérfanos, con la prueba de que están fusionados, y los borra solo tras confirmación. Úsalo cuando el usuario pida "limpia ramas", "quita los worktrees viejos", "higiene del repo" o al cerrar una tanda de PR.
user-invocable: true
disable-model-invocation: true
argument-hint: [--dry-run]
---

# /repo-hygiene: podar lo que ya está fusionado

Borrar es lo único de git que no se deshace con un `revert`, así que esta skill primero
demuestra y después pregunta. Con `--dry-run` en `$ARGUMENTS`, solo la tabla; nada se borra.

## Estado actual (automático)

```!
git fetch --prune --quiet 2>/dev/null
echo "rama protegida: $(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#origin/##' || echo main)"
echo "--- ramas locales (vv)"; git branch -vv 2>/dev/null
echo "--- ramas remotas"; git branch -r 2>/dev/null | grep -v HEAD
echo "--- worktrees"; git worktree list 2>/dev/null
echo "--- PR fusionados (rama de origen -> número)"
gh pr list --state merged --limit 40 --json number,headRefName --jq '.[] | "\(.headRefName) -> #\(.number)"' 2>/dev/null || echo "(gh no disponible)"
```

## Qué es "fusionado" aquí

Una rama cuenta como fusionada solo con una de estas dos pruebas, y se anota cuál:

1. `git merge-base --is-ancestor <rama> origin/<protegida>` devuelve 0 (merge o fast-forward).
2. Un PR **fusionado** tiene esa rama como `headRefName` (squash: el commit no es ancestro,
   pero su contenido está en `main`). El `[gone]` de `git branch -vv` no es prueba: solo dice
   que el remoto ya no existe.

## Qué NO se toca nunca

- La rama protegida y la rama actual de cada worktree que tenga cambios sin commitear
  (`git -C <worktree> status --porcelain` no vacío).
- Una rama con commits que no están en ningún PR fusionado ni son ancestros de la protegida:
  se lista como "con trabajo sin fusionar" y se deja.
- Nada sin prueba. Si `gh` no responde, solo vale la prueba 1.

## Salida

Tabla en español, una fila por candidato:

| Qué | Tipo (local / remota / worktree) | Prueba | Acción propuesta |

Acciones posibles: `git worktree remove <ruta>` (antes que la rama que lo ocupa),
`git branch -D <rama>` (`-D` porque tras un squash `-d` se niega), `git push origin --delete <rama>`.

Después de la tabla, **para y pide confirmación una sola vez para toda la lista**. Si se
confirma, ejecuta en ese orden (worktrees, ramas locales, ramas remotas) y pega la salida real
de cada comando. Si algo falla, se para ahí y se enseña el error; no se sigue con el resto.

Termina con el `git branch -vv` y el `git worktree list` de después, para que se vea lo que
queda.
