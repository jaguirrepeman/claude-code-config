# Plantilla de `.claude/` para un repo de proyecto

Lo mínimo que un repo propio debe llevar versionado para que las sesiones de Claude Code se
comporten igual en todas las máquinas. Se copia a la raíz del repo y se adapta; nada de esto
sustituye al `CLAUDE.md` del proyecto, lo complementa.

| Fichero | Qué es | Se adapta |
|---|---|---|
| `.claude/settings.json` | Permisos compartidos del proyecto: `allow` para los comandos de verificación del repo (lo que ya cubre el snippet global no hace falta repetirlo) | Sí: los comandos reales del repo |
| `.claude/rules/zonas-calientes.md` | Regla con `paths:`: solo entra en contexto cuando la sesión toca esos ficheros. Declara las zonas calientes del repo (donde un error cambia un número, no rompe el build) y qué implican | Sí: los globs y el porqué |
| `.claude/verify-command` | El comando de verificación completa del repo, una línea. Lo lee `hooks/pre-push-verify.py` antes de cada `git push` | Sí |
| `gitignore.snippet` | Lo que se añade al `.gitignore` del repo: lo personal de `.claude/` fuera de git, lo compartido dentro | No |
| `.claude/skills/pr-gate/SKILL.md` | Revisión propia del repo antes del auto-merge. La ejecuta el job `review` del CI con la GitHub Action de Claude; su veredicto `block` para el merge | Sí: la sección "Qué comprobar en este repo", con comandos y resultado esperado |
| `.github/workflows/ci-gate.snippet.yml` | Los jobs `review` y `auto-merge` del gate y el `ready_for_review` del disparador, para pegar en `ci.yml`. Trae el setup de uv de ejemplo (`astral-sh/setup-uv` con versión fijada y `uv sync --locked --dev`) | Sí: `needs`, la versión de uv y el directorio del `pyproject.toml` |
| `.python-version` y `uv.lock` | No están en la plantilla porque los genera uv en el repo (`uv python pin <versión>` y `uv lock`), pero forman parte del estándar y van versionados: el primero fija el intérprete (el mismo que exige el destino de despliegue) y el segundo es la única fuente de verdad de las dependencias, la que usan `uv sync --locked` en CI y en la Pi. Sin `requirements.txt` a mano; si algo lo necesita, `uv export` desde el lock | Sí: la versión de Python |

Reglas que se aplican al usar la plantilla:

- **Nunca ignorar `.claude/` entero en `.gitignore`.** Todo lo que se cree ahí queda fuera de git
  en silencio y cada máquina diverge. Se ignora solo `settings.local.json`, `worktrees/` y
  `CLAUDE.local.md`.
- **Lo que ya dice `CLAUDE.md` no se repite en una regla.** Una regla por ruta añade lo que solo
  aplica a esos ficheros; si dos sitios dicen lo mismo, acaban diciendo cosas distintas.
- **El comando de `verify-command` es el mismo que documenta `CLAUDE.md`** para "verificar
  antes de dar algo por bueno". Si hay dos comandos, uno se queda obsoleto.
- **Los comandos de Python van con `uv run`** (`uv run pytest -q`, `uv run ruff check .`), tanto
  en `settings.json` como en `verify-command` y en la skill `pr-gate`: es lo que garantiza que
  corren en el `.venv` del repo, sincronizado con `uv.lock`. La regla completa está en la sección
  "Entornos Python" del `CLAUDE.md` común.
- Los hooks de proyecto (`hooks` en `.claude/settings.json`) se añaden solo cuando una regla
  tiene que cumplirse aunque nadie se acuerde y se puede comprobar con un comando. Los globales
  (`~/.claude/settings.json`) corren también en el repo.

Fuentes: [memory.md](https://code.claude.com/docs/en/memory.md) (reglas por ruta, `CLAUDE.local.md`),
[settings.md](https://code.claude.com/docs/en/settings.md) (`settings.json` frente a
`settings.local.json`), [permissions.md](https://code.claude.com/docs/en/permissions.md)
(sintaxis de las reglas).
