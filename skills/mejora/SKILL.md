---
name: mejora
description: Mejora continua programada de los repos. `auditar` audita el repo al que le toca turno y convierte los hallazgos en issues; `arreglar` coge el issue autónomo más grave, lo arregla con su test de regresión y abre un PR en draft. Úsala solo cuando la pida explícitamente `/mejora` o una tarea programada que la nombre; "mejora este código" en una sesión normal no es esto.
user-invocable: true
argument-hint: auditar|arreglar [--root carpeta] [--repos a,b] [--max-drafts N]
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/pick.py *)
---

# /mejora: auditar a issues, arreglar a PR draft

Corre sin nadie delante. Por eso hay dos reglas que no se negocian, y mandan sobre cualquier
otra cosa de este fichero:

1. **Nunca pasa de PR en draft.** En estos repos un PR que no es draft lo fusiona el gate y
   despliega a producción. El robot no fusiona, no marca "ready for review", no toca `main` y
   no despliega. Quien pasa el PR a listo es la persona, tras revisarlo.
2. **Ante la duda, para y deja constancia.** Si algo no cuadra (verificación en rojo antes de
   tocar nada, issue ambiguo, el arreglo toca una zona caliente, falta una herramienta), no se
   improvisa: se comenta en el issue lo que se vio, con la salida real, y se termina el turno.

Modo pedido: `$ARGUMENTS` (la primera palabra es `auditar` o `arreglar`).

## Qué toca (automático)

```!
python "${CLAUDE_SKILL_DIR}/scripts/pick.py" $ARGUMENTS || true
```

Usa el repo, la ruta y el issue de arriba. No elijas otro por tu cuenta.

## Etiquetas

Todas en ASCII, para que `gh` no dependa de la codificación de la consola. Antes del primer
`gh issue create` en un repo, créalas si faltan (`gh label create <nombre> -R <owner/repo>
--color <color> --description <texto> --force`; `--force` no duplica):

| Etiqueta | Para qué |
|---|---|
| `audit` | Todo issue que abre esta skill |
| `audit-autonomo` | Se puede arreglar sin decidir nada de negocio: bug claro, lint, higiene, test que falta |
| `audit-decision` | Necesita a la persona: trade-off de producto, infraestructura viva, borrado, zona caliente |
| `P0` a `P3` | Severidad, la misma escala que `/audit` |

## Modo `auditar`

Sin editar nada en el repo. El único efecto son issues en GitHub y la marca de la rotación.

1. **Copia limpia de `origin`.** `git -C <ruta> fetch --prune` y un worktree desacoplado de la
   rama por defecto en el scratchpad (`git -C <ruta> worktree add --detach <scratch>/audit-<repo>
   origin/<rama-por-defecto>`). Se audita eso, no la copia de trabajo de la persona, que puede
   estar a medias o atrasada. Al terminar, `git -C <ruta> worktree remove --force` de ese
   worktree y nada más.
2. **Contexto del repo.** Lee su `CLAUDE.md`, su `.claude/verify-command` y sus
   `.claude/rules/*.md`. Los `paths:` de las reglas de zona caliente son la lista de ficheros que
   nunca llevan `audit-autonomo`.
3. **Auditoría.** Lanza el subagente `repo-auditor` sobre esa copia con la lista de "Qué revisar"
   y "Cómo verificar cada hallazgo" de la skill `/audit` (léela en
   `~/.claude/skills/audit/SKILL.md`) y pídele la tabla de criticidad. Además, que corra la
   verificación del repo una vez y diga cuánto tarda y si pasa: un `main` en rojo es un `P0`.
4. **Sin duplicados.** `gh issue list -R <slug> --label audit --state all --limit 100`. Un
   hallazgo que ya tiene issue abierto no se repite (si hay evidencia nueva, se comenta en él);
   uno cerrado como "not planned" no se reabre.
5. **Issues.** Como mucho cinco por ejecución, los más graves; el resto va en una línea cada uno
   al final del resumen. Título `[P1] <qué falla, en llano>`. Cuerpo, en español:
   - Qué pasa y dónde (`fichero:línea`).
   - La prueba: comando ejecutado y salida real, recortada. Sin prueba no hay issue: un hallazgo
     que no se pudo comprobar va al resumen como "sin verificar", no a GitHub.
   - Causa raíz y arreglo propuesto.
   - **Criterio de aceptación**: qué test de regresión lo demuestra (falla hoy, pasa tras el
     arreglo).
   - Por qué es `autonomo` o `decision`. Zona caliente, cambio de dependencias mayores,
     migraciones de datos, despliegue y borrados siempre son `decision`.
6. **Marca la rotación**: `python "${CLAUDE_SKILL_DIR}/scripts/pick.py" marcar <repo>`.
7. **Resumen final**, corto: repo auditado, issues creados con su enlace y etiqueta, hallazgos
   sin verificar, y la verificación de `main` (pasa o no, y tiempo).

## Modo `arreglar`

Un solo issue por ejecución: el de arriba. Si el script dice "NADA QUE ARREGLAR", se dice y se
termina.

1. **Lee el issue entero** (`gh issue view <n> -R <slug> --comments`). Si un comentario de la
   persona cambia el plan o lo para, manda el comentario.
2. **Rama y worktree propios** desde `origin`, nunca desde la copia local:
   `git -C <ruta> fetch --prune` y `git -C <ruta> worktree add -b claude/audit-<n>-<slug-corto>
   <ruta>/.claude/worktrees/audit-<n> origin/<rama-por-defecto>`. Todo lo que sigue se hace
   dentro de ese worktree.
3. **Lee el `CLAUDE.md` del repo** y sus reglas. Si el arreglo tiene que tocar un fichero de una
   zona caliente, para: comenta en el issue qué fichero y por qué, cambia la etiqueta a
   `audit-decision` y termina.
4. **Verificación antes de tocar nada**: el comando de `.claude/verify-command`. Si ya está en
   rojo, el issue no se puede comprobar: comenta la salida en el issue y termina.
5. **Test de regresión primero.** Escribe el test del criterio de aceptación y córrelo: tiene que
   fallar, y por el motivo del issue. Guarda la salida. Si pasa sin arreglo, el issue no se
   reproduce: coméntalo con la salida y termina, sin PR.
6. **Arreglo mínimo.** Lo que pide el issue y nada más: sin refactors de paso ni otros arreglos
   que se vean por el camino (esos, como mucho, un comentario en el issue). Después, el test de
   regresión en verde y la verificación completa en verde. Ruff en lo que se toque, si el repo es
   Python.
7. **Segunda opinión.** Lanza el subagente `verifier` con el diff y el criterio de aceptación del
   issue. Su veredicto va tal cual al cuerpo del PR; si refuta el arreglo, el PR se abre igual en
   draft pero el título empieza por `[refutado]`, para que no se pase a listo sin mirarlo.
8. **Commit y PR en draft.** Ficheros explícitos (nunca `git add -A`), conventional commit con
   scope en el idioma del repo, con su línea `Co-Authored-By`. `git push -u origin <rama>` (el
   hook `pre-push-verify` vuelve a verificar; si bloquea, se arregla, no se rodea) y
   `gh pr create --draft --title ... --body-file ...`. El cuerpo lleva: `Closes #<n>`, qué se
   cambió y por qué, la salida del test fallando antes y pasando después, la verificación, el
   veredicto del `verifier` y la línea de "Generated with Claude Code".
9. **Recoge**: `git -C <ruta> worktree remove` del worktree (la rama sigue en el remoto con su
   PR). Nunca `gh pr ready`, nunca `gh pr merge`.
10. **Resumen final**, corto: issue, enlace del PR draft, resultado del test antes y después,
    verificación, veredicto del `verifier`.

## Si falla a medias

Lo que quede a medias se deja visible, no se limpia en silencio: si hay rama con commits sin PR,
se dice en el resumen con el nombre de la rama. Nunca se borra una rama sin fusionar.
