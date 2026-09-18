# claude-code-config

Configuración personal de [Claude Code](https://code.claude.com) a nivel de usuario
(`~/.claude/`), pensada para aplicarse igual en cualquier máquina. Sirve como referencia y como
forma de sincronizar la configuración entre ordenadores. No contiene nada de ningún proyecto
concreto: solo reglas de flujo de trabajo, skills, hooks y permisos.

Lo común a todas las máquinas está separado de lo que depende de cada una: `CLAUDE.md` importa
al final `~/.claude/machine.md`, y ese fichero es el `machines/*.md` que toque.

## Qué hay aquí

| Fichero o carpeta | Va a | Qué es |
|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Reglas comunes: antes de escribir código, alcance, verificación, git, estilo, texto, comunicación. Termina importando `machine.md` |
| `machines/personal.md` | `~/.claude/machine.md` | Máquina personal: Windows 10 y PowerShell, sin Node, Raspberry Pi por SSH, GitHub con `claude/*` y PR |
| `machines/deloitte.md` | `~/.claude/machine.md` | Máquina corporativa: PowerShell 5.1, Group Policy que bloquea `.ps1` y `npm`, proxy TLS, VPN, Git Credential Manager, OneDrive |
| `docs/ways-of-working.md` | (solo lectura) | El porqué de cada regla: principios, piezas, sesión, flujo, verificación, git con agentes, hooks, y qué se descarta |
| `skills/audit/` | `~/.claude/skills/audit/` | `/audit`: auditoría de un repo con tabla de criticidad, sin editar nada |
| `skills/deploy-pi/` | `~/.claude/skills/deploy-pi/` | `/deploy-pi`: despliega a la Pi y exige verificación en vivo con evidencia real |
| `skills/refute/` | `~/.claude/skills/refute/` | `/refute [criterio]`: segunda opinión en contexto limpio. Lanza al subagente `verifier` contra el diff actual y devuelve un veredicto con pruebas; no arregla nada |
| `skills/humanizar/` | `~/.claude/skills/humanizar/` | `/humanizar [fichero]`: quita los tics de texto de IA en español o inglés sin cambiar lo que dice. Trae `tells.py`, un detector sin dependencias que cuenta los patrones y lista candidatos con fichero:línea, y cuatro pruebas para decidir cada contraste "no es X, es Y" |
| `agents/repo-auditor.md` | `~/.claude/agents/repo-auditor.md` | Subagente de solo lectura para explorar y auditar repos sin gastar el contexto principal |
| `agents/verifier.md` | `~/.claude/agents/verifier.md` | Subagente verificador: intenta refutar un cambio ya hecho, ejecuta la verificación del repo y recalcula por otro camino. Es el "revisor independiente" de `docs/ways-of-working.md`, sección 5.2 |
| `hooks/lint-check.py` | `~/.claude/hooks/` | `PostToolUse`: lint del fichero recién editado (ruff o eslint del repo), informativo, sub-segundo |
| `hooks/session-start-status.py` | `~/.claude/hooks/` | `SessionStart`: rama, sucio o limpio, worktree o checkout principal, distancia a `origin`. No hace pull |
| `hooks/block-commit-on-protected.py` | `~/.claude/hooks/` | `PreToolUse`: deniega `git commit` en la rama protegida (`origin/HEAD`, o `main`/`master`) |
| `hooks/_target_dir.py` | `~/.claude/hooks/` | Ayuda de los dos hooks anteriores: el repo que se mira es aquel al que va el comando (`cd ../otro && git ...`, `git -C ../otro ...`), no el `cwd` de la sesión |
| `hooks/pre-push-verify.py` | `~/.claude/hooks/` | `PreToolUse`: antes de un `git push` ejecuta el comando de `.claude/verify-command` del repo y deniega el push si falla. Sin ese fichero no hace nada |
| `hooks/tests/` | (solo este repo) | Tests de los cuatro hooks: `pytest -q hooks/tests`. Cada hook se ejecuta como proceso aparte con JSON por stdin, igual que lo lanza Claude Code |
| `settings/hooks.snippet.json` | fusionar en `~/.claude/settings.json` | El bloque `"hooks"` que registra los cuatro scripts |
| `settings/permissions.snippet.json` | fusionar en `~/.claude/settings.json` | Lista curada de permisos: `allow` para lo de solo lectura, `ask` para lo que sale de la máquina, `deny` para lo irreversible y los secretos |
| `templates/project/` | copiar a la raíz de cada repo | Plantilla de `.claude/` para un repo: `settings.json`, regla por ruta de zonas calientes, `verify-command` y el trozo de `.gitignore`. Ver su README |
| `docs/optimizacion-2026-09.md` | (solo lectura) | Auditoría de septiembre de 2026 de los cuatro repos: hallazgos con evidencia, recomendaciones contrastadas con la documentación oficial, qué se aplicó y qué queda pendiente de decidir |
| `install.sh` | (solo este repo) | `sh install.sh` copia todo a `~/.claude`; `sh install.sh --check` dice qué difiere entre el repo y la máquina (drift) |
| `ruff.toml` | (solo este repo) | Para que el hook de lint pase sobre los propios hooks al editarlos aquí |
| `.github/workflows/ci.yml` | (solo este repo) | `ruff check`, `ruff format --check` y los tests de los hooks en cada PR |

## Instalación en una máquina nueva

Desde Git Bash (Windows) o cualquier shell en Linux. En la máquina corporativa Group Policy
bloquea los `.ps1`, así que el instalador es `sh` a propósito:

```bash
git clone https://github.com/jaguirrepeman/claude-code-config.git
cd claude-code-config
sh install.sh --machine personal     # o --machine deloitte
```

Copia `CLAUDE.md`, el `machine.md` que toque, `skills/`, `agents/` y `hooks/*.py` a `~/.claude/`.
Para saber si la máquina se ha quedado atrás respecto al repo (o al revés, si se editó algo en
`~/.claude` sin subirlo): `sh install.sh --check`, que lista `igual`, `DIFIERE` o `FALTA` por
fichero y sale con 1 si hay drift.

El instalador **no toca `~/.claude/settings.json`**: fusiona a mano (no sobrescribas)
`settings/hooks.snippet.json` y `settings/permissions.snippet.json` dentro de él. Si no existe, puedes
juntar los dos bloques en un fichero nuevo. Si `~/.claude/settings.json` ya tiene `hooks` o
`permissions`, añade las entradas dentro de las listas existentes.

Requisitos de los hooks: `python` en el PATH (3.10 o superior). Los comandos usan `$HOME`, que
Claude Code expande en el shell con el que lanza los hooks; si en la primera sesión no aparece el
informe de estado del repo, sustituir `$HOME` por la ruta absoluta del perfil. Si un hook no
encuentra ruff, eslint o git, no hace nada: los tres fallan abiertos por diseño.

Para comprobar que están activos: abrir una sesión en cualquier repo y ver que aparece "Estado
del repo" al arrancar. Para comprobar que los hooks hacen lo que dicen, en este repo:
`pytest -q hooks/tests`.

## Por qué esto es así

- **Hooks en Python y no en PowerShell.** Group Policy bloquea los `.ps1` en la máquina
  corporativa y Python está en las dos. El `lint-check.ps1` anterior además imprimía a stdout,
  que en `PostToolUse` no llega al modelo; la versión en Python devuelve el aviso como
  `additionalContext`, que es lo que hace que Claude lo vea y lo arregle.
- **Lint del fichero, no del repo.** `ruff check .` sobre un repo grande tarda segundos y un hook
  que tarda se acaba apagando. Sobre un fichero es sub-segundo.
- **Los tres hooks fallan abiertos, devuelven la salida del fallo y nunca salen con error.** Son
  las tres reglas de diseño de `docs/ways-of-working.md`, sección 7. Cualquier hook nuevo las
  sigue.
- **El bloqueo de commit es de sesión, no de servidor.** Impide que una sesión de Claude Code
  commitee en la rama protegida; no impide hacerlo a mano. Para eso está la protección de rama
  del remoto. Se puede fijar la rama con `CLAUDE_PROTECTED_BRANCHES=main,release`.
- **En un repo que ya tiene sus propios hooks de proyecto** (`.claude/settings.json`), los
  globales corren también. Un aviso de estado repetido es inofensivo; si molesta, se quita el del
  proyecto o el global, no los dos.
- **El commit no está en `ask`, a propósito.** Es local y se deshace. Lo que para de verdad es
  que nada salga de la máquina sin que lo veas: `push`, `merge`, `pr create`.
- **La verificación se exige en el push, no en cada turno.** Un `Stop` hook que verifica en cada
  respuesta tarda segundos y se acaba apagando (probado). El push pasa pocas veces al día y es
  cuando el código llega al CI o a otra persona. Cada repo declara su comando en
  `.claude/verify-command`; sin él, el hook calla. `CLAUDE_SKIP_VERIFY=1` lo apaga para una
  sesión, para un push consciente de emergencia.
- **`/deploy-pi` lleva `disable-model-invocation: true`.** Desplegar tiene efectos fuera de la
  máquina; lo lanza la persona con `/deploy-pi`, nunca el modelo por su cuenta. Es lo que la
  documentación recomienda para skills con efectos secundarios.

## Skills: criterio de admisión

Una skill se justifica solo si se cumplen las tres:

1. El procedimiento se ha repetido **al menos tres veces**, con evidencia (commits, actas,
   `/insights`), no por intuición.
2. Tiene **pasos que se olvidan o se hacen distinto cada vez**. Un procedimiento que nadie hace
   mal no necesita skill.
3. **Mantenerla cuesta menos que repetirla.** Envolver un comando de una línea no aporta nada.

Y se descarta lo que ya cubre una regla de `CLAUDE.md` o de `.claude/rules/`, porque eso se
carga solo y una skill encima sería la misma información en dos sitios. Una regla ("diagnóstico
antes de arreglo") es una línea en `CLAUDE.md`; una skill es un procedimiento con pasos.

| Skill | Qué resuelve | Por qué existe |
|---|---|---|
| `audit` | Auditoría de solo lectura con tabla de criticidad y plan priorizado, antes de tocar código | Se pedía en cada repo nuevo con pasos distintos cada vez |
| `deploy-pi` | Deploy a la Pi con verificación en vivo obligatoria | El paso que se saltaba era la verificación con evidencia real |
| `refute` | Segunda opinión en contexto limpio: un subagente que no escribió el cambio intenta refutarlo y devuelve pruebas | La revisión con contexto limpio se pedía con una frase distinta cada vez y sin criterio; la skill fija el procedimiento, el formato y que no arregle nada |
| `humanizar` | Pasada final sobre un texto para quitar lo que suena a IA (contrastes "no es X, es Y", fragmentos cortos, rayas, léxico inflado), con detector y recuento antes y después | Se pedía con una frase distinta cada vez ("suena a IA", "déjalo más llano") y sin criterio para decidir qué tocar; medido en 38 documentos de un repo real, lo frecuente era forma (139 "X, no Y.", 52 "no es X, es Y", 72 fragmentos cortos) y el léxico de los catálogos casi no aparecía (5 aciertos), así que las listas de palabras no bastaban. Copia general de la `humanizar-es` de SKLUM, sin lo específico del proyecto |

Candidatas descartadas: convenciones de commit y ramas (regla, no procedimiento), verificación
con lint y tests (un comando, ya en `CLAUDE.md`), revisión de código (`/code-review` del harness
ya lo cubre).

## Buenas prácticas de Claude Code (notas de referencia, 2026-09)

Con fuentes oficiales. No todo está aplicado arriba; al final, lo que falta.

### CLAUDE.md

- **Qué incluir**: comandos no obvios, convenciones de estilo que difieren del default, flujo de
  trabajo específico del repo, "gotchas" (por ejemplo "no hay Node en esta máquina"), decisiones
  de arquitectura que no se infieren del código, variables de entorno necesarias.
- **Qué no incluir**: obviedades ("escribe código limpio"), documentación de librerías (mejor un
  enlace), listados de ficheros que Claude ya puede descubrir solo, tutoriales largos (eso es una
  skill, no memoria).
- **Tamaño**: la señal de que algo no pertenece ahí es "si borro esta línea, ¿Claude comete el
  mismo error otra vez?". Si no, fuera. Menos de 200 líneas.
- **Precedencia** (de más general a más específico): managed policy, user (`~/.claude/CLAUDE.md`),
  project (`./CLAUDE.md`), local (`CLAUDE.local.md`, gitignored), anidados por subcarpeta.
- **Imports**: `@ruta/al/fichero.md` para dividir por tema; se cargan al inicio de sesión igual,
  no ahorran contexto, solo organizan. Es lo que usa este repo para `machine.md`.
- Fuentes: [memory.md](https://code.claude.com/docs/en/memory.md),
  [large-codebases.md](https://code.claude.com/docs/en/large-codebases.md)

### Skills

- Frontmatter: `name`, `description` (crítico para que Claude la elija sola),
  `disable-model-invocation` (solo a mano con `/nombre`), `user-invocable`, `allowed-tools`,
  `context: fork` (corre en subagente aislado), `model`, `paths` (glob para activar solo en
  ciertos ficheros).
- **Inyección dinámica**: una línea `` !`comando` `` ejecuta el comando antes de que Claude vea la
  skill y sustituye la salida. Un exit code distinto de 0 aborta la skill entera: usar
  `2>/dev/null || true` en comandos que puedan fallar.
- User (`~/.claude/skills/`) frente a project (`.claude/skills/`, para el equipo) frente a plugin.
- Fuente: [skills.md](https://code.claude.com/docs/en/skills.md)

### Hooks

- Eventos: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SessionStart`, `Stop`,
  `PreCompact`, `PostCompact`, `PermissionRequest`, `Notification`, `ConfigChange`.
- Tipos: `command` (shell), `prompt` (evalúa con un modelo rápido), `agent` (subagente con
  herramientas, puede bloquear con lógica real), `http`, `mcp_tool`.
- **No bloquear por accidente**: un hook informativo acaba siempre en exit 0. Para que Claude vea
  la salida de un `PostToolUse`, JSON con `hookSpecificOutput.additionalContext`; el stdout suelto
  solo va al transcript. `SessionStart` es la excepción: su stdout entra en el contexto.
- **Seguridad**: nunca credenciales en claro dentro de un hook, cuidado con interpolar variables
  de entorno sin validar.
- Fuente: [hooks-guide.md](https://code.claude.com/docs/en/hooks-guide.md)

### Otras piezas

- **Subagentes** (`~/.claude/agents/*.md`): un rol reutilizable con `name`, `description`,
  `tools`. Compensa guardarlo cuando es el mismo papel en muchos proyectos; en un repo de equipo
  pequeño, pedirlo con una frase hace lo mismo.
- **`/insights`**: informe HTML sobre las últimas sesiones (proyectos, fricciones, sugerencias de
  reglas y skills). Es la revisión periódica de "qué se ha repetido" hecha sola.
- **`/fewer-permission-prompts`**: escanea las transcripciones y propone la lista `allow` con
  evidencia, en vez de acumular clics.

### Lo que falta y conviene añadir

Lo que estaba aquí en la versión anterior (hook sobre `git push`, reglas por ruta) ya está hecho:
`hooks/pre-push-verify.py` y `templates/project/.claude/rules/`. Lo que queda, con su motivo y
su coste, está en `docs/optimizacion-2026-09.md`, sección "Pendiente de decisión". Resumen:

1. **Hook `Stop` de tipo `agent`** que compruebe antes de cerrar un turno de deploy que hay
   evidencia real pegada. Cambia el comportamiento (puede bloquear turnos): se decide a mano.
2. **Revisión automática de PR con la Claude Code GitHub Action** (`/install-github-app`).
   Gasta cuota en cada PR; se activa por repo y con `--max-turns`, o no se activa.
3. **Job `auto-merge` en `atril`**, como en `finance` e `idealista_bot`. Un merge despliega,
   así que es una decisión de producción, no de configuración.
