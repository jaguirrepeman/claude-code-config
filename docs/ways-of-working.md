# Ways of working con Claude Code

Cómo se trabaja con Claude en un repositorio de verdad: qué prácticas se adoptan, cuáles se
descartan y por qué. El objetivo es doble: **mínimo riesgo** (que una sesión no rompa nada que
cueste recuperar) y **máxima homogeneidad** (que se comporte igual en todas las máquinas y que lo
que aprende una sesión lo herede la siguiente).

Es la parte independiente de proyecto de un framework escrito y puesto en vigor en un repo de
equipo de dos personas en 2026, con máquina corporativa restrictiva. Lo que aquí es regla ya está
destilado en `CLAUDE.md`; este documento es el porqué de cada regla, para no volver a discutirla
desde cero. Cada repo concreto añade su parte II: entorno, zonas calientes, modelo de ramas y
estado.

Fuentes: documentación oficial de Claude Code contrastada con lo que pasa en repos reales. Donde
una práctica oficial no encaja, se dice y se descarta explícitamente.

---

## 1. Principios

1. **El repositorio es la única fuente de verdad compartida.** La memoria automática de Claude
   es local a cada máquina y no viaja: si se pierde el perfil, se pierde con ella, y el código en
   cambio sobrevive porque está versionado. Todo lo que otra persona o la sesión de mañana
   necesita saber acaba en un fichero del repo. (No es hipotético: el borrado de un perfil de
   máquina se llevó la memoria entera, y el código volvió íntegro con un clon.)
2. **Claude propone, la persona decide.** Claude no pushea, no fusiona y no borra sin petición
   explícita. Es regla escrita, y además está respaldada por configuración (7).
3. **Nada se da por terminado sin verificación ejecutada.** El cierre de un cambio de código es
   la verificación en verde, no "parece que funciona".
4. **Contexto pequeño y fresco gana a contexto grande y viejo.** Una tarea por sesión, y limpiar
   entre tareas que no tienen que ver.
5. **La configuración que define comportamiento se versiona; la que define preferencia personal,
   no.** Listas de permisos, reglas y comandos compartidos van a git; el modo de trabajo y las
   comodidades de cada uno van a ficheros locales ignorados.
6. **Una regla que nadie cumple es peor que no tenerla,** porque da por cubierto algo que no lo
   está. Cada regla dice qué la sostiene, y si la respuesta es solo la buena voluntad, se dice
   también.

---

## 2. Las piezas: qué es cada cosa

### 2.1 El contrato: `CLAUDE.md`

Fichero markdown en la raíz del repo (y otro en `~/.claude/` para lo que aplica a todos los
repos). Claude lo carga **entero al empezar cada sesión**, sin que nadie lo pida. Es el único
texto que influye siempre, así que ahí van las reglas que deben cumplirse en todas las tareas.
Está versionado, de modo que cambiarlo cambia el comportamiento de las sesiones de todos.

Reglas para que no se pudra:

1. **Menos de 200 líneas.** Es el límite de la documentación oficial: por encima, la adherencia
   del modelo cae y lo empieza a leer como ruido.
2. **Sustituir, no encadenar.** Cuando una decisión cambia, se reescribe la regla; el relato del
   cambio va al registro de reuniones o al changelog. Bloques del tipo "ACTUALIZACIÓN 22-jul /
   23-jul" apilados son el antipatrón.
3. **Solo reglas verificables.** "Usar `X`, no `Y`" sirve; "cuidado con los precios" no.
4. **Cambiarlo es cambiar la sesión del otro.** Todo cambio de regla va en su propio commit y se
   avisa, con el mismo trato que un cambio de API interna. Nunca dentro de un commit de feature.
5. **Lo que solo aplica a una parte del repo no va aquí,** va a `.claude/rules/` (2.2), que solo
   se carga al tocar esos ficheros. Es lo que permite mantener el límite sin perder detalle.

Qué **no** va: nada que el modelo pueda inferir del código, nada que cambie cada semana (los
estados de tareas van a su propio fichero) y nada de historia. La prueba: "si borro esta línea,
¿Claude comete el mismo error otra vez?". Si no, fuera.

Y lo más importante para entender el resto del documento: **es una instrucción, no una
garantía**. El modelo lo lee y lo sigue con mucha probabilidad, pero no es determinista, y en
una sesión larga la adherencia se degrada. Lo que tiene que cumplirse siempre, sin depender de
que el modelo se acuerde, va a permisos (2.3) o a hooks (2.4).

### 2.2 La carpeta `.claude/`

Es la configuración del proyecto. Qué es cada fichero:

| Fichero | ¿Versionado? | Qué hace |
|---|---|---|
| `settings.json` | Sí | Configuración del proyecto: la lista de permisos y la declaración de los hooks. |
| `settings.local.json` | No | Lo mismo, pero personal de cada máquina: lo que no se le impone al otro. |
| `launch.json` | Sí | Declara los servidores del proyecto con su comando y su puerto, para que Claude pueda arrancarlos y abrir la app sin inventarse el comando. |
| `rules/*.md` | Sí | Reglas por ruta: cada fichero lleva una cabecera `paths:` y solo entra en el contexto cuando la sesión toca esos ficheros. |
| `skills/<nombre>/SKILL.md` | Sí | Procedimientos repetidos, empaquetados y con nombre. |
| `agents/*.md` | Sí | Subagentes propios, con su prompt y sus herramientas. Ver 8 para cuándo compensan. |
| `hooks/` | Sí | Los scripts que ejecutan los hooks (la carpeta es convención, no obligación). |
| `worktrees/` | No | Carpeta de trabajo de los worktrees, local a la máquina. |

Cuidado con el `.gitignore`: si ignora `.claude/` entero, todo lo que se cree ahí queda fuera de
git **en silencio** y cada máquina diverge sin que nadie lo vea. Se des-excluye el directorio y
se re-excluye solo lo personal, porque git no desciende en un directorio excluido.

```gitignore
!.claude/
.claude/settings.local.json
.claude/worktrees/
```

### 2.3 Permisos y modos

Que Claude pueda hacer algo solo o tenga que preguntar depende de dos cosas distintas, y
conviene no confundirlas.

La **lista de permisos** de `settings.json` es explícita y determinista: `allow` se ejecuta sin
preguntar, `ask` pregunta siempre aunque una sesión anterior lo aceptara, `deny` no se ejecuta
nunca. No depende de que el modelo recuerde nada y manda en cualquier modo.

El **modo de la sesión** es el ajuste general. Se cambia sobre la marcha:

| Modo | Qué hace |
|---|---|
| **Auto** | Un clasificador mira cada acción: deja pasar el trabajo rutinario y frena lo que puede hacer daño. Es el modo por defecto en los planes de pago. |
| **Manual** | Pregunta por cada edición y cada comando; leer es gratis. Su valor en la configuración se llama `default`, lo que despista. |
| **Plan** | Solo lectura: no puede escribir hasta que apruebas el plan (4.2). |
| **Aceptar ediciones** | Las escrituras de fichero dejan de preguntar; los comandos siguen preguntando. |
| **Bypass** | Sin ningún control. Descartado siempre (8). |

Que el modo por defecto sea auto tiene una consecuencia que hay que entender: el clasificador
juzga por peligro técnico, no por tus normas. Un commit, para él, es rutina. Por eso las listas
`ask` y `deny` siguen importando: son donde se pone el límite propio. **Y el límite razonable no
es el commit, es el push.** Un commit es local, no lo ve nadie y se deshace con un `git revert`,
así que pararse en cada uno es fricción sin beneficio; lo que sale del repo local ya lo ve el
otro y deshacerlo cuesta. Y en un repo personal con gate de CI, tampoco el push: la rama es
propia, el hook de push verifica antes de que salga nada, y quien fusiona es el gate, solo en
verde. Ahí el límite se mueve a lo que se salta el gate (fusionar a mano) o no se deshace
(borrar ramas, `reset --hard`). Cada `machine.md` dice cuál de los dos casos aplica.

**Cómo crece la lista.** Cuando aceptas un permiso en caliente con la opción de no volver a
preguntar, esa decisión se escribe en un fichero y sigue viva mañana. Va al `settings.local.json`
personal. La regla es distinta para cada fichero: el personal puede crecer solo, y **el
compartido solo crece por commit revisado**, para que diga lo que alguien decidió y no lo que
alguien clicó con prisa.

El modo es preferencia de cada persona, así que vive en el fichero local o se cambia en
caliente, nunca en el compartido.

### 2.4 Hooks, skills y subagentes

Las tres formas de que algo pase sin escribirlo a mano cada vez, y no son intercambiables.

- **Hook.** Un comando del sistema que la herramienta ejecuta por su cuenta en un momento fijo
  del ciclo, declarado en `settings.json`. Es **la única vía determinista**: pasa aunque el
  modelo no se acuerde. Recibe por su entrada estándar el contexto de lo que acaba de ocurrir y
  decide con su código de salida o con un JSON, donde 0 deja seguir y `deny` o `block` paran y
  devuelven el motivo para que se arregle. Los momentos útiles: `SessionStart` (al abrir la
  sesión), `PreToolUse` (antes de usar una herramienta, puede bloquearla), `PostToolUse` (justo
  después, por ejemplo para pasar lint al fichero recién tocado) y `Stop` (cuando va a cerrar el
  turno).
- **Skill.** Un procedimiento escrito una vez y guardado con nombre, en
  `.claude/skills/<nombre>/SKILL.md` (o `~/.claude/skills/` si vale para todos los repos). Se
  versiona, se invoca por su nombre y, si se deja, el modelo la elige solo cuando encaja con su
  descripción. Es la respuesta a "esto lo pedimos cada semana y cada uno lo pide distinto".
- **Subagente.** Una sesión hija con su propio contexto que recibe un encargo acotado y devuelve
  solo la conclusión. Sirve para no llenar el contexto principal con la búsqueda, y para revisar
  sin el sesgo de quien escribió el código.

**Subagente o sesión aparte.** Se confunden porque los dos delegan, y el criterio no es el
tamaño de la tarea, es a dónde vuelve el resultado:

- **Vuelve a esta conversación** para seguir trabajando con él: subagente. Lee, busca o revisa,
  devuelve una conclusión y no deja ni ficheros ni rama detrás.
- **Vuelve al repo por su propia rama**, con sus commits y puede que varias conversaciones:
  sesión aparte con worktree (6.3).

La prueba rápida: si lo que produce hay que ir a buscarlo a otro árbol de trabajo para traerlo
aquí, era un subagente y lo mandaste a una sesión aparte.

### 2.5 La memoria automática

Claude va anotando por su cuenta lo que aprende trabajando: decisiones del proyecto, cómo
prefieres que se escriba, cabos sueltos. No lo guarda en el repo, sino en el perfil de usuario
**de esa máquina**, así que esas notas son de esa persona y de ese ordenador: nadie más las ve, y
si se pierde el perfil se pierden.

La consecuencia práctica es una regla: **nada que otro necesite saber puede vivir solo ahí**. Lo
que se escribe en memoria son punteros ("esto se decidió así, está en tal documento") y el
contenido de verdad vive versionado en el repo. Es el principio 1 aplicado.

---

## 3. Manejar la sesión

Esta sección es la que más depende de la versión y del cliente (app de escritorio, terminal o
editor). La lista viva de atajos la tienes en la propia app; aquí van solo los que cambian cómo
se trabaja.

Aviso de teclado: los atajos suelen documentarse para teclado americano, donde el `/` tiene
tecla propia. En un teclado español el `/` es Shift+7, así que un atajo escrito como Ctrl+`/` se
teclea Ctrl+Shift+7, y hay combinaciones que directamente no llegan a la aplicación.

### 3.1 Atajos que cambian cómo trabajas

| Atajo | Para qué |
|---|---|
| **Esc** | Interrumpir al modelo a media respuesta. El más importante de todos: cortar pronto vale más que dejarle terminar algo que vas a tirar. |
| **Esc Esc** | Abrir el menú de rewind, para deshacer código o conversación (3.4). |
| **Shift+Tab** | Ciclar entre modos de permiso, plan mode incluido (2.3). |
| **Ctrl+G** | Abrir el plan en tu editor para corregirlo antes de aprobarlo (en plan mode). |
| **Ctrl+O** | Cambiar el nivel de detalle de la vista: normal, todo lo que hace, o solo conclusiones. |

### 3.2 Comandos del día a día

| Comando | Para qué |
|---|---|
| `/clear` | Empezar limpio. Lo que separa una tarea de la siguiente. |
| `/compact` | Resumir la conversación y seguir en ella (3.3). |
| `/context` | Ver cuánto contexto se está usando y qué lo ocupa. |
| `/rewind` | Deshacer cambios de código o volver atrás en la conversación (3.4). |
| `/resume` y `/rename` | Volver a una conversación anterior, y ponerle nombre para que eso sirva de algo. |
| `/branch` | Copiar la conversación hasta aquí a otra, para probar un camino sin perder el que iba bien. |
| `/memory` | Ver y gestionar lo que la memoria automática ha guardado (2.5). |
| `/code-review` | Revisar el diff en una sesión que no lo escribió (5.1). |
| `/btw` | Preguntar algo al margen: la respuesta no entra en el historial. |
| `/usage` | Ver el consumo y qué lo está causando. |
| `/insights` | Informe de cómo se ha trabajado en las últimas sesiones: fricciones, patrones, qué convertir en regla o skill. |
| `/init` | Generar un `CLAUDE.md` inicial analizando el repo, si aún no hay. |

### 3.3 El contexto: `/clear`, `/compact` y la compactación automática

La ventana de contexto se llena, y lo que hagas cuando se llena decide si la sesión sigue siendo
buena o empieza a inventar.

- **`/clear`** empieza de cero: se va todo el historial y se recargan las instrucciones. Es lo
  que se usa **entre tareas que no tienen que ver**.
- **`/compact`** se queda en la misma tarea pero comprime lo anterior en un resumen: conserva
  las decisiones y lo que se ha cambiado, y tira el ruido. Se usa **dentro de la misma tarea**
  cuando el contexto se llena y todavía queda trabajo. Admite instrucciones, del tipo `/compact
  céntrate en los cambios de la API`.
- **La compactación automática** hace eso mismo sola al acercarse al límite. Funciona, pero
  decide ella qué es ruido, así que llegar ahí es peor que compactar tú a tiempo. Se le puede
  dar criterio desde `CLAUDE.md` ("al compactar, conserva siempre la lista completa de ficheros
  modificados"), para que lo que no puede perderse sobreviva al resumen.

La regla práctica: si te has visto corrigiendo lo mismo dos veces, no compactes, limpia y vuelve
a empezar con un prompt mejor. Arrastrar un contexto contaminado sale más caro que reescribir el
encargo.

**Archivar la conversación y abrir otra hace lo mismo que `/clear`.** Lo que importa no es el
mecanismo, es no arrastrar una tarea dentro de otra. Y una trampa: como no cuesta nada, es fácil
acabar con veinte conversaciones abiertas y ninguna cerrada de verdad, es decir, sin lo
aprendido volcado a un fichero (4.4). Cerrar una conversación no es archivarla, es haber
escrito lo que hay que escribir antes de archivarla.

### 3.4 Deshacer: checkpoints y `/rewind`

La herramienta guarda una copia de los ficheros antes de cada cambio, así que **Esc Esc** o
`/rewind` permiten volver atrás en el código, en la conversación o en las dos cosas.

Con una limitación que hay que tener muy presente: **los checkpoints no cubren lo que hizo un
comando de shell.** Si se ejecutó un `rm`, un `git reset` o un build que sobreescribió algo, eso
no vuelve con rewind. Para eso está git, y por eso las acciones que salen del repo local viven
en la lista `ask` (2.3).

---

## 4. El flujo de trabajo por sesión

### 4.1 El ciclo: explorar, planificar, ejecutar, verificar

Es el flujo oficial recomendado y el que menos retrabajo genera:

1. **Explorar.** Pedir que lea los ficheros relevantes y explique lo que hay antes de tocar
   nada. Para búsquedas amplias, un subagente de exploración (2.4), que no contamina el contexto
   principal.
2. **Planificar.** Para cambios no triviales, pedir plan y leerlo antes de aprobar. El plan es
   el momento barato de corregir; el código es el caro.
3. **Ejecutar.** Con criterio de aceptación explícito en el prompt (4.3).
4. **Verificar.** La verificación del repo en verde y, si el cambio se ve en la app, verlo
   corriendo (5).

Cuándo saltarse los pasos 1 y 2: la tarea cabe en una frase y toca pocos ficheros de una zona
que conoces (renombrar, un log, un texto de la interfaz).

### 4.2 Plan mode obligatorio en las zonas calientes

Hay ficheros donde un error no rompe el build, sino que cambia un número que alguien va a mirar.
En esos se activa plan mode (2.3) y no se aprueba nada sin leer el plan. Cada proyecto tiene los
suyos; lo importante es que estén **escritos** en su `CLAUDE.md`, no que se sepan.

Para el resto (interfaz, documentos, scripts auxiliares), plan mode es opcional.

### 4.3 Prompts con criterio de aceptación

Un prompt sin verificación produce código que "parece terminado". La forma de cerrar el bucle es
dar algo ejecutable contra lo que iterar:

- Mal: "mejora el cálculo de impacto".
- Bien: "el impacto de la fila X debe dar Y con estos datos; añade un test que lo fije, hazlo
  pasar y corre la verificación".

Que el criterio vaya en el prompt no lo hace opcional: la verificación hay que pasarla igual
(5.1). Lo que cambia es quién itera. Escrito en el prompt, Claude repite hasta que pasa y te
entrega algo ya verificado; sin escribirlo, te entrega algo que parece terminado y el que
comprueba eres tú.

Y el complemento, cuando lo que hay es un bug y no una feature: **diagnóstico antes de arreglo**.
Hipótesis, un comando que la falsifique, el output real, y solo entonces el cambio. La causa
afirmada sin medir sale mal con una frecuencia que no compensa el tiempo que ahorra: cada
diagnóstico equivocado son dos rondas más.

### 4.4 Higiene de contexto

- **Una tarea, una sesión.** `/clear` antes de empezar algo no relacionado; una sesión larga
  arrastra exploraciones fallidas y degrada la adherencia a las reglas.
- **Cortar pronto.** Si va por mal camino, Esc y redirigir. No dejarle terminar para luego tirar
  el resultado.
- **Al cerrar, documentar.** Lo que se ha decidido va a un fichero versionado antes de cerrar.
  Es lo que hace que las sesiones de uno alimenten a las del otro, dado que la memoria
  automática no se comparte (2.5).

### 4.5 El plan de un cambio grande se escribe en un fichero

Plan mode resuelve el plan **dentro** de la sesión: lo lee quien la lleva y desaparece con ella.
Para un cambio que vaya a durar más de una sesión, que toque la zona de otra persona, o en un
entorno donde la sesión puede cortarse (red corporativa, límites de uso), el plan se vuelca a un
fichero corto antes de escribir código: objetivo, criterio de aceptación, qué ficheros se tocan
y qué se decide **no** hacer.

Es el principio 1 aplicado al plan, y es además lo que la literatura de agentes llama trabajar
desde la especificación en vez de desde el prompt. No aplica a lo pequeño: si la tarea cabe en
una frase, el plan es la frase.

### 4.6 Los cinco fallos que se repiten

La documentación oficial los lista, y los cinco pasan:

| Fallo | Cómo se ve | Salida |
|---|---|---|
| La sesión cajón de sastre | Empiezas una tarea, preguntas otra cosa, vuelves a la primera | `/clear` entre tareas sin relación |
| Corregir una y otra vez | Corriges, sigue mal, vuelves a corregir | A la segunda corrección fallida, limpiar y reescribir el encargo con lo aprendido |
| El `CLAUDE.md` inflado | Tiene tantas reglas que ignora la mitad | Podar sin piedad, y convertir en hook lo que tenga que cumplirse siempre |
| Confiar y no comprobar | Sale algo plausible que no cubre los casos raros | Verificación siempre: si no puedes comprobarlo, no lo entregues |
| La exploración infinita | "Investiga esto" sin acotar, y se lee media base de código | Acotar, o mandarlo a un subagente para que no consuma tu contexto |

---

## 5. Verificación

### 5.1 La definición de hecho

**Qué queremos decir con "hecho".** No "parece que funciona" ni "lo he probado a ojo": un
comando corrió, y devolvió sí o no. Si el resultado es no, se dice con su salida tal cual, sin
maquillarla. Ese comando es uno solo, vive en un único sitio, y todo lo demás (el `.bat`, el
`.sh`) son envoltorios de tres líneas que solo localizan el intérprete y lo llaman. Si cada
máquina tuviera su propia copia de los pasos, acabarían separándose sin que nadie lo decidiera.

Tiene dos velocidades porque no todo momento pide lo mismo: la ejecución completa para cerrar un
cambio, y una corta sin tests para lo que tiene que correr a menudo. Un hook que tarda se acaba
desactivando, así que lo que corre en cada turno tiene que ser barato.

**Los tests nuevos fijan comportamiento de negocio, no cobertura.** Cuando se arregla un bug,
primero el test que lo reproduce, y se ve fallar; después el arreglo, y se ve pasar. Es la única
defensa real contra que el mismo bug vuelva.

**Cuándo pasa por revisión con contexto limpio.** `/code-review` mira el diff en una sesión que
no lo escribió, así que ve el cambio y el criterio pero no el razonamiento que lo produjo. Tres
casos, y el motivo es siempre el mismo, que quien lo escribió ya no es un juez imparcial:

- El cambio toca zona caliente (4.2).
- El diff es más grande de lo que te cabe en la cabeza de una sentada.
- La sesión ha sido larga o ha ido y venido: cuanto más ha peleado el modelo con el problema,
  más convencido está de su solución.

Fuera de esos tres casos no hace falta: pasa la verificación y se lee la lista de ficheros
tocados.

Un aviso de la propia documentación oficial: pedirle a un revisor que encuentre huecos casi
siempre le hace encontrar alguno, esté bien o no el trabajo, porque es lo que se le ha pedido.
Perseguir todos los hallazgos lleva a sobreingeniería. Hay que decirle que marque solo lo que
afecta a la corrección, y que el resto es opcional.

**Verificar en la app lo que se ve en la app.** Un cambio de pantalla no está hecho hasta verlo
corriendo, y no hay que hacerlo a mano: es 5.2.

### 5.2 La IA como validador

**El problema.** El agente que escribe el código no puede certificarlo. Si decide él solo si su
trabajo está bien, eso no es verificación, es autoconfirmación; y si escribe el código y sus
tests en la misma sesión, los tests fijan lo que el modelo entendió, no lo que se pedía.

**La salida** no es dejar de usarlo para verificar, es **darle control para que compruebe en vez
de que afirme**. La diferencia práctica está entre "el cambio funciona" y "he levantado la API,
he abierto la pantalla, la fila X da Y, aquí está la captura y la respuesta del endpoint". Leer
la evidencia es más rápido que rehacer tú la comprobación.

**Cuatro formas de comprobar:**

| Qué se verifica | Cómo | Evidencia |
|---|---|---|
| El diff | Revisión en una sesión que no lo escribió (`/code-review`) | Lista de hallazgos |
| La pantalla | Levantar la app, navegar y pulsar | Captura y las cifras que se ven |
| Una cifra | Recalcularla por un camino distinto del que la produjo | Los dos números y su diferencia |
| Un endpoint | Llamarlo directo contra la API | La respuesta cruda |

En las cuatro aplica lo mismo: lo que no vale es recalcular con el mismo código que acaba de
escribir, porque eso no es un segundo camino, es el mismo camino dos veces.

**Las reglas para que la evidencia valga algo:**

- **Al verificar un arreglo, el criterio lo pones tú y el test lo escribe Claude.** Si no dices
  qué tiene que dar, el test fijará lo que el código hace hoy, no lo que debería, y pasará en
  verde sin decir nada.
- **Cada afirmación va con su prueba, o se marca como no verificada.** Sin término medio. "No he
  podido comprobarlo" es una respuesta válida; "debería funcionar" no lo es. Es comportamiento
  del modelo, así que es instrucción y va en `CLAUDE.md`, no en un hook.
- **La afirmación no puede ser más ancha que la prueba.** "La pantalla pinta 214 filas y la
  primera recomienda 39,90" lo prueba una captura. "La recomendación está bien" no lo prueba
  ninguna.
- **Verificar y arreglar no se encadenan solos.** Si al comprobar sale un fallo, el arreglo es un
  cambio nuevo con su diff, no una corrección dentro del mismo turno seguida de una segunda
  comprobación propia: eso es autoconfirmación con un paso más.
- **Lo que valida el cliente no se valida con capturas.** La IA verifica que el código hace lo
  que dice hacer, no que el número sea el correcto para el negocio.

**Cuánto se automatiza, por escalones.** Subir solo lo que haga falta:

| Escalón | Qué es | Cuándo |
|---|---|---|
| En el prompt | "haz esto, corre la verificación y arregla lo que falle" | Siempre. Funciona hoy y no hay que montar nada |
| Condición de objetivo | Se fija una condición y la sesión no para hasta cumplirla | Tareas largas que quieres dejar corriendo |
| Hook de cierre | La verificación bloquea el cierre del turno (7) | Cuando lo anterior se olvida más de una vez |
| Revisor independiente | Un subagente en contexto limpio intenta refutar el resultado | Antes de dar por bueno algo que nadie ha mirado |

Los dos primeros son gratis y son los que más rinden. El cuarto es el que cierra el agujero de
esta sección, porque el que juzga no es el que trabajó.

**La skill de verificar pantalla.** Cuando la segunda fila de la tabla se pide a menudo con los
mismos pasos, se empaqueta como skill con dos detalles de diseño: corre en **contexto propio**
(`context: fork` en la cabecera), así no hereda el de la sesión que escribió el código, y por
eso el cuerpo lleva dentro cómo se levanta la app y qué se mira; y **no arregla nada**, devuelve
afirmaciones con su prueba, marca como no verificado lo que no pudo comprobar y para. Lo que
falle vuelve a la sesión de trabajo como un cambio nuevo con su diff.

**Límite de lo que se le da.** Levantar servidores locales y navegar, sí. Builds, push y
fusiones siguen en la lista `ask`: verificar no es entregar.

---

## 6. Git con agentes

### 6.1 Commits y qué se revisa

- **Claude commitea cuando se lo pides; no decide por su cuenta que algo merece un commit.** Si
  dices "arregla el texto de esa columna y commitea", lo hace sin volver a preguntar, porque un
  commit es local y se deshace con un `git revert` (2.3). Si terminas una tarea y no dices nada,
  espera a que se lo pidas. Y `push` y fusionar nunca pasan sin confirmación explícita en cada
  ocasión, porque ahí el cambio deja de ser solo tuyo.
- **Qué se revisa antes de un commit.** La práctica establecida para revisar código generado
  por IA se apoya en tres cosas, y ninguna de ellas es leérselo entero:

  1. **No es lo mismo que revisar el código de un compañero.** El de un compañero falla de
     formas que se notan. El de la IA sale plausible, ordenado y bien nombrado, y esa apariencia
     de corrección es la trampa: lo que hay que buscar no es una errata, es una suposición
     equivocada, y eso no salta leyendo líneas.
  2. **Alguien responde por el diff.** La pregunta de control es "qué comprobaste", y "lo dijo
     Claude" no es una respuesta.
  3. **Se revisa por riesgo, no por volumen.** Cuatrocientas líneas de interfaz pueden necesitar
     menos atención que ocho en el cálculo del margen.

  De ahí sale un orden que es el contrario del que se hace por defecto: **primero que explique
  qué ha hecho y por qué, y después miras el diff**, ya sabiendo dónde mirar. Y tres niveles:

  | Nivel | Qué entra | Qué se hace |
  |---|---|---|
  | Alto | Zona caliente (4.2), y todo lo que toque credenciales, entrada externa o borrado de datos | Se lee el diff entero, una persona, sin excepción |
  | Medio | Cambios de comportamiento fuera de zona caliente | Explicación primero, revisión con contexto limpio (5.1) y lectura de los ficheros tocados |
  | Bajo | Documentos, textos, renombrados, scripts auxiliares | Verificación en verde y a otra cosa |

  La seguridad entra en el nivel alto a propósito: está medido que el código generado trae más
  vulnerabilidades por línea que el escrito a mano, y eso el lint no lo caza.

  Mirar la lista de ficheros tocados, aunque no se lea el contenido, sigue valiendo la pena en
  cualquier nivel: es donde se ve el fichero que no pintaba nada en esa tarea.

- **Mensajes:** conventional commits con scope, en el idioma del repo. Claude redacta el
  mensaje; la persona lo valida.
- **Un commit por cambio lógico.** Los cambios de `CLAUDE.md` o de la configuración compartida
  van siempre en commit propio.

### 6.2 Ramas: las tres formas de fusionar, y cuál toca

- **Merge commit** (`git merge --no-ff`): la rama entra con todos sus commits y se añade uno
  extra que une las dos historias.
- **Squash** (`git merge --squash`): git coge todo lo que hizo la rama, sean 2 commits o 30, y
  lo escribe en el destino como **un único commit nuevo**. Los commits originales no viajan, y
  ese commit único es, para git, algo que no había visto antes, sin relación registrada con los
  commits de los que salió.
- **Fast forward** (`git merge --ff-only`): si el destino no ha cambiado desde que la rama salió
  de él, git solo mueve la etiqueta del destino hasta el último commit de la rama.

**La regla que se deriva: squash para lo que se borra, merge para lo que se queda.** Una rama de
trabajo es corta y desechable, y una sesión de IA la llena de pasos intermedios: el intento, la
corrección del intento y el arreglo del formato. Lo que tiene que sobrevivir es el cambio
terminado, una entrada por cambio lógico, revertible con un solo `git revert`. En cambio, entre
dos ramas que siguen vivas, el squash es veneno: git deja de saber que ese trabajo ya está en
las dos, y en la siguiente fusión vuelve a ofrecer los mismos cambios como nuevos, con conflictos
que no tienen sentido y que empeoran en cada vuelta.

**Qué quiere decir rama corta.** Horas, no semanas. DORA lleva años midiendo qué distingue a los
equipos que entregan rápido y con pocos fallos, y una de sus conclusiones más repetidas es que
las ramas que viven menos de un día son una de las señales más fuertes de un equipo que va bien.
La regla:

- La rama se abre para la tarea de hoy y se cierra hoy. Es el caso normal.
- Si al final del día sigue abierta porque falta poco, se termina mañana a primera hora. Dos
  días es el límite, no la costumbre.
- Si llegan los dos días y sigue abierta, no se alarga más: se para y se parte la tarea en piezas
  más pequeñas. El síntoma de una rama larga no es la rama, es que la tarea era demasiado grande.

**Las ramas las abre Claude, no tú.** Pides "arregla el texto de esa columna", y antes de tocar
ningún fichero, lo primero que pasa es `git checkout -b fix/texto-columna` (o el prefijo que
toque). Así nunca se cuela un cambio directamente en la rama protegida sin que nadie haya
abierto una rama para él.

Esto es una instrucción, no un mecanismo (2.1): se sigue porque se lee al empezar cada sesión,
pero puede fallar si se olvida. La red que no depende de que se acuerde es un hook que bloquea
directamente el `commit` mientras se esté en la rama protegida (`hooks/block-commit-on-protected.py`).

### 6.3 Un worktree por tarea, obligatorio, no opcional

Un worktree es un checkout adicional del mismo repo, en otra carpeta y con otra rama, que
comparte el mismo `.git`. Hay dos formas de entrar en uno:

- **Desde fuera** (el selector de sesiones, o `claude --worktree`): abre **una sesión aparte**,
  con su propio contexto.
- **Desde dentro de una sesión ya en marcha**, con la herramienta `EnterWorktree`: la sesión
  sigue siendo la misma, solo cambia el directorio en el que corren sus herramientas.

Las dos dan el mismo aislamiento de ficheros y de rama; lo que cambia es si es una conversación
nueva o la misma continuando en otro sitio.

**Por qué es obligatorio y no una buena práctica más:** dos sesiones sin worktree que comparten
el mismo checkout se pisan. Una abre una rama con `git checkout -b` sin que la otra lo sepa, y el
`HEAD` compartido empieza a devolver una rama distinta según qué sesión pregunte. Abrir rama con
`git checkout -b` no protege de esto: sigue siendo el mismo directorio para las dos. Solo un
worktree lo hace.

**Un límite que hay que conocer:** ni un hook ni ninguna otra pieza puede forzar esto desde
fuera. `EnterWorktree` solo se dispara cuando el usuario dice la palabra worktree, o cuando una
instrucción de `CLAUDE.md` lo pide explícitamente. Si una sesión no lee `CLAUDE.md`, o lo lee y
no lo sigue, nada se lo impide.

**Otro límite al entrar:** por defecto, un worktree nuevo se crea desde la rama por defecto que
git tiene registrada para `origin` (`refs/remotes/origin/HEAD`). Si la rama de integración es
otra (`dev`, `develop`), hay que arrancar la rama corta explícitamente desde ella:
`git checkout -b <prefijo>/<nombre> <rama-de-integración>`. Y git no permite tener la misma rama
desplegada en dos worktrees, así que la rama de integración no se puede "heredar": se arranca
de ella, no en ella.

La práctica, en cuatro pasos:

1. Tarea nueva: `EnterWorktree`, y ya dentro, la rama corta desde la rama de integración.
2. Se trabaja ahí hasta terminar, con la verificación en verde antes de cerrar.
3. Se integra con squash. Si la integración es local, no se puede hacer desde el worktree:
   primero `ExitWorktree` con `action: "keep"` (el trabajo ya está commiteado en la rama), y
   desde el checkout principal, `git merge --squash <rama>` y el commit único. Si la integración
   es por PR, el PR se abre desde la rama y se fusiona con squash en el servidor.
4. **Se borra el worktree y la rama**: `git worktree remove <ruta>` y `git branch -D <rama>`
   (`-D` porque tras un squash git no sabe que la rama ya está fusionada). Este es el paso que
   todo el mundo se salta: los worktrees no se limpian solos, y en dos semanas tienes seis
   carpetas y no sabes cuál tiene algo sin fusionar.

Cuándo no hace falta: una tarea que cabe en una frase (renombrar, un texto, un log) se queda en
el checkout principal.

Lo que hay que preparar en cada worktree nuevo: lo que no está en git no viaja. Dependencias
instaladas (`node_modules`, `.venv`), ficheros de entorno y cachés hay que rehacerlos ahí, o
apuntar a los de la raíz.

### 6.4 Releases: saber qué versión tiene el cliente

Cuando lo que se entrega es un binario que alguien instala, hay dos preguntas que el repo tiene
que poder contestar meses después: qué versión está usando, y con qué datos. Si no se puede
contestar, cualquier medición sobre esa entrega es discutible.

1. **Una versión por entrega.** Se sube la versión, se etiqueta el commit y ese tag es el nombre
   de la entrega. La convención habitual añade el commit como metadato de build, del estilo
   `0.3.0+a1b2c3d`.
2. **Un manifiesto dentro del paquete.** El script que construye el paquete escribe al lado un
   `manifest.json` con versión, commit, fecha de build y la fecha de cada dato.
3. **Que la app lo enseñe.** Una marca de agua del tipo `v0.3.0 · datos al 30-08-2026` en la
   barra superior: el usuario la lee por teléfono y los dos sabéis contra qué estáis comparando.

**Cuándo se pone el tag: al construir, no en cada push.** La rama protegida es el código, el
tag es una entrega, y no todo push es una entrega. Etiquetar en el momento del build captura
exactamente lo que hace falta: alguien decidió, a propósito, que este código se convierte en lo
que va al cliente.

---

## 7. Automatizar: qué hook, y cuándo

El criterio para decidir si algo va a un hook es simple: **¿tiene que cumplirse aunque nadie se
acuerde?** Si la respuesta es sí y además se puede comprobar con un comando, es un hook. Si no,
es una instrucción, y entonces asume que a veces no pasará.

El segundo criterio es el tiempo. Un hook que corre en cada turno tiene que ser de segundos: si
molesta, alguien lo quita, y entonces no protege nada.

| Momento | Para qué sirve | Coste típico |
|---|---|---|
| `SessionStart` | Informar del estado al abrir: rama, si hay cosas sin commitear, si falta bajar algo | Segundos, y no debe tocar nada |
| `PostToolUse` sobre edición | Lint o formato del fichero recién tocado, solo ese | Sub-segundo |
| `Stop` | Impedir cerrar el turno si la verificación rápida falla | Los segundos que tarde la verificación corta |
| `PreToolUse` sobre push | Exigir la verificación completa antes de que algo salga | Lo que tarde, pero pasa poco |
| `PreToolUse` sobre commit | Bloquear el commit en la rama protegida | Milisegundos |

Los hooks de este repo (`hooks/`) siguen tres reglas de diseño que conviene mantener en
cualquiera nuevo: **fallan abiertos** (si no pueden comprobar, dejan pasar; solo bloquean con
prueba de que algo falla), **devuelven la salida del fallo, no un "falló"** (el modelo necesita
el mensaje de ruff o el traceback para arreglarlo sin volver a ejecutar), y **nunca salen con
error** (un problema en el hook no puede dejar la sesión atrapada).

Cosas aprendidas que conviene no repetir:

- **Un `git pull` automático al arrancar es mala idea.** Si estás a mitad de un cambio, o falla o
  te mete una fusión que no elegiste. Informar sí; tocar el árbol de trabajo, no.
- **Un hook no puede invocar `/code-review`**, y conviene entender por qué: un hook no es una
  sesión de Claude, es un script que la herramienta ejecuta por su cuenta, sin modelo. Y aunque
  se pudiera, colgarlo del push sería el sitio equivocado: en un día normal se empuja la misma
  rama varias veces mientras se itera. El diff solo merece que alguien lo juzgue una vez, cuando
  se va a integrar.
- **El hook de `Stop` que verifica en cada turno se apaga solo.** Escrito y probado: 5 a 9 s en
  cada respuesta, también en las que no tocan código, es la fricción diaria que hace que alguien
  lo quite. La misma regla se cubre en el push, que es cuando el código le llega a otra persona.
  Se deja escrito y apagado, con el disparador anotado: si se cuela código roto entre turnos, es
  el que se enciende.
- **Del bucle infinito te protege la herramienta:** si un hook de cierre bloquea varias veces
  seguidas, se rinde y deja cerrar. Aun así, el hook debe decir con claridad qué falla.

**Detectar skills nuevas sin depender de que se te ocurra.** Una skill nace de un procedimiento
que ya se ha repetido, así que la pregunta no se contesta pensando, se contesta mirando atrás.
Cada revisión periódica lleva una pasada corta: qué se ha pedido tres veces desde la última vez,
leyendo el historial de commits y las actas. `/insights` hace parte de esa pasada solo. Lo que se
acepta y lo que se descarta, con su motivo, se apunta (README, sección de skills) para no volver
a proponer lo descartado sin un motivo nuevo.

Cualquier hook o skill que se adopte se versiona y, si el repo es compartido, se estrena
avisando al otro, porque cambia también sus sesiones.

**Pasada de `/insights` del 2026-09-19** (63 sesiones, del 4 al 19 de septiembre; casi toda la
configuración actual entró los días 17 y 18, así que la fricción que cuenta es en gran parte
anterior a ella). Aceptado: `/repo-hygiene`; tres reglas en `CLAUDE.md` (delegar el mismo
cambio en varios repos, muestra antes de generar en serie, dos intentos y preguntar ante
"retoma aquello"); en `machine.md`, nunca editar a mano en la Pi y cache bust del service
worker antes de verificar en Kindle o Kobo; captura de navegador como evidencia en
`/deploy-pi`. Descartado: `/ship` (el flujo rama, PR, gate, deploy ya está en reglas y en el
gate; una skill sería un tercer sitio que dice lo mismo; se revisa si la próxima pasada
muestra que se sigue reexplicando); el enjambre de seis subagentes con seis worktrees por
auditoría (contradice "nunca más de uno o dos worktrees vivos" de 6.3; si se quiere, es una
decisión sobre esa regla, no una skill); un hook que corra ruff sobre todo el repo tras cada
edición (ya descartado en 8: lint del fichero tocado, sí). Pendiente sin decidir: un agente
de mantenimiento que compare cada repo con `templates/project/` y abra un PR por el drift.

---

## 8. Descartado, y por qué

- **`bypassPermissions` y el auto-accept total.** Nunca. Elimina la única barrera entre una
  alucinación y un borrado o un push. El camino para reducir fricción es crecer la lista `allow`
  con criterio, no quitar el freno.
- **Subagentes propios definidos en `.claude/agents/` de un repo de equipo pequeño.** Lo que se
  descarta es guardar una definición propia por repo; lo que sí se usa es la idea de detrás, que
  es contexto aislado. Un subagente empieza sin memoria de la conversación: no ha visto lo que se
  le pidió a Claude ni por qué tomó las decisiones que tomó, y es justo lo que hace falta para
  que revise sin el sesgo de "esto está bien porque lo acabo de escribir yo". Se consigue
  pidiéndolo ("usa un subagente para revisar X"), sin nada guardado. Guardar uno compensa cuando
  se quiere el mismo papel fijo, invocado muchas veces, en muchos proyectos: por eso
  `agents/repo-auditor.md` vive a nivel de usuario y no de repo.
- **Compartir la memoria automática entre máquinas.** Va contra su diseño: lo compartible vive
  en el repo como documento, la memoria es índice local (2.5).
- **Confiar a la memoria una regla de comportamiento.** Puede perderse o estar desactualizada.
  Una regla que debe cumplirse siempre va a `CLAUDE.md` si basta con que el modelo la siga, y a
  permisos o hooks si tiene que cumplirse aunque no se acuerde: esos dos sí son deterministas,
  `CLAUDE.md` no (2.1).
- **Un hook `PostToolUse` que corra los tests tras cada edición.** Los tests tardan; el hook se
  apaga en una semana. Lint del fichero tocado sí (sub-segundo); tests, en el push.
