# Optimización del entorno Claude Code (septiembre de 2026)

Auditoría de cómo están montados para Claude Code los cuatro repos (`claude-code-config`,
`finance`, `atril`, `idealista_bot`), contrastada con la documentación oficial vigente en
septiembre de 2026. Cada hallazgo lleva su evidencia (fichero, comando o cifra) y cada
recomendación su fuente. Al final: qué se aplicó en esta tanda y qué queda pendiente de una
decisión que no es de configuración sino de producción o de cuota.

Método: lectura completa de los `CLAUDE.md`, `.claude/`, `.gitignore`, hooks, skills, agentes,
snippets de settings y workflows de CI de los cuatro repos, más el log de git; y lectura de las
páginas oficiales listadas en la sección 8. Lo que no se pudo ejecutar en esta sesión (no había
Claude Code interactivo ni acceso a la Pi) está marcado "sin verificar".

## 1. Resumen ejecutivo

- **La base está bien.** `claude-code-config` ya aplica lo que la documentación recomienda:
  `CLAUDE.md` corto y verificable (124 líneas), hooks deterministas que fallan abiertos,
  permisos con `ask` en lo que sale de la máquina, skills solo para procedimientos repetidos y
  un documento de porqués. Los tres repos de proyecto tienen `CLAUDE.md` con comandos de
  verificación y CI con gate.
- **Lo que faltaba era la mitad "determinista" de la verificación.** Las reglas de verificación
  vivían solo en `CLAUDE.md` (instrucción, no garantía). Ahora hay un hook que exige la
  verificación del repo antes de cada `git push`, tests para los cuatro hooks y CI en el propio
  repo de configuración.
- **La "IA como validador" estaba descrita pero no montada.** `ways-of-working.md` 5.2 define
  el revisor independiente; no existía la pieza. Ahora: subagente `verifier` y skill `/refute`,
  siguiendo el patrón "adversarial review" de la documentación oficial.
- **Tres repos de proyecto no declaraban zonas calientes ni versionaban `.claude/`.**
  `idealista_bot` además ignoraba `.claude/` entero en `.gitignore`, el antipatrón que
  `ways-of-working.md` 2.2 describe. Corregido con reglas por ruta (`paths:`), `settings.json`
  de proyecto y `verify-command`.
- **Contradicciones documentales.** `finance/WORKFLOW.md` mandaba `gh pr merge --auto`, que su
  propio `CLAUDE.md` prohíbe. Corregido. Los `CLAUDE.md` de los tres proyectos incumplían la
  regla de texto global (em-dashes). Corregido.
- **Multiagente: no cambiar de modelo.** Para repos de una persona, la combinación correcta es
  subagentes (investigar, verificar) más sesiones paralelas en worktrees. Los agent teams son
  experimentales, están apagados por defecto y "use significantly more tokens"; solo compensan
  para depurar con hipótesis en competencia o revisar un PR por varias lentes a la vez.
- **Pendiente de decisión (no de configuración):** job `auto-merge` en `atril` (un merge
  despliega), revisión automática de PR con la GitHub Action (gasta cuota por PR), ruff en el CI
  de `atril` e `idealista_bot`, y borrar o documentar los `.githooks/` de `finance`.

## 2. Estado de partida, pieza por pieza

| Pieza | claude-code-config | finance | atril | idealista_bot |
|---|---|---|---|---|
| `CLAUDE.md` | 124 líneas, importa `machine.md` | 126 líneas | 45 líneas | 93 líneas |
| `.claude/` versionado | n/a (es el repo de `~/.claude`) | no existía | no existía | no existía, y `.gitignore` lo ignoraba entero |
| Zonas calientes declaradas | pide que cada repo las declare | no | nombradas en prosa (`chordpro.py`, `aligner.py`) | nombradas en prosa (`nlp_extractor.py`, `valuation.py`) |
| Hooks | 3 globales (sesión, commit en protegida, lint) | `.githooks/` de git (no de Claude Code), sin documentar | ninguno | ninguno |
| Skills | `audit`, `deploy-pi` | ninguna | ninguna | ninguna |
| Subagentes | `repo-auditor` | ninguno | ninguno | ninguno |
| CI | ninguno | pytest, ruff, contrato OpenAPI, vitest+tsc, gitleaks, `auto-merge` | pytest, vitest+tsc; **sin `auto-merge`** | pytest, tsc+build, `auto-merge`; **sin ruff** |
| Despliegue | n/a | webhook, rollback | webhook, rollback | manual por SSH |
| Tests | ninguno para los hooks | 84 ficheros | 17 | 28 |
| Ficheros de plan | n/a | `PLAN_INTEGRACION.md` (27 KB), `next_steps.md` | `PLAN_PIANO_SHEETS.md` (20 KB) | `docs/PLAN_FRONTEND.md`, `docs/BACKLOG.md`, `next_steps.md` |

## 3. Hallazgos con evidencia

Severidad: **P1** cambia el comportamiento de las sesiones o deja pasar código roto; **P2**
inconsistencia que acabará causando un error; **P3** higiene. "Aplicado" significa en esta
tanda, en la rama `claude/optimize-claude-code-repo-3dunjq` de cada repo.

### 3.1 claude-code-config

| # | Hallazgo | Evidencia | Sev. | Estado |
|---|---|---|---|---|
| C1 | Sin hook que exija la verificación antes de que el código salga. La regla "ruff y pytest antes de cada push" era solo instrucción | `CLAUDE.md`, sección "Comprobaciones antes de pushear"; README, "Lo que falta", punto 2 | P1 | Aplicado: `hooks/pre-push-verify.py` |
| C2 | Los hooks no tenían tests ni CI, mientras el propio `CLAUDE.md` exige test de regresión para todo. Un hook roto cambia todas las sesiones de todas las máquinas | `git ls-files` no mostraba tests ni `.github/` | P1 | Aplicado: `hooks/tests/test_hooks.py` (17 tests, 17 en verde) y `.github/workflows/ci.yml` |
| C3 | El revisor independiente de `ways-of-working.md` 5.2 no existía como pieza; había que pedirlo con una frase distinta cada vez | no había `agents/verifier.md` ni skill | P1 | Aplicado: `agents/verifier.md` + `skills/refute/`. **Sin verificar en vivo** (esta sesión no tiene Claude Code interactivo); los tests cubren solo los hooks |
| C4 | `hooks/__pycache__/*.pyc` (3 ficheros, CPython 3.14) versionados; no había `.gitignore` | `git ls-files \| grep pycache` = 3 | P3 | Aplicado: `.gitignore` y `git rm --cached` |
| C5 | `/deploy-pi` podía invocarla el modelo por su cuenta. La documentación pide `disable-model-invocation: true` "for workflows with side effects (deploy, commit)" | `skills/deploy-pi/SKILL.md`, frontmatter | P2 | Aplicado |
| C6 | La regla `deny` `Bash(gh pr merge --auto:*)` no cazaba `gh pr merge 12 --auto`: el `--auto` puede ir en cualquier posición | permissions.md: "Wildcards with `*` match at any position" | P2 | Aplicado: `Bash(gh pr merge *--auto*)` |
| C7 | Instalación por copia manual sin forma de saber si `~/.claude` y el repo han divergido | README, sección de instalación | P3 | Aplicado: `install.sh` con `--check` (probado contra un `HOME` temporal: sin drift sale 0, con drift lista `DIFIERE`/`FALTA` y sale 1) |
| C8 | Sin plantilla de `.claude/` para un repo nuevo: cada proyecto lo montaba distinto (y tres no lo montaban) | sección 2 de este documento | P2 | Aplicado: `templates/project/` |

### 3.2 finance

| # | Hallazgo | Evidencia | Sev. | Estado |
|---|---|---|---|---|
| F1 | `WORKFLOW.md` regla 5 manda `gh pr create --fill` + `gh pr merge --auto`; `CLAUDE.md` dice "No ejecutes `gh pr merge --auto`" y que si un documento choca con él, "arregla el otro en el mismo PR" | `WORKFLOW.md:24-27` frente a `CLAUDE.md`, sección "Cómo llega un cambio a producción" | P1 | Aplicado: regla 5 reescrita |
| F2 | Zonas calientes sin declarar, con el `CLAUDE.md` global diciendo "Cada repo dice cuáles son sus zonas calientes" | `finance/CLAUDE.md` no contiene "zona caliente" | P2 | Aplicado: `.claude/rules/zonas-calientes.md` con `paths:` sobre `backend/app/services/**` y `api/endpoints.py` |
| F3 | `.githooks/pre-commit` y `pre-push` corren una lista blanca de 3 y 4 ficheros de test, el patrón que el propio `ci.yml` abandonó ("lista blanca que había que mantener a mano y se quedaba desactualizada"); requieren `git config core.hooksPath .githooks`, que ningún documento menciona; y abortan el commit si no hay Poetry | `.githooks/*`, `ci.yml` comentario del job `backend-tests`; `grep hooksPath` en README, WORKFLOW, CLAUDE.md, docs = 0 | P2 | **Pendiente de decisión**: borrarlos (recomendado; `verify-command` + CI los sustituyen) o documentar `core.hooksPath` |
| F4 | ESLint fuera del gate con 37 errores reales conocidos | `ci.yml`, comentario "PENDIENTE" en `frontend-build` | P2 | Pendiente: tarea de código, no de configuración. Hacerla en una sesión en la nube, que sí tiene Node (ver 5.6) |
| F5 | `.claude/` sin versionar; sin `settings.json` de proyecto ni `verify-command` | `ls .claude` = no existe | P2 | Aplicado |
| F6 | 8 em-dashes en `CLAUDE.md` contra la regla de texto global | `grep -c` del em-dash en `CLAUDE.md` = 8 | P3 | Aplicado |
| F7 | `WORKFLOW.md` "Fontanería pendiente" (dos remotos, `gh` sin autenticar) puede estar obsoleto: los PR #139 a #152 se fusionaron por el CI | `git log --oneline -12` | P3 | Sin verificar (depende de la máquina local); revisar y borrar la sección si ya no aplica |

### 3.3 atril

| # | Hallazgo | Evidencia | Sev. | Estado |
|---|---|---|---|---|
| A1 | Sin job `auto-merge`: los PR se fusionan a mano y con merge commit, contra "squash para lo que se borra, merge para lo que se queda" | `ci.yml` solo tiene `backend` y `frontend`; `git log --merges` muestra "Merge pull request #16", "#15", "#14"... | P2 | **Pendiente de decisión**: añadir el job (YAML listo en 6.1). Un merge despliega en la Pi, así que activarlo es una decisión de producción |
| A2 | Zonas calientes nombradas en prosa (`chordpro.py`, `aligner.py`) pero sin regla por ruta | `CLAUDE.md` regla 3 | P2 | Aplicado: `.claude/rules/zonas-calientes.md` |
| A3 | Sin ruff, ni configuración ni CI | `grep tool.ruff backend/pyproject.toml` = nada | P3 | Pendiente: añadir `[tool.ruff]` con el conjunto corto de `finance` (E, W, F, I, B) y un job; primero medir cuántos avisos saca |
| A4 | `.claude/` sin versionar; `.gitignore` sin entradas de Claude Code | `ls .claude` = no existe | P2 | Aplicado |
| A5 | 1 em-dash en `CLAUDE.md` | `grep -c` = 1 | P3 | Aplicado |

### 3.4 idealista_bot

| # | Hallazgo | Evidencia | Sev. | Estado |
|---|---|---|---|---|
| I1 | `.gitignore` ignora `.claude/` entero: todo lo que se cree ahí (settings, reglas, skills) queda fuera de git en silencio y cada máquina diverge. Es el antipatrón que `ways-of-working.md` 2.2 describe con su corrección | `.gitignore:30-31` | P1 | Aplicado: se ignora solo `settings.local.json`, `worktrees/` y `CLAUDE.local.md` |
| I2 | Zonas calientes en prosa (`nlp_extractor.py`, `valuation.py`, `rate_limit.py`) sin regla por ruta | `CLAUDE.md`, "Reglas de código" | P2 | Aplicado: `.claude/rules/zonas-calientes.md` |
| I3 | Sin ruff ni configuración; el CI solo corre pytest y el build del frontend | `pyproject.toml` sin `[tool.ruff]`; `tests.yml` | P3 | Pendiente, igual que A3 |
| I4 | 13 em-dashes en `CLAUDE.md` | `grep -c` = 13 | P3 | Aplicado |
| I5 | `scripts/test_*.py` (scraper, uc, images) son diagnósticos con nombre de test fuera de `tests/`; pytest no los recoge porque el CI lanza `pytest tests/` explícito, pero un `pytest` a secas desde la raíz sí los intentaría | `ls scripts` | P3 | Pendiente: renombrar a `probe_*.py` o `check_*.py` como los vecinos |

### 3.5 Transversal

| # | Hallazgo | Evidencia | Sev. | Estado |
|---|---|---|---|---|
| T1 | La explicación del gate de `auto-merge` (repo privado Free, sin branch protection, draft para retener) está en cuatro sitios: `machines/personal.md`, `finance/CLAUDE.md`, `finance/docs/METODOLOGIA.md`, `idealista_bot/CLAUDE.md`. "Una regla, un sitio" también vale para las instrucciones: la documentación avisa de que "if two rules contradict each other, Claude may pick one arbitrarily" | `grep -l "auto-merge"` | P3 | Pendiente: dejar el porqué en `METODOLOGIA.md` y en cada `CLAUDE.md` solo la regla de dos líneas con el enlace |
| T2 | Los planes grandes existen (`PLAN_INTEGRACION.md`, `PLAN_PIANO_SHEETS.md`, `PLAN_FRONTEND.md`) pero sin convención de sitio ni de estructura, y con estados de tarea mezclados con el plan | raíz de `finance` y `atril`, `docs/` en `idealista_bot` | P3 | Recomendación en 5.4 |

## 4. Qué dice la documentación oficial y cómo encaja

### 4.1 CLAUDE.md y reglas por ruta

- Tamaño: "target under 200 lines per CLAUDE.md file. Longer files consume more context and
  reduce adherence" (memory.md). Los cuatro cumplen; el mayor es `finance` con 126.
- Qué incluir: "Bash commands Claude can't guess", "Repository etiquette", "Common gotchas";
  qué no: "Anything Claude can figure out by reading code", "File-by-file descriptions"
  (best-practices.md). `finance/CLAUDE.md` lleva un árbol de directorios de 12 líneas: es
  candidato a recorte, pero cada línea explica un porqué ("TODA la lógica de cálculo",
  "NO editar a mano"), así que se deja. `/doctor` "proposes trims for a checked-in CLAUDE.md"
  (memory.md); pasarlo una vez por repo es barato.
- Reglas por ruta: `.claude/rules/*.md` con `paths:` "only load into context when Claude works
  with matching files" y "trigger when Claude reads files matching the pattern" (memory.md).
  Es la forma de declarar zonas calientes sin engordar el `CLAUDE.md`, y es lo aplicado en los
  tres repos. Detalle que importa: sobreviven a la compactación al releer un fichero que casa,
  mientras que una instrucción dada solo en conversación se pierde ("Instructions seem lost
  after `/compact`", memory.md).
- Consistencia: `finance` tiene `.cursorrules` y `.github/copilot-instructions.md` convertidos
  en punteros a `CLAUDE.md`. Correcto: la documentación dice que `/init` lee ambos y los
  incorpora, y tener dos juegos de reglas es lo que provocó los módulos fantasma que esos
  ficheros aún recuerdan.
- `CLAUDE.local.md` (gitignored) es el sitio para preferencias personales por repo; ninguno lo
  usa y no hace falta mientras `machine.md` cubra lo de la máquina. Queda en la plantilla de
  `.gitignore` para que no acabe versionado por accidente.

### 4.2 Skills

- Frontmatter que importa aquí: `disable-model-invocation: true` "for workflows with side
  effects (deploy, commit)"; `context: fork` para correr "in isolation without conversation
  history" con `agent:` para elegir el subagente; `paths` para activar una skill solo en ciertos
  ficheros (skills.md). Aplicado: `deploy-pi` pasa a invocación manual; `refute` corre en fork
  con el agente `verifier`.
- Coste: "Once a skill loads, its content stays in context across turns, so every line is a
  recurring token cost" (skills.md). Las tres skills del repo tienen 40 a 60 líneas; bien.
- Inyección `` !`comando` ``: "Any non-zero exit code aborts the entire skill invocation";
  `grep`, `git diff` con exit 1 se toleran, 2 o más no; "Append `|| true` to commands you expect
  to exit non-zero" (skills.md). `audit`, `deploy-pi` y `refute` lo cumplen.
- Skills incluidas que ya cubren cosas que se pedían a mano: `/code-review` (revisión del diff
  "in a fresh subagent"), `/simplify`, `/security-review`, `/verify` ("Build and run your app to
  confirm a code change does what it should"; escribe la receta que le funcionó en
  `.claude/skills/verify/SKILL.md`), `/batch` (reparte un cambio en 5 a 30 subagentes, cada uno
  en su worktree y con su PR), `/doctor`, `/insights`, `/fewer-permission-prompts`.
- Criterio de admisión del README (tres repeticiones con evidencia): `refute` entra porque la
  revisión con contexto limpio ya era regla escrita (ways-of-working 5.1 y 5.2) y se pedía con
  una frase distinta cada vez; las candidatas descartadas siguen descartadas.

### 4.3 Hooks

- "Use hooks for actions that must happen every time with zero exceptions. Unlike CLAUDE.md
  instructions which are advisory, hooks are deterministic" (best-practices.md). Es el criterio
  de `ways-of-working.md` 7 y el que justifica `pre-push-verify`.
- Códigos de salida: "exit code 2 is the only exit code that blocks through the code alone";
  exit 1 sin JSON "is a non-blocking error and proceeds with the action" (hooks.md). Los hooks
  de este repo deciden por JSON (`permissionDecision: deny`) y salen siempre con 0, que es la
  forma explícita y la que no depende de ese matiz.
- `PostToolUse`: el stdout suelto no llega al modelo; `SessionStart` sí ("Claude Code adds
  plain-text stdout as context"). Es lo que ya hace `lint-check` (`additionalContext`) y
  `session-start-status` (stdout). Confirmado.
- Novedades útiles: el campo `if` con sintaxis de permisos (`"if": "Bash(git push *)"`) evita
  lanzar el proceso en cada comando; no se aplica todavía porque `Bash(git push *)` no casaría
  `git -C ruta push` y el hook ya filtra por regex en milisegundos. `once: true` solo vale en
  hooks de skill. Los hooks de tipo `agent` y `prompt` permiten un `Stop` hook con criterio
  (hooks.md); sigue descartado por el coste por turno medido (ways-of-working 7).
- `Stop` como gate: "blocks the turn from ending until it passes. Claude Code overrides the hook
  and ends the turn after 8 consecutive blocks" (best-practices.md). Confirma el límite que
  `ways-of-working.md` 7 daba como "se rinde y deja cerrar".

### 4.4 Planes y plan mode

- "If you could describe the diff in one sentence, skip the plan"; planificar "when the change
  modifies multiple files, or when you're unfamiliar with the code" (best-practices.md). Es la
  regla actual del `CLAUDE.md` global.
- `Ctrl+G` abre el plan en el editor antes de aprobarlo. Para una feature grande, "have Claude
  interview you first" con `AskUserQuestion` y "write a complete spec to SPEC.md", y ejecutar
  en una sesión nueva: "The new session has clean context focused entirely on implementation"
  (best-practices.md). Encaja con "El plan de un cambio grande se escribe en un fichero".
- Recomendación (T2): convención `docs/plans/<fecha>-<tema>.md` con las cuatro partes del
  `CLAUDE.md` global (objetivo, criterio de aceptación, ficheros que se tocan, qué se decide no
  hacer) más un paso final de verificación de extremo a extremo ("end with an end-to-end
  verification step that proves the feature works"). Los estados de tareas (`next_steps.md`,
  `BACKLOG.md`) quedan aparte: un plan se ejecuta y se archiva; un backlog cambia cada semana.
  No se aplica en esta tanda porque mover `PLAN_*.md` es reescribir historia de otros PR.

### 4.5 Verificación y la IA como validador

La documentación lo formula como escalera, y coincide con la de `ways-of-working.md` 5.2:

| Escalón | Documentación | Estado en estos repos |
|---|---|---|
| Criterio en el prompt | "ask Claude to run the check and iterate in the same message" | Regla del `CLAUDE.md` global |
| Condición de objetivo | `/goal`: "a separate evaluator re-checks it after every turn" | Disponible; se usa en tareas largas desatendidas |
| Gate determinista | Stop hook (descartado por coste) o, en su lugar, hook en el push | **Aplicado**: `pre-push-verify` |
| Segunda opinión | "a verification subagent [...] has a fresh model try to refute the result, so the agent doing the work isn't the one grading it" | **Aplicado**: `verifier` + `/refute` |

Tres matices oficiales que el agente `verifier` incorpora tal cual:

1. "A reviewer prompted to find gaps will usually report some, even when the work is sound [...]
   Tell the reviewer to flag only gaps that affect correctness or the stated requirements, and
   treat the rest as optional." Por eso el informe separa "Fallos" de "Opcional".
2. "Have Claude show evidence rather than asserting success: the test output, the command it ran
   and what it returned." Por eso cada afirmación lleva comando y salida.
3. `/code-review` cubre la corrección del diff; el prompt propio sirve para comprobar "the diff
   against your plan". `/refute` recibe el criterio como argumento por ese motivo.

Fuera de la sesión hay dos validadores más:

- **El CI con `auto-merge`** ya es un validador determinista; es el mejor de todos porque no
  depende de que nadie se acuerde. `atril` no lo tiene (A1).
- **Revisión automática de cada PR con la Claude Code GitHub Action** (`/install-github-app`,
  workflow de ejemplo en github-actions.md con `/code-review:code-review --comment`). Coste: "each
  interaction consumes tokens based on the length of prompts and responses, task complexity, and
  codebase size"; con token OAuth "runs use your Claude subscription". Mitigaciones oficiales:
  `--max-turns`, timeouts de workflow, `CLAUDE.md` corto, saltar drafts. Es un gasto de cuota por
  PR (incluidos los de dependabot en `finance`, que son la mayoría de los últimos merges): queda
  como decisión, con la recomendación de activarlo primero solo en `finance` y solo en
  `ready_for_review`, y medir un mes.

### 4.6 Desarrollo multiagente

Tres mecanismos distintos, con un criterio claro para cada uno:

| Mecanismo | Cuándo | Coste | Fuente |
|---|---|---|---|
| **Subagentes** (Explore, Plan, `repo-auditor`, `verifier`) | Investigar sin llenar el contexto; verificar sin el sesgo de quien escribió; tareas con salida voluminosa que solo necesitan un resumen | "Lower: results summarized back to main context" | sub-agents.md |
| **Sesiones paralelas en worktrees** (`claude --worktree`, `EnterWorktree`) | Dos tareas independientes a la vez; patrón escritor/revisor entre dos sesiones ("A fresh context improves code review since Claude won't be biased toward code it just wrote") | Una sesión por tarea | best-practices.md, common-workflows.md |
| **Agent teams** (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) | Depurar con hipótesis en competencia ("have them talk to each other to try to disprove each other's theories"), revisar un PR por varias lentes, módulos separados por persona | "significantly more tokens than a single session"; experimental; sin `/resume` de teammates; "teams can form even when you didn't ask for one" al nombrar subagentes | agent-teams.md |

Recomendación: **mantener los teams apagados** en `~/.claude/settings.json` y activarlos por
sesión, a mano, para los dos casos donde aportan. Para el resto, subagentes y worktrees, que ya
son la regla de `ways-of-working.md` 2.4 y 6.3. Antes de lanzar cualquier cosa que multiplique
sesiones (teams, `/batch`, un deep research), estimar cuota y preguntar, que es además una
preferencia declarada del usuario.

Un caso concreto de esta familia que sí conviene adoptar: **sesiones en la nube para el
frontend**. La máquina personal no tiene Node (`machines/personal.md`), así que el TypeScript se
valida "en CI o en la Pi". Una sesión de Claude Code en la nube sí tiene Node (esta misma corre
Node 22), con lo que `npm run lint`, `npm test` y `npm run build` se verifican antes del PR. Es
el sitio natural para F4 (los 37 errores de ESLint).

### 4.7 Permisos y modos

- Evaluación: "deny, then ask, then allow. The first match in that order determines the outcome"
  (permissions.md). El snippet sigue ese diseño.
- Comandos compuestos: "a rule like `Bash(safe-cmd *)` won't give it permission to run the
  command `safe-cmd && other-cmd`" y "Deny and ask rules apply when any subcommand matches"
  (permissions.md). Por eso `ask` sobre `git push` se dispara también dentro de
  `pytest && git push`; el hook de push no depende de esto (usa regex), pero se apoya en ello.
- `Read`/`Edit` usan sintaxis gitignore; `Read(.env)` y `Read(**/.env)` son equivalentes
  (permissions.md). El snippet tiene ambas formas: redundante, no incorrecto.
- `defaultMode` `auto` y `bypassPermissions` "don't take effect from project or local settings"
  (settings.md): el modo es de usuario, como dice `ways-of-working.md` 2.3.
- `.claude/settings.local.json` "Claude Code keeps it out of git when it creates the file; if you
  create it by hand, add it to `.gitignore` yourself" (settings.md). Añadido a los tres repos.
- Permisos `allow` de proyecto "apply only after each teammate trusts the folder"; `deny` y
  `ask` "apply right away" (settings.md). Los `settings.json` de proyecto añadidos solo llevan
  `allow` de comandos de verificación.

### 4.8 Memoria automática, `/insights`, `/doctor`

- La memoria automática es "machine-local", compartida entre worktrees del mismo repo, y se
  carga hasta 200 líneas o 25 KB de `MEMORY.md` (memory.md). Confirma el principio 1 de
  `ways-of-working.md`: lo compartible va al repo.
- `/insights` y `/doctor` cubren la revisión periódica de "qué se ha repetido tres veces" y de
  "qué sobra en `CLAUDE.md`". Recomendación: una pasada mensual con los dos, y anotar en el
  README las skills aceptadas y descartadas, como ya se hace.

## 5. Aplicado en esta tanda

Rama `claude/optimize-claude-code-repo-3dunjq` en cada repo. Sin PR: se abren cuando la persona
lo pida, y en `finance` e `idealista_bot` un PR no-draft se fusiona y despliega solo si el CI
está en verde.

**claude-code-config** (un commit por cambio lógico):

1. `.gitignore` y `git rm --cached` de los `.pyc` (C4).
2. `hooks/pre-push-verify.py`, registrado en `settings/hooks.snippet.json` con `timeout: 600`
   (C1); `hooks/tests/test_hooks.py` y `.github/workflows/ci.yml` (C2). Verificado:
   `ruff check .` limpio, `ruff format --check hooks` limpio, `pytest -q hooks/tests` 17/17.
3. `agents/verifier.md`, `skills/refute/SKILL.md`, `disable-model-invocation` en `deploy-pi`
   (C3, C5). Sin verificar en vivo.
4. `templates/project/` (C8) e `install.sh` con `--check` (C7), probado contra un `HOME`
   temporal. Corrección de la regla `deny` de `--auto` (C6).
5. `docs/optimizacion-2026-09.md` (este fichero) y README.
6. `CLAUDE.md`: dos líneas nuevas (`/refute` en zona caliente; el hook de push no se apaga para
   pasar). Commit propio, como manda la regla.

**finance**: `WORKFLOW.md` regla 5 (F1); `.claude/settings.json`, `.claude/rules/zonas-calientes.md`,
`.claude/verify-command`, `.gitignore` (F2, F5); em-dashes en `CLAUDE.md` en commit propio (F6).

**atril**: `.claude/` completo y `.gitignore` (A2, A4); em-dash en `CLAUDE.md` en commit propio (A5).

**idealista_bot**: `.gitignore` (I1); `.claude/` completo (I2); em-dashes en `CLAUDE.md` en
commit propio (I4).

Lo que estos cambios **no** hacen: no tocan código de aplicación, no cambian ningún número, no
tocan CI de los proyectos y no despliegan nada.

## 6. Pendiente de decisión

| # | Qué | Qué hay que decidir | Coste si se hace |
|---|---|---|---|
| A1 | Job `auto-merge` en `atril` | Que un PR en verde se fusione y **despliegue solo** en la Pi, como en `finance` | Un job de CI (YAML abajo); ninguna cuota |
| 4.5 | Revisión automática de PR con la GitHub Action | Gastar cuota de la suscripción en cada PR no-draft | Tokens por PR según tamaño del diff; se limita con `--max-turns` |
| F3 | `.githooks/` de `finance` | Borrar (recomendado) o documentar `core.hooksPath` | Cero |
| A3, I3 | ruff en `atril` e `idealista_bot` | Aceptar que el primer `ruff check` saque avisos que hay que arreglar antes de ponerlo en el gate | Una sesión por repo |
| F4 | ESLint en el gate de `finance` | 37 errores reales que arreglar primero | Una sesión en la nube |
| T1 | Deduplicar la explicación del gate | Dejar el porqué solo en `METODOLOGIA.md` | Cero |
| T2 | Convención `docs/plans/` | Mover o no los `PLAN_*.md` existentes | Cero |
| README 1 | `Stop` hook de tipo `agent` para turnos de deploy | Asumir que puede bloquear turnos | Segundos por turno de deploy |

### 6.1 YAML del job `auto-merge` para `atril`

Copiado de `finance/.github/workflows/ci.yml`, con los nombres de job de `atril`. Se añade al
final de `atril/.github/workflows/ci.yml`; al añadir un job de verificación nuevo hay que
añadirlo a `needs`, o falla y el PR se fusiona igual.

```yaml
  auto-merge:
    name: Auto-merge on green
    needs: [backend, frontend]
    if: >-
      github.event_name == 'pull_request' &&
      github.event.pull_request.draft == false
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Squash-merge the PR
        env:
          GH_TOKEN: ${{ github.token }}
        run: >-
          gh pr merge "${{ github.event.pull_request.number }}"
          --repo "${{ github.repository }}"
          --squash --delete-branch
```

## 7. Cómo mantener esto

- Cada mes: `/insights`, `/doctor` en cada repo, `sh install.sh --check` en cada máquina.
- Cada cambio de hook: test primero, `pytest -q hooks/tests` en verde, y avisar de que cambia
  todas las sesiones.
- Cada repo nuevo: copiar `templates/project/`, adaptar los tres ficheros, y declarar las zonas
  calientes en la regla por ruta, no en prosa.
- Cada regla nueva: preguntarse si tiene que cumplirse aunque nadie se acuerde. Si sí, hook o
  permiso; si no, `CLAUDE.md`, y aceptar que a veces no pasará.

## 8. Fuentes

Documentación oficial de Claude Code, consultada el 17 de septiembre de 2026:

- Best practices: https://code.claude.com/docs/en/best-practices.md
- CLAUDE.md, reglas por ruta y memoria automática: https://code.claude.com/docs/en/memory.md
- Hooks (referencia): https://code.claude.com/docs/en/hooks.md
- Skills: https://code.claude.com/docs/en/skills.md
- Subagentes: https://code.claude.com/docs/en/sub-agents.md
- Agent teams: https://code.claude.com/docs/en/agent-teams.md
- Flujos comunes (plan mode, worktrees, `claude -p`): https://code.claude.com/docs/en/common-workflows.md
- Settings y precedencia: https://code.claude.com/docs/en/settings.md
- Permisos (sintaxis de reglas): https://code.claude.com/docs/en/permissions.md
- GitHub Actions: https://code.claude.com/docs/en/github-actions.md

Evidencia interna: los ficheros y comandos citados en la sección 3, ejecutados en esta sesión
sobre los cuatro repos en la rama `claude/optimize-claude-code-repo-3dunjq`.
