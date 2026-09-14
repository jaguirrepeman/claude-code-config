# claude-code-config

Configuración personal de [Claude Code](https://code.claude.com) a nivel de
usuario (`~/.claude/`), pensada para aplicarse igual en cualquier máquina.
Sirve como referencia y como forma de sincronizar la config entre ordenadores
(este repo no contiene nada de ningún proyecto concreto — solo reglas
generales de flujo de trabajo, skills y hooks).

## Qué hay aquí

| Archivo/carpeta | Va a | Qué es |
|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Memoria de usuario: entorno (shell/SO), reglas de git/ramas/worktrees, estilo de código, verificación antes de dar algo por bueno |
| `skills/audit/` | `~/.claude/skills/audit/` | `/audit` — auditoría de un repo con tabla de criticidad, sin editar nada |
| `skills/deploy-pi/` | `~/.claude/skills/deploy-pi/` | `/deploy-pi` — despliega y exige verificación en vivo con evidencia real |
| `agents/repo-auditor.md` | `~/.claude/agents/repo-auditor.md` | Subagente de solo lectura (sin Edit/Write) para explorar/auditar repos en paralelo sin gastar el contexto principal |
| `hooks/lint-check.ps1` | `~/.claude/hooks/lint-check.ps1` | Script que corre `ruff check`/`npm run lint` tras cada edición, de forma informativa (no bloqueante) |
| `settings/hooks.snippet.json` | fusionar dentro de `~/.claude/settings.json` | El bloque `"hooks"` que registra el script anterior como hook `PostToolUse` |

## Instalación en una máquina nueva (Windows)

```powershell
git clone <url-de-este-repo> claude-code-config
cd claude-code-config

Copy-Item CLAUDE.md ~/.claude/CLAUDE.md -Force
Copy-Item -Recurse skills/* ~/.claude/skills/ -Force
Copy-Item -Recurse agents/* ~/.claude/agents/ -Force
New-Item -ItemType Directory -Force ~/.claude/hooks | Out-Null
Copy-Item hooks/lint-check.ps1 ~/.claude/hooks/lint-check.ps1 -Force
```

Luego **fusiona a mano** (no sobrescribas) el contenido de
`settings/hooks.snippet.json` dentro de `~/.claude/settings.json` — sustituye
`<TU_USUARIO>` por el usuario real de esa máquina en la ruta del comando. Si
`~/.claude/settings.json` no existe todavía, puedes copiarlo tal cual y
renombrarlo.

Requisitos del hook: Windows PowerShell (`powershell.exe`, viene de fábrica).
No hace falta `pwsh` (PowerShell Core) ni `jq`. Si el hook no encuentra
`ruff`/`npm`, simplemente no hace nada — es no bloqueante por diseño.

## Por qué esto es así (contexto)

- El hook usa `powershell -NoProfile -File <ruta>` en vez de `-Command "..."`
  para evitar problemas de escapado de comillas anidadas entre el shell que
  envuelve el hook (bash/cmd/PowerShell, según la máquina) y PowerShell.
- El script `.ps1` siempre termina en `exit 0`: es informativo, nunca debe
  bloquear una edición aunque el lint encuentre errores.
- `CLAUDE.md` asume que la máquina de desarrollo es Windows y que el destino
  de despliegue (si lo hay) es Linux por SSH — ajusta esa sección si tu
  entorno es distinto.

---

## Resumen: buenas prácticas de Claude Code (investigado 2026-09)

Notas de referencia, con fuentes oficiales. No todo lo de aquí está aplicado
arriba — al final hay una lista de "lo que falta y conviene añadir".

### CLAUDE.md

- **Qué incluir**: comandos no obvios, convenciones de estilo que difieren
  del default, flujo de trabajo específico del repo, "gotchas" (p. ej. "no
  hay Node en esta máquina"), decisiones de arquitectura que no se infieren
  del código, variables de entorno necesarias.
- **Qué NO incluir**: obviedades ("escribe código limpio"), documentación de
  librerías (mejor un link), listados de archivos que Claude ya puede
  descubrir solo, tutoriales largos (eso es un skill, no memoria).
- **Tamaño**: la señal de que algo no pertenece ahí es "si borro esta línea,
  ¿Claude comete el mismo error otra vez?" — si no, fuera.
- **Precedencia** (de más general a más específico): managed policy → user
  (`~/.claude/CLAUDE.md`) → project (`.claude/CLAUDE.md` o `./CLAUDE.md`) →
  local (`CLAUDE.local.md`, gitignored) → anidados por subcarpeta.
- **Imports**: `@ruta/al/fichero.md` para dividir por tema
  (`@.claude/rules/deployment.md`); se cargan al inicio de sesión igual, no
  "ahorran" contexto, solo organizan.
- Fuentes: [memory.md](https://code.claude.com/docs/en/memory.md),
  [large-codebases.md](https://code.claude.com/docs/en/large-codebases.md)

### Skills (`.claude/skills/*/SKILL.md`)

- Frontmatter soportado: `name`, `description` (crítico para que Claude lo
  auto-invoque sin que lo pidas explícitamente), `disable-model-invocation`
  (solo invocable a mano con `/nombre`), `user-invocable`, `allowed-tools`,
  `disallowed-tools`, `arguments` (positional, `$0`/`$1`/`$nombre` además de
  `$ARGUMENTS`), `context: fork` (aislado en subagente), `model`, `paths`
  (glob para activar solo en ciertos ficheros).
- **Inyección dinámica**: una línea `` !`comando` `` (o un bloque ```` ```! ````)
  ejecuta el comando ANTES de que Claude vea el skill y sustituye la salida
  inline. Un exit code distinto de 0 aborta el skill entero — hay que ser
  cuidadoso con comandos que puedan fallar (ver `audit`/`deploy-pi` arriba,
  usan `2>/dev/null || true`/`|| echo ...` para no abortar).
- User (`~/.claude/skills/`) vs project (`.claude/skills/`, commiteado, para
  el equipo) vs plugin (distribuido por marketplace).
- Fuentes: [skills.md](https://code.claude.com/docs/en/skills.md)

### Hooks (`settings.json`)

- Eventos: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SessionStart`,
  `Stop`, `PreCompact`/`PostCompact`, `PermissionRequest`, `Notification`,
  `ConfigChange`, entre otros.
- Tipos de hook: `command` (shell), `prompt` (evalúa con un LLM rápido),
  `agent` (corre un subagente con tools — puede leer archivos, ejecutar
  comandos, y bloquear con lógica real, no solo un exit code), `http`,
  `mcp_tool`.
- **No bloquear por accidente**: un hook informativo debe acabar siempre en
  `exit 0` (o devolver JSON sin `continue: false`). El campo `"if"` permite
  filtrar cuándo corre el hook sin gastar un proceso de más.
- **Seguridad**: nunca credenciales en claro dentro de un hook, nunca `sudo`
  sin contexto explícito, cuidado con interpolar variables de entorno sin
  validar.
- Fuentes: [hooks-guide.md](https://code.claude.com/docs/en/hooks-guide.md),
  referencia completa de hooks en la doc de `settings.json`.

### Otras funcionalidades con las que vale la pena familiarizarse

- **Subagentes** (`~/.claude/agents/*.md`, o `.claude/agents/` de proyecto):
  definen un rol reutilizable (frontmatter `name`, `description`, `tools`,
  opcionalmente `model`) invocable por nombre desde el Agent tool. Sirven para
  explorar/auditar en paralelo sin ensuciar el contexto principal — es lo que
  usa este repo con `repo-auditor.md`.
- **Workflows/routines**: tareas recurrentes programadas (cron en la nube) o
  bucles (`/loop`) sin tener que reabrir sesión cada vez.
- **Permisos granulares en `settings.json`** (`permissions.allow`/`deny`):
  reduce prompts repetidos para comandos de solo lectura de uso frecuente
  (`git *`, `pytest`, etc.) sin abrir la puerta a todo.

### Lo que falta y conviene añadir (siguiente paso, no aplicado todavía)

1. **Un hook `Stop` de tipo `agent`** que verifique antes de terminar un turno
   de deploy que tests/lint pasaron y que hay evidencia real pegada — esto es
   un cambio de comportamiento real (puede alargar/bloquear turnos), así que
   antes de activarlo hay que decidirlo explícitamente, no meterlo por
   defecto.
2. **Permisos granulares** en `settings.json` para los comandos de solo
   lectura que se repiten en cada sesión (`git status`, `git branch -vv`,
   `git log`) y así reducir prompts de aprobación.
3. Revisar si conviene mover parte de las reglas de flujo de git/worktrees a
   un `.claude/rules/*.md` con `paths:` en los repos donde solo aplican a una
   subcarpeta (monorepos), en vez de repetirlas en cada `CLAUDE.md` de
   proyecto.
