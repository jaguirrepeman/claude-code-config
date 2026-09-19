# Entorno: máquina personal

Se instala como `~/.claude/machine.md`. Lo importa el `CLAUDE.md` común al final.

## Shell y sistema operativo

- **Windows 10 + PowerShell.** Los comandos que se dan para pegar en terminal van en sintaxis
  PowerShell: `;` para encadenar (nunca `&&` ni `||`), `$env:VAR` para variables, `Set-Content`
  y `Get-Content` en vez de heredocs, sin `sudo`.
- No emitir comandos bash (encadenados con `&&`, heredocs, `| tee`) para ejecutar en local:
  fallan o se comportan distinto en PowerShell.

## Node.js

- **No hay Node instalado.** No asumir que `npm`, `node`, `tsc` ni `vite build` corren en local.
  La validación de tipos y el build de frontend se hacen en CI o en el destino de despliegue. No
  dar por bueno TypeScript o JS sin haberlo visto compilar ahí.
- Frontend antes de abrir PR: `npm run lint`, `npm run build` y `npm test`, que aquí solo se
  pueden verificar en CI o en la Pi.

## Raspberry Pi (destino remoto)

- La Pi de producción es **Linux/bash**, no Windows. Cualquier comando pensado para la Pi va
  envuelto en una sola invocación SSH: `ssh pi@<host> 'bash -lc "comando"'`. Nunca mezclar
  sintaxis PowerShell dentro de esa cadena, ni asumir que un comando local también corre en la
  Pi.
- **Ficheros systemd**: nunca escribir un unit file con `sudo tee` desde Windows; es propenso a
  fallos silenciosos (puede vaciar el fichero y dejar el servicio enmascarado). Escribir el
  fichero en local, copiarlo con `scp`, y en la Pi `sudo mv` más `sudo systemctl daemon-reload`.
- **Nunca editar ficheros a mano en la Pi ni desplegar con pasos sueltos.** El camino es rama,
  PR, gate en verde, script de deploy del repo, health check. Si el pipeline falla, se arregla
  el pipeline (en su repo, con su PR), no se rodea con un `ssh` y un `nano`.
- Tras cualquier deploy a la Pi, comprobar el endpoint o la página en vivo (curl o navegador) y
  pegar los valores reales observados antes de afirmar que funciona.
- Si el cambio toca layout responsive o varios dispositivos (iPad, móvil, Kindle Scribe, Kobo),
  verificar que los demás siguen renderizando bien; no declarar éxito comprobando solo uno.
- Kindle Scribe y Kobo cachean la app con service worker: antes de verificar en ellos, forzar
  la recarga sin caché (o subir la versión del service worker) y comprobar que la versión que
  se ve es la recién desplegada; si no, se está verificando la anterior.

## Git y GitHub

- `origin/main` es el proyecto de verdad (de ahí despliega la Pi): siempre verde y desplegable.
  Nada es real hasta que se fusiona.
- Ramas `claude/*`, integración a `main` vía PR (`gh pr create --fill`), no push directo.
- **`git push` y `gh pr create` no piden confirmación** (decidido el 2026-09-19): son repos
  personales de una sola persona, el hook `pre-push-verify` corre la verificación antes de que
  salga nada y el gate del CI es quien fusiona, solo en verde. Abrir un PR no-draft es dar la
  orden de fusionar y desplegar; lo que no deba salir todavía se abre como draft. `gh pr merge`
  tampoco pregunta: sirve para fusionar a mano un PR que el gate no cogió (por ejemplo, uno
  anterior al gate), y solo se usa con el CI en verde.
- **No ejecutar `gh pr merge --auto`** salvo que conste que el repo tiene branch protection o
  checks obligatorios de verdad. En un repo privado de plan Free no hay eso, así que `--auto`
  fusiona al instante sin esperar al CI. Si el repo tiene un job `auto-merge` que depende de los
  tests y fusiona por squash solo en verde, ese job es el gate: dejar que actúe él. Sin ese job,
  dejar el PR abierto para que la persona decida. **Un merge a `main` normalmente despliega solo
  a producción** (webhook, script de deploy en la Pi, rollback si falla el health check): es una
  acción con efecto en producción, no un paso inerte.
- Para retener un PR sin que se fusione solo: abrirlo como *draft*; los jobs de auto-merge no
  corren en draft.
