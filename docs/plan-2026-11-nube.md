# `/mejora` en la nube, con este PC primero (noviembre de 2026)

Cierra la decisión de #38. Decidido con la persona el 2026-11-28.

## Objetivo

- gymapp se trabaja solo en la nube.
- El resto, en este PC (tareas de la app de escritorio, 13:00 y 21:00; auditar 9:00 miércoles y
  sábado). Si el PC no ha corrido, una tarea en la nube hace la pasada una hora y media después.

## Lo comprobado y lo supuesto

Documentado (code.claude.com/docs/en/routines.md y cloud-environments.md, leído el 2026-11-28),
sin probar todavía:

- Una tarea en la nube clona en cada ejecución los repos que se le den, puede ser más de uno.
- Solo ve lo que hay dentro de los repos: ni `~/.claude/skills` ni `~/.claude/CLAUDE.md`. Este
  repo es público, así que el script de arranque lo clona y corre `install.sh`.
- El proxy rechaza `gh pr` y `gh issue` (van por GraphQL); `gh api` por REST funciona.
- Ubuntu con uv, pytest, ruff, Node y gh. Deno no viene: gymapp lo necesita para verificar.
- Gasta de la suscripción igual que una sesión normal. Como mucho una ejecución por hora.

Comprobado en la primera ejecución de prueba en la nube (2026-11-28, 12:04 UTC, PR atril#178):

- Clona los 8 repos en `/home/user/<repo>`, `install.sh` funciona y deja la skill instalada.
- `gh api` por REST lee issues y PR, y crea el PR: funciona.
- Las variables de Actions **no** se leen desde la nube: el latido salió "desconocido" cuando
  existía, y la nube cogió atril, que era del PC. Por eso el estado pasó a un issue.

## Diseño

- **Estado en GitHub, no en un fichero del PC.** En el cuerpo de un issue abierto con la
  etiqueta `mejora-estado` en este repo (#41): la fecha de la última auditoría de cada repo (lo
  que antes era `~/.claude/state/mejora.json`) y cuándo pasó el PC por última vez. Si no se puede
  leer, se usa el fichero local como antes, y el PC no escribe a ciegas.
- **Reparto** en `skills/mejora/repos.json`: `"nube"` (solo la nube) o, por defecto, `"pc"`
  (el PC, con la nube de respaldo).
- `pick.py --donde pc` apunta el latido y salta los repos `nube`. `pick.py --donde nube` coge los
  repos `nube` siempre y los `pc` solo si el latido tiene más de 3 horas.
- **Todo GitHub por REST** (`gh api`) en `pick.py` y en la skill, en el PC y en la nube: un solo
  camino.

## Criterio de aceptación

- Tests de `pick.py`: el reparto y el latido deciden qué repos entran en cada sitio.
- Una ejecución de prueba en la nube sobre gymapp que llega hasta el final: elige issue o repo,
  verifica, y crea su issue o PR por REST. Si algo de lo "documentado" falla, se apunta aquí con
  la salida real.

## Fuera

- El candado de dos auditorías a la vez (#37).
- Instalar en la nube algo que no sea Deno.
