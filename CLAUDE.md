# Entorno de esta máquina

## Shell y sistema operativo
- La máquina local es **Windows 10 + PowerShell**. Para comandos locales, usa siempre sintaxis PowerShell: `;` para encadenar (nunca `&&`/`||` de bash), `$env:VAR` para variables de entorno, `Set-Content`/`Get-Content` en vez de heredocs, sin `sudo`.
- No emitas comandos bash (encadenados con `&&`, con heredocs, con `pipe | tee`) para ejecutar nada en local — fallarán o se comportarán de forma distinta en PowerShell.

## Raspberry Pi (destino remoto)
- El Raspberry Pi de producción es **Linux/bash**, no Windows. Cualquier comando pensado para el Pi debe ir explícitamente envuelto en una sola invocación SSH, por ejemplo:
  `ssh pi@<host> 'bash -lc "comando"'`
  Nunca mezclar sintaxis PowerShell dentro de esa cadena remota, ni asumir que un comando local also corre en el Pi.
- **Archivos systemd**: nunca escribir un unit file con un pipe `sudo tee` desde el lado Windows — es propenso a fallos silenciosos (puede vaciar el archivo y dejar el servicio enmascarado sin aviso). En su lugar: escribir el archivo en local, copiarlo con `scp`, y en el Pi hacer `sudo mv` + `sudo systemctl daemon-reload`.

## Verificación antes de decir "hecho"
- Verificar siempre contra `origin/<rama>`, no contra la copia local — hacer `fetch` primero y confirmar que el SHA local coincide con el desplegado.
- Tras cualquier deploy al Pi, comprobar el endpoint/página en vivo (curl o navegador) y pegar los valores reales observados antes de afirmar que funciona.
- Si el cambio toca layout responsive o varios dispositivos (iPad, móvil, Kindle Scribe, Kobo), verificar que los demás dispositivos siguen renderizando bien — no declarar éxito comprobando solo uno.
- Si no se puede producir evidencia real, decir "sin verificar" en vez de "hecho".

## Disciplina de alcance
- Preferir el cambio mínimo aditivo sobre regenerar archivos de configuración completos (p. ej. añadir una entrada a `hooks.json` en vez de reescribirlo entero).
- Antes de refactors grandes o cambios multi-archivo, exponer el plan y el alcance, y esperar confirmación.

## Flujo de trabajo con git, ramas y worktrees (patrón repetido en mis repos)

Modelo mental: `origin/main` es el proyecto de verdad (de ahí despliega la Pi), así
que tiene que estar siempre verde y desplegable. Nada es real hasta que se fusiona.

- **Una tarea = una rama `claude/*` = un worktree**, pequeña y enfocada. Nunca
  mezclar temas en una rama.
- **Nunca `git add -A`.** Añadir explícitamente los ficheros de la tarea — evita
  arrastrar cambios de otro workstream.
- **Sincronizar `main` antes de cada tarea** (`git pull` o ramificar desde
  `origin/main`) — el `main` local tiende a quedarse atrás.
- **Fusionar pronto y a menudo.** Las ramas que envejecen generan conflictos,
  sobre todo en los ficheros más compartidos del repo. Borrar rama + worktree
  justo después de fusionar (`git worktree remove <ruta>` + `git branch -d
  <rama>`). Nunca más de 1-2 worktrees vivos a la vez.
- **Si dos ramas tocan el mismo fichero:** fusionar una, rebasar la otra sobre el
  `main` nuevo y resolver el conflicto pequeño. Nunca fusionar dos a ciegas.
- **Integración a `main` vía PR** (`gh pr create --fill`), no push directo.
- **No ejecutar `gh pr merge --auto`** salvo que conste que el repo tiene branch
  protection / checks obligatorios de verdad. En un repo privado plan Free no hay
  eso, así que `--auto` fusiona al instante sin esperar al CI. Si el repo tiene un
  job tipo `auto-merge` que depende de los jobs de test y fusiona por squash solo
  si están en verde, ese job es el gate — dejar que actúe él, no forzar el merge.
  Sin ese job, dejar el PR abierto (o commiteado en su rama) para que el humano
  decida — **un merge a `main` normalmente despliega solo a producción**
  (webhook → script de deploy en la Pi, con rollback automático si falla el
  health check), así que trátalo como una acción con efecto en producción, no
  como un paso inerte.
- **Para retener un PR sin que se fusione solo:** abrirlo como *draft* — los jobs
  de auto-merge no corren en draft.

## Node.js en esta máquina
- **En este PC no hay Node instalado.** No asumas que `npm`/`node`/`tsc`/`vite build` corren en local. La validación de tipos y el build de frontend se hacen en CI o en el destino de despliegue (la Pi) — no dar por bueno TypeScript/JS sin haberlo visto compilar ahí.

## Estilo de código (patrón repetido en mis repos)
- **La lógica de negocio vive en una capa de servicios**, no en los endpoints/handlers. Si un endpoint pasa de ~40 líneas, probablemente lleva lógica que debería vivir aparte.
- **Todo bug arreglado lleva su test de regresión.** Es la regla de oro: el test es el contrato, no la revisión humana línea a línea.
- **Tests en verde antes de dar algo por bueno**, sean tuyos o preexistentes. Se puede delegar su arreglo, no ignorarlos.
- **Una regla, un solo sitio.** Antes de añadir una constante o heurística, comprobar si ya existe — la lógica duplicada en varios módulos ha causado bugs reales de divergencia.
- `logging`, nunca `print()`. Capturar la excepción concreta, no `Exception` a secas; usar `logger.exception` al tragar una excepción.
- Los comentarios explican **el porqué**, no el qué.

## Comprobaciones antes de pushear (siempre en local si se puede)
- Python: `ruff check .` (o el linter que use el repo) y `pytest -q` antes de cada push — no dejes que lo descubra el CI primero si se puede correr aquí. (Ahora hay un hook global que corre `ruff check`/`npm run lint` automáticamente tras cada Edit/Write si el proyecto los tiene — es informativo, no bloqueante; esto es la comprobación manual antes de pushear.)
- Frontend: `npm run lint && npm run build && npm test` antes de abrir el PR — recuerda que en esta máquina no hay Node, así que esto normalmente solo se puede verificar en CI/Pi, no en local (ver sección "Node.js" arriba).
- **Nunca timers falsos/mockeados en tests async.** Han colgado CI en este tipo de proyectos. Prefiere timeouts reales y cortos.

## Comunicación
- Responde primero en lenguaje llano (2-4 frases, sin rutas de fichero ni código), y luego ofrece profundizar ("¿quieres el detalle técnico?"). Escala a referencias de código solo si se pide explícitamente.
