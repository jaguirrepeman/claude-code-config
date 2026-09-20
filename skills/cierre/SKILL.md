---
name: cierre
description: Check de fin de hilo. Recoge los pendientes de la conversación y los convierte en issues del repo (con confirmación), comprueba que no queda nada sin commitear, sin pushear ni sin fusionar, y da el veredicto ARCHIVABLE o NO ARCHIVABLE con pruebas. Úsalo cuando el usuario diga "hemos terminado", "ciérralo", "ya está", "¿se puede archivar?" o invoque /cierre.
user-invocable: true
argument-hint: [--sin-issues]
allowed-tools: Bash(git status *), Bash(git branch *), Bash(git rev-list *), Bash(git worktree list *), Bash(git fetch *), Bash(gh pr list *), Bash(gh pr view *), Bash(gh issue list *)
---

# /cierre: ¿se puede archivar este hilo sin perder nada?

Un hilo se archiva cuando lo que hizo está en `main` y lo que no hizo está escrito donde se va a
volver a ver: un issue del repo. "Quedan X e Y" en el último mensaje no cuenta, porque el mensaje
se archiva con el hilo. Este es el orden: primero guardar los pendientes, después mirar git.

## Estado (automático)

```!
git fetch --prune --quiet 2>/dev/null || true
echo "rama: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
echo "--- sin commitear"; git status --porcelain 2>/dev/null || true
echo "--- por delante / por detrás del upstream"; git rev-list --left-right --count HEAD...@{upstream} 2>/dev/null || echo "(sin upstream)"
echo "--- PR de esta rama"; gh pr list --head "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" --state all --limit 3 --json number,state,isDraft,url --jq '.[] | "#\(.number) \(.state) draft=\(.isDraft) \(.url)"' 2>/dev/null || echo "(gh no disponible)"
echo "--- worktrees"; git worktree list 2>/dev/null || true
echo "--- issues abiertos del repo"; gh issue list --state open --limit 20 --json number,title --jq '.[] | "#\(.number) \(.title)"' 2>/dev/null || echo "(gh no disponible)"
```

## 1. Pendientes: de la conversación a issues

Repasa el hilo entero, no solo el último mensaje, y haz una lista de lo que quedó abierto:

- lo que se dijo "pendiente", "queda por", "más adelante" o "en otro PR";
- lo marcado "sin verificar" que alguien tiene que comprobar de verdad;
- lo que se decidió no hacer por alcance pero conviene hacer;
- lo que depende del usuario (probar en un dispositivo, una decisión de negocio).

Para cada uno: título corto, y cuerpo con el contexto que hará falta al retomarlo (PR y commit
de donde sale, qué falta exactamente, por qué se dejó, cómo se verifica). Si ya existe un issue
abierto que lo cubre (lista de arriba), se referencia, no se duplica.

**Enseña la lista y espera el OK antes de crear nada.** Con el OK, un `gh issue create --title
... --body ...` por pendiente, y pega las URL. Con `--sin-issues` en `$ARGUMENTS`, o si el usuario
dice que no, los pendientes se dejan listados en el mensaje final marcados como "NO guardados":
el hilo no es archivable en ese caso. Si no hay pendientes, escríbelo con estas palabras: "sin
pendientes que guardar".

## 2. Git: nada a medias

Con el estado de arriba, sin ejecutar más comandos salvo que falte un dato:

| Comprobación | Pasa si |
|---|---|
| Sin commitear | `git status --porcelain` vacío |
| Sin pushear | 0 commits por delante del upstream (o la rama es la protegida y está al día) |
| PR | fusionado (`MERGED`), o cerrado a propósito, o draft retenido a propósito y dicho |
| Worktree | el de este hilo se puede borrar: rama fusionada y sin cambios |
| Verificación | si hubo deploy, la evidencia en vivo está pegada en el hilo (`/deploy-pi`); si no, "sin verificar" está en un issue |

## 3. Veredicto

Termina siempre con este bloque, y nada después de él:

```
VEREDICTO: ARCHIVABLE | NO ARCHIVABLE
Pendientes guardados: <URL de cada issue>, o "sin pendientes que guardar"
Git: <rama>, <n> sin commitear, <n> sin push, PR <#n estado>, worktree <borrable | no aplica | ...>
Falta (solo si NO ARCHIVABLE): <qué, y qué comando o acción lo resuelve>
```

Con ARCHIVABLE, ofrece archivar la sesión (la app pide confirmación; archivar limpia el worktree)
y podar la rama con `/repo-hygiene` si el usuario quiere. No archives por tu cuenta.
