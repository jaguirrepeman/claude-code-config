# Reglas de trabajo (comunes a todas las máquinas)

Lo que depende de la máquina (shell, red, herramientas instaladas) no va aquí: va en
`~/.claude/machine.md`, que se importa al final. Las reglas de un repo concreto van en el
`CLAUDE.md` de ese repo y mandan sobre estas.

## Antes de escribir código

- **Explorar, planificar, ejecutar, verificar.** Para un cambio no trivial: leer lo que hay y
  explicarlo antes de tocar nada, plan corto y aprobado, ejecución con criterio de aceptación,
  verificación en verde. Si la tarea cabe en una frase y toca pocos ficheros conocidos, se salta
  la exploración y el plan.
- **Herramienta existente antes que reimplementar.** Buscar en el repo (CLI, `scripts/`, skills,
  paquetes ya instalados) antes de escribir nada nuevo. Si existe un camino en el repo, se usa
  ese, aunque esté en otro lenguaje.
- **Diagnóstico antes de arreglo.** Ante un bug, una cifra rara o algo lento: (1) hipótesis,
  (2) un comando o medida que la falsifique (conteo, tamaño, traza, tiempo), (3) el output real,
  (4) solo entonces el cambio. Nunca afirmar una causa sin haberla medido. Si la evidencia
  contradice la hipótesis, decirlo y pasar a la siguiente.
- **Plan mode en zonas calientes.** Donde un error no rompe el build sino que cambia un número
  que alguien va a mirar (cálculo, precio, medición), plan mode y no aprobar nada sin leer el
  plan. Cada repo dice cuáles son sus zonas calientes.
- **El plan de un cambio grande se escribe en un fichero** (objetivo, criterio de aceptación,
  ficheros que se tocan, qué se decide no hacer) antes de escribir código, si va a durar más de
  una sesión o el entorno puede cortar la sesión a medias.
- **Exploración amplia, a un subagente.** "Investiga esto" sin acotar se manda a un subagente de
  solo lectura que devuelve la conclusión, no al contexto principal.

## Disciplina de alcance

- Cambio mínimo y aditivo. Añadir una entrada a un fichero de configuración, no regenerarlo
  entero. Nada de refactors oportunistas dentro de un arreglo.
- Antes de refactors grandes o cambios multi-fichero, exponer plan y alcance, y esperar
  confirmación.
- A la segunda corrección fallida sobre lo mismo, parar: limpiar contexto y reescribir el encargo
  con lo aprendido, no seguir corrigiendo encima.

## Verificación antes de decir "hecho"

- "Hecho" significa que un comando corrió y devolvió sí. Si devolvió no, se enseña la salida tal
  cual, sin maquillar.
- **Cada afirmación va con su prueba, o se marca "sin verificar".** Sin término medio: "debería
  funcionar" no es una respuesta; "no he podido comprobarlo" sí lo es. La afirmación no puede ser
  más ancha que la prueba.
- **Todo bug arreglado lleva su test de regresión**, y se ve fallar antes del arreglo y pasar
  después. Las dos ejecuciones son la prueba. El test es el contrato, no la revisión línea a
  línea.
- Tests en verde antes de dar algo por bueno, sean propios o preexistentes. Se puede delegar su
  arreglo, no ignorarlos. Reportar cifras reales ("220/220").
- Tras un arreglo, buscar referencias obsoletas (docstrings, README, changelog, `launch.json`) y
  actualizarlas en el mismo cambio.
- Lo que se ve en una app o en un navegador se verifica ahí, corriendo, no leyendo el código.
- Verificar contra `origin/<rama>`, no contra la copia local: `fetch` primero.

## Git

- **Claude commitea cuando se le pide; no decide por su cuenta que algo merece commit.** `push`,
  fusionar y borrar ramas nunca pasan sin confirmación explícita en cada ocasión.
- **Las ramas las abre Claude, no la persona**, antes de tocar el primer fichero. Una tarea, una
  rama corta, un worktree. Nunca mezclar temas en una rama. Rama corta son horas, no semanas: dos
  días es el límite; si se pasa, la tarea era demasiado grande y se parte.
- **Nunca `git add -A`.** Ficheros explícitos de la tarea, para no arrastrar otro workstream.
- Sincronizar la rama base antes de cada tarea; la copia local tiende a quedarse atrás.
- **Squash para lo que se borra, merge para lo que se queda.** Una rama de trabajo se aplasta al
  integrar (un commit por cambio lógico, revertible con un `git revert`) y se borra, con su
  worktree. Entre dos ramas que siguen vivas, nunca squash.
- Un commit por cambio lógico. Los cambios de `CLAUDE.md` o de configuración compartida van en
  commit propio, nunca dentro de un commit de feature.
- Mensajes: conventional commits con scope, en el idioma del repo. Claude redacta, la persona
  valida.
- Fusionar pronto y a menudo. Nunca más de uno o dos worktrees vivos. Si dos ramas tocan el mismo
  fichero, fusionar una y rebasar la otra; nunca fusionar dos a ciegas.
- Revisar por riesgo, no por volumen: primero que explique qué ha hecho y por qué, y después el
  diff, ya sabiendo dónde mirar. Zona caliente, credenciales, entrada externa o borrado de datos
  se leen enteros.

## Estilo de código

- La lógica de negocio vive en una capa de servicios, no en endpoints ni handlers. Un endpoint
  que pasa de unas 40 líneas lleva lógica que debería vivir aparte.
- **Una regla, un solo sitio.** Antes de añadir una constante o heurística, comprobar si ya
  existe. La lógica duplicada ha causado bugs reales de divergencia.
- `logging`, nunca `print()`. Capturar la excepción concreta, no `Exception` a secas;
  `logger.exception` al tragar una.
- Los comentarios explican el porqué, no el qué.
- Nunca timers falsos ni mockeados en tests async: han colgado CI. Timeouts reales y cortos.

## Comprobaciones antes de pushear

- Python: `ruff check` y `pytest -q` (o lo que use el repo) en local antes de cada push. Que no
  lo descubra el CI si se puede correr aquí. El hook global de lint tras cada edición es
  informativo; esto es la comprobación deliberada.

## Contexto

- Una tarea, una sesión. `/clear` antes de empezar algo no relacionado.
- Al compactar, conservar siempre la lista completa de ficheros modificados y las decisiones
  tomadas.
- Al cerrar una tarea, lo decidido va a un fichero versionado antes de cerrar. La memoria
  automática es índice con punteros al repo, nunca el original.

## Texto

- **Sin em-dashes (—) en nada de lo que se escribe**: documentos, código, comentarios, UI,
  commits. No sustituir por guion (-), que en incisos es falta de ortografía y el mismo tell de
  IA. Reescribir con coma, dos puntos, paréntesis o punto.
- **Español con ortografía completa: tildes y ñ**, en todo, incluidos comentarios y mensajes de
  commit. Excepciones técnicas solo: `.bat` en ASCII puro, y nombres de fichero, rutas e
  identificadores sin acentos.
- Código en inglés (identificadores, ficheros, flags, comentarios) salvo que el repo diga otra
  cosa; documentos internos en el idioma del repo.

## Comunicación

- Responder primero en lenguaje llano, 2 a 4 frases, sin rutas de fichero ni código, y ofrecer
  profundizar. Escalar a referencias de código solo si se pide.
- Por defecto corto: resumen ejecutivo primero, detalle solo si se pide. Sin jerga; si un término
  técnico es inevitable, definirlo en una frase.
- Nunca inventar hechos, cifras, commits ni "áreas de mejora". Si no está en el repo o en los
  datos, escribir "no encontrado" o "no verificado", no rellenar el hueco.
- Los comandos que se dan para pegar en un terminal van en la sintaxis del shell de la máquina
  (ver `machine.md`), no en la del shell de la herramienta.

@~/.claude/machine.md
