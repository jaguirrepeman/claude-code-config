---
name: mejora
description: Mejora continua programada de los repos. `auditar` audita el repo al que le toca turno y convierte los hallazgos en issues; `arreglar` coge el issue `audit-autonomo` o `audit-revision` más grave, lo arregla con su test de regresión y abre un PR (listo si es autónomo, para que lo fusione el gate; en draft si necesita un vistazo). Úsala solo cuando la pida explícitamente `/mejora` o una tarea programada que la nombre; "mejora este código" en una sesión normal no es esto.
user-invocable: true
argument-hint: auditar|arreglar [--root carpeta] [--donde pc|nube] [--repos a,b] [--max-drafts N]
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/pick.py *)
---

# /mejora: auditar a issues, arreglar a PR

Corre sin nadie delante. Por eso hay tres reglas que no se negocian, y mandan sobre cualquier
otra cosa de este fichero:

1. **El PR sale listo solo si el issue es `audit-autonomo`.** En estos repos un PR que no es
   draft lo fusiona el gate (solo en verde) y despliega a producción, con su health check. Eso
   es lo que se quiere para los arreglos claros: que lleguen solos, sin que la persona mire
   (decidido el 2026-11-27). Todo lo demás (issue `audit-revision`, un diff que acaba tocando
   una zona caliente, un intento de refutación que no queda limpio) va en draft. El robot nunca
   ejecuta `gh pr merge`, nunca toca `main` y nunca despliega a mano: fusiona el gate.
2. **Ante la duda, para y deja constancia.** Si algo no cuadra (verificación en rojo antes de
   tocar nada, issue ambiguo, el arreglo toca una zona caliente, falta una herramienta), no se
   improvisa: se comenta en el issue lo que se vio, con la salida real, y se termina el turno.
3. **Todo en primer plano, en un solo turno.** Una ejecución programada acaba cuando acaba tu
   turno, y nada la vuelve a despertar. Así que nada de subagentes (la herramienta Agent los
   lanza en segundo plano) ni de comandos con `run_in_background`, y nunca se cierra el turno
   "esperando" algo. Los comandos largos (la verificación de un repo) van con `timeout: 600000`,
   para que la herramienta Bash no los pase sola a segundo plano a los dos minutos. Medido el
   2026-11-01: la auditoría de atril lanzó `repo-auditor` en segundo plano, cerró el turno a los
   tres minutos y la ejecución terminó sin crear ningún issue, con el subagente aún trabajando.
   Esta sesión ya es un contexto limpio dedicado solo a esto: no hace falta otro.

Modo pedido: `$ARGUMENTS` (la primera palabra es `auditar` o `arreglar`).

## Qué toca (automático)

```!
python "${CLAUDE_SKILL_DIR}/scripts/pick.py" $ARGUMENTS || true
```

Usa el repo, la ruta y el issue de arriba. No elijas otro por tu cuenta. Si dice `DÓNDE: nube`
y no da repo ni issue, es que este PC ya ha pasado hace poco o no hay nada: se dice y se termina.

## GitHub, siempre por REST

En la nube el proxy rechaza `gh issue` y `gh pr` (van por GraphQL); `gh api` sí pasa. Para que
haya un solo camino, se usa `gh api` también en el PC. Los cuerpos van en un fichero UTF-8 y se
pasan con `-F body=@fichero.md`.

| Para | Comando |
|---|---|
| Leer un issue y sus comentarios | `gh api repos/<slug>/issues/<n>` y `gh api repos/<slug>/issues/<n>/comments` |
| Listar issues `audit` | `gh api "repos/<slug>/issues?labels=audit&state=all&per_page=100"` (quita los que tengan `pull_request`) |
| Crear un issue | `gh api repos/<slug>/issues -f title=... -F body=@f.md -f "labels[]=audit" -f "labels[]=P2"` |
| Comentar | `gh api repos/<slug>/issues/<n>/comments -F body=@f.md` |
| Cambiar etiquetas | `gh api -X POST repos/<slug>/issues/<n>/labels -f "labels[]=..."` y `gh api -X DELETE repos/<slug>/issues/<n>/labels/<etiqueta>` |
| Crear una etiqueta | `gh api repos/<slug>/labels -f name=... -f color=... -f description=...` (un 422 es que ya existe) |
| Abrir el PR | `gh api repos/<slug>/pulls -f title=... -F body=@f.md -f head=<rama> -f base=<rama-por-defecto> -F draft=true` (`draft=false` si sale listo) |

## Etiquetas

Todas en ASCII, para que `gh` no dependa de la codificación de la consola. Antes del primer
issue en un repo, créalas si faltan (tabla de arriba):

| Etiqueta | Para qué |
|---|---|
| `audit` | Todo issue que abre esta skill |
| `audit-autonomo` | Lo arregla el robot y se fusiona solo: bug claro, lint, higiene, test que falta, fuera de zonas calientes |
| `audit-revision` | Lo arregla el robot, pero el PR va en draft para un vistazo: arreglo en zona caliente, o una elección pequeña de producto en la que el robot aplica su opción recomendada |
| `audit-decision` | Decisión gorda, el robot no la toca: borrar o migrar datos, infraestructura viva, despliegue o gate del CI, credenciales, dinero o cuota, dependencias mayores, un cambio de producto con consecuencias que no se deshacen |

La persona quiere el máximo de autonomía: **ante la duda entre dos niveles, el menos
restrictivo que no sea irreversible**. Una elección de producto pequeña y reversible (cómo
repartir una sesión entre dos días, qué hacer con dos pantallas abiertas) es `audit-revision`
con la opción recomendada escrita en el issue, no `audit-decision`.
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
3. **Auditoría, hecha por ti en esta sesión** (regla 3: sin subagente). Sobre esa copia, con la
   lista de "Qué revisar" y "Cómo verificar cada hallazgo" de la skill `/audit` (léela en
   `~/.claude/skills/audit/SKILL.md`) y la forma de trabajar de `~/.claude/agents/repo-auditor.md`
   (leer antes de grepear, citar `fichero:línea`, distinguir "es" de "parece"). Saca la tabla de
   criticidad. Corre además la verificación del repo una vez y apunta cuánto tarda y si pasa: un
   `main` en rojo es un `P0`.
4. **Sin duplicados.** Lista los issues `audit` del repo (tabla de arriba). Un
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
   - Por qué es `autonomo`, `revision` o `decision`, según la tabla de etiquetas. Un fichero de
     zona caliente es como mínimo `revision`. Migraciones de datos, borrados, despliegue, gate
     del CI, credenciales y dependencias mayores siempre son `decision`. Si es `revision` por una
     elección de producto, el issue dice qué opción aplicará el robot y por qué.
6. **Marca la rotación**: `python "${CLAUDE_SKILL_DIR}/scripts/pick.py" marcar <repo> --root
   <la misma carpeta de arriba>` (apunta en GitHub, que es lo que ven el PC y la nube).
7. **Resumen final**, corto: repo auditado, issues creados con su enlace y etiqueta, hallazgos
   sin verificar, y la verificación de `main` (pasa o no, y tiempo).

## Modo `arreglar`

Un solo issue por ejecución: el de arriba. Si el script dice "NADA QUE ARREGLAR", se dice y se
termina.

1. **Lee el issue entero**, con sus comentarios (tabla de arriba). Si un comentario de la
   persona cambia el plan o lo para, manda el comentario.
2. **Rama y worktree propios** desde `origin`, nunca desde la copia local:
   `git -C <ruta> fetch --prune` y `git -C <ruta> worktree add -b claude/audit-<n>-<slug-corto>
   <ruta>/.claude/worktrees/audit-<n> origin/<rama-por-defecto>`. Todo lo que sigue se hace
   dentro de ese worktree.
3. **Lee el `CLAUDE.md` del repo** y sus reglas, incluidas las de zona caliente (siguen
   valiendo: test con fixtures, un solo parser, lo que digan). El modo del PR sale de `pick.py`
   (`PR: listo` o `PR: draft`). Si un issue `audit-autonomo` acaba tocando un fichero de zona
   caliente, se sigue, pero el PR pasa a draft y el cuerpo dice qué fichero y por qué. Si el
   arreglo exige algo de la fila `audit-decision` (migrar datos, tocar el gate o el despliegue,
   borrar), para: comenta en el issue, cambia la etiqueta a `audit-decision` y termina.
4. **Verificación antes de tocar nada**: el comando de `.claude/verify-command`. Si ya está en
   rojo, el issue no se puede comprobar: comenta la salida en el issue y termina.
5. **Test de regresión primero.** Escribe el test del criterio de aceptación y córrelo: tiene que
   fallar, y por el motivo del issue. Guarda la salida. Si pasa sin arreglo, el issue no se
   reproduce: coméntalo con la salida y termina, sin PR.
6. **Arreglo mínimo.** Lo que pide el issue y nada más: sin refactors de paso ni otros arreglos
   que se vean por el camino (esos, como mucho, un comentario en el issue). Después, el test de
   regresión en verde y la verificación completa en verde. Ruff en lo que se toque, si el repo es
   Python.
7. **Intento de refutación, en esta sesión** (regla 3: sin subagente). Sigue el método de
   `~/.claude/agents/verifier.md` contra tu propio diff y el criterio de aceptación del issue:
   relee el diff entero buscando lo que rompe, comprueba el criterio por un camino distinto al del
   test que escribiste y busca usos del código tocado que el test no cubre. No es una revisión
   independiente, porque la hace quien escribió el arreglo, y el PR lo dice así; la independiente
   es el gate del CI y, en draft, la persona. Si encuentras un fallo que no sabes cerrar, el PR
   se abre en draft (aunque tocara listo) y el título empieza por `[refutado]`.
8. **Commit y PR.** Ficheros explícitos (nunca `git add -A`), conventional commit con
   scope en el idioma del repo, con su línea `Co-Authored-By`. `git push -u origin <rama>` (el
   hook `pre-push-verify` vuelve a verificar; si bloquea, se arregla, no se rodea) y
   abre el PR por REST (tabla de arriba), en draft salvo que el modo sea `listo` y el
   paso 3 y el 7 no lo hayan bajado a draft. El cuerpo lleva: `Closes #<n>`, qué se
   cambió y por qué, la salida del test fallando antes y pasando después, la verificación, lo que
   salió del intento de refutación (marcado "no independiente") y la línea de "Generated with
   Claude Code".
9. **Recoge**: `git -C <ruta> worktree remove` del worktree (la rama sigue en el remoto con su
   PR). Nunca `gh pr ready` sobre un draft, nunca `gh pr merge`: fusiona el gate.
10. **Resumen final**, corto: issue, enlace del PR y si salió listo o en draft (y por qué),
    resultado del test antes y después,
    verificación, resultado del intento de refutación.

## Si falla a medias

Lo que quede a medias se deja visible, no se limpia en silencio: si hay rama con commits sin PR,
se dice en el resumen con el nombre de la rama. Nunca se borra una rama sin fusionar.
