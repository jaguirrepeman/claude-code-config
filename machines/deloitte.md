# Entorno: máquina corporativa (Deloitte)

Se instala como `~/.claude/machine.md`. Lo importa el `CLAUDE.md` común al final.

## Shell y sistema operativo

- **Windows 11 Enterprise con Windows PowerShell 5.1.** No hay `pwsh` (PowerShell Core). Los
  comandos que se dan para pegar en terminal van en sintaxis 5.1: `;` para encadenar (nunca
  `&&` ni `||`), sin ternarios, sin `??`, sin heredocs.
- **Group Policy bloquea los scripts `*.ps1` y `npm` lanzado desde PowerShell.** Cualquier script
  va en `.bat` (ASCII puro, nada por encima de 127) y se lanza con `cmd /c script.bat`, o se
  llama a `python` y `node` directamente. Nunca proponer un `.ps1`.
- **Group Policy bloquea el remote debugging de Chrome** (`RemoteDebuggingAllowed = 0`).
  Playwright con `channel="chrome"` abre la ventana y nunca conecta. Usar siempre el Chromium
  propio de Playwright (`python -m playwright install chromium`).
- La herramienta Bash de Claude Code es **Git Bash (MSYS)**: ahí `&&` sí funciona, pero las
  rutas se traducen. Para invocar `cmd` desde Git Bash, `cmd //c` (doble barra).
- Nunca sugerir `rm -rf`, `ls`, `touch` ni `find` para que la persona los pegue en PowerShell.
  `Remove-Item`, `Get-ChildItem`, `New-Item`.

## Red y credenciales

- **Proxy corporativo que intercepta TLS.** `uv sync` necesita `system-certs = true` en
  `[tool.uv]`; otras herramientas pueden necesitar el certificado de la empresa. Un error de
  certificado no es un bug del paquete.
- **Los Bitbucket internos solo se alcanzan con VPN.** Un fallo de DNS o de host al hacer fetch
  o push es un problema de red, no de git: decirlo así y no intentar arreglarlo tocando el repo.
- **Git Credential Manager secuestra la autenticación** con la cuenta corporativa. Para un
  remoto de GitHub personal, usar un PAT (`https://<usuario>:<token>@github.com/...` o
  `-c credential.helper=`) y quitarlo de `.git/config` en cuanto se termine. Nunca dejar un
  token escrito en el repo ni en un fichero versionado.
- **IT bloquea algunas peticiones web con 403 ("Your IT Admin has blocked this request").**
  Tres sesiones han muerto así sin entregar nada. Por eso: ante una tarea larga, escribir el
  plan a un fichero antes de ejecutar, para que sobreviva a un corte.

## Ficheros y rendimiento

- **Varios repos viven en carpetas sincronizadas por OneDrive** (`OneDrive - Deloitte`): I/O
  lenta, ficheros bloqueados a ratos, tests que tardan más de lo normal. Si un fichero no se deja
  escribir o borrar, primero sospechar de OneDrive.
- **Buscar con `git grep`, nunca con `grep -r` ni `find` sobre la raíz.** Los repos tienen
  `node_modules`, `.venv`, `data/` y carpetas de build con cientos de miles de ficheros; un
  recorrido recursivo se cuelga o agota el timeout.
- Un fichero grande de documentación (más de 50 KB) se lee por tramos, no entero.

## Python

- Python gestionado por `uv`, no el que instala IT. Cada repo tiene su `.venv`; los hooks y
  scripts llaman a `.venv\Scripts\python.exe` directamente.
- Los worktrees de `.claude/worktrees/` no tienen `.venv` propio: usar el de la raíz del
  checkout y poner el `src/` del worktree por delante en `PYTHONPATH` si el paquete está
  instalado en editable.
