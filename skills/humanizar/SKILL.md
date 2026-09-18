---
name: humanizar
description: Revisa un texto en español o en inglés (un fichero o un texto pegado) y reescribe lo que suena a generado por IA sin cambiar lo que dice. Trae un detector (tells.py, sin dependencias) que cuenta los tells y lista los candidatos con fichero:línea, y cuatro pruebas para decidir cada contraste "no es X, es Y". Úsala antes de cerrar un documento, un correo o un entregable, o cuando el usuario diga que un texto suena a IA, que lo humanice, que lo deje más llano o menos artificial. Si el repo tiene una skill propia de humanizar (por ejemplo humanizar-es en SKLUM), esa va delante: lleva la guía de estilo y las excepciones del proyecto.
argument-hint: [ruta del fichero o texto a revisar]
---

# Humanizar un texto

Texto o documento a revisar: **$ARGUMENTS** (si está vacío, el último documento editado en esta
sesión).

Versión general del 2026-09-18, sacada de la skill `humanizar-es` del repo SKLUM. Los patrones
de forma vienen de `blader/humanizer` v3 (MIT) y del fork `skk-hub/humanizer`, del catálogo de
Wikipedia "Signs of AI writing", de las pruebas del contraste de Humanized Copy, Ruben Hassid y
refine.so, y de lo medido en documentos reales de un proyecto de consultoría (unas 900 líneas de
un deep dive técnico con 24 contrastes, que es la tasa de un modelo; la cifra de
Datociencia para el español es 5 "no es X, es Y" por cada 1.000 frases en texto humano y 27 en
los modelos).

Si el proyecto tiene guía de estilo, va por encima de todo lo que sigue. Si el usuario da una
muestra de cómo escribe, la muestra manda sobre los patrones: se imita su longitud de frase, su
puntuación y sus arranques.

## Qué no se toca

Código, comandos, rutas, nombres de ficheros, cifras, tablas, citas literales y bloques de YAML
o JSON. En un texto en inglés aplican los mismos patrones de forma y el léxico inglés del
detector; nunca se reescribe un texto inglés a partir de la lista española ni al revés.

Nunca inventar un dato que falte. Si una frase afirma algo sin cifra ni fuente, se marca;
rellenarla sería inventar. Nunca añadir un hecho, un nombre, una cifra o una cita que no estén
en el original o los dé el usuario.

Las palabras que en el proyecto son término del dominio y no tell se pasan al detector con
`--ignore` (en un proyecto de pricing, "palanca", "robusto" u "óptimo" son términos, no adorno).

## Patrones, por orden de peso

### 1. El contraste que escenifica (el patrón que más pesa)

Las tres formas, y sus disfraces:

- "No es X, es Y" y "no se trata de X, sino de Y". En inglés "it's not X, it's Y".
- "No solo X, sino (también) Y". En inglés "not just/only X but Y".
- "X, no Y." cerrando la frase. Es la misma figura al revés y suele ser la más frecuente.
- Disfraces: "lo que importa no es X, es Y", "el problema real no es X", "más que X, Y", "menos
  X y más Y", "X llama la atención; Y importa más", "sí, X, pero Y es donde". En inglés "the
  real issue isn't X", "this isn't about X", "more than a X, it's a Y", "less about X and more
  about Y".

Cuatro pruebas, y basta con que falle una para reescribir:

1. Creencia real. ¿Alguien sostiene X de verdad: el lector, el cliente, un documento anterior?
   Un contraste solo se queda cuando corrige un hecho que el lector puede creer ("la reunión es
   el martes, no el jueves"). Si X se inventó para rechazarlo, fuera.
2. Información. ¿Y dice algo que X no decía, o es X con más peso? "No es un problema de medición,
   es un fenómeno real" no aporta: la segunda mitad es la primera con otro tono.
3. Borrado. Quita todo lo anterior a la coma. Si no se pierde nada, X era andamio.
4. Posición. Si el contraste remata un párrafo, una sección o un título, es escenificación casi
   siempre: los modelos lo usan de cierre profundo.

Y un tope de densidad: aunque cada uno pase las pruebas, más de uno por página es tic. Se
reescribe dejando la afirmación sola, y si la primera mitad tenía un dato, se convierte en frase
propia.

Ejemplos con la reescritura validada por el autor:

| Antes | Después |
|---|---|
| "Descartada mientras el régimen sea backorder. No es prudencia, es que corrige algo que no está pasando." | "Descartada mientras el régimen sea backorder: corrige algo que no está pasando." |
| "No es una decisión, es lo que da la cuenta, y cuando haya más semanas..." | "Sale de la cuenta, y cuando haya más semanas la misma cuenta..." |
| "La respuesta no es ralentizar, es cerrar la brecha con un documento corto." | "La respuesta es un documento corto que cierre la brecha." |
| Título: "El problema real no es estimar, es identificar" | "Identificar la pendiente" |
| "Es la capa de gobierno, no la de ejecución." | "Es la capa de gobierno." |
| "Las reglas viven en Power BI por decisión del cliente, no en el motor." | Se queda: corrige una creencia posible (prueba 1). |

### 2. El fragmento corto como frase

Una frase de una a tres palabras después de otra ("Sobreajuste.", "No es ruido.", "Cada día
cuenta.", "Dimensiona la apuesta.", "Sexta vez."; en inglés "That's the real win.", "Read that
again."), cierre el párrafo o vaya en medio. Se integra en la frase anterior o se quita, también
cuando el fragmento es un dato seco.

| Antes | Después |
|---|---|
| "Manu vuelve a escribir a Jordi hoy. Sexta vez." | "Manu vuelve a escribir a Jordi hoy, por sexta vez." |
| "...se queda por detrás de los tramos fuera. Sobreajuste." | "...se queda por detrás de los tramos fuera: sobreajusta." |
| "...t = −2,8 y −3,4. No es ruido." | "...t = −2,8 y −3,4, lejos del ruido." |
| "...fija casi todos los precios. Dimensiona la apuesta." | "...fija casi todos los precios, y eso dimensiona la apuesta." |
| "...con la que empezar a trabajar. Cada día cuenta." | Se quita: el párrafo ya dice que el plazo se acerca. |

### 3. La raya como inciso

La raya (—) está muy identificada con texto de IA. No se cambia por guion (en español, encerrar
un inciso con guiones es una falta según la RAE): se reescribe el inciso con coma (inciso
ligero), dos puntos (lo que sigue explica o concreta), paréntesis (aclaración que se puede
saltar) o punto (dos ideas independientes). El guion solo vale como glifo de celda vacía. Si el
usuario da una muestra con rayas, se respeta su tasa.

### 4. Otras formas de escenificar

- Frases de arranque que no dicen nada ("Es importante entender que", "Conviene señalar que",
  "Hay que tener en cuenta que", "En un mundo donde"; "It's important to note", "Let's dive
  in", "Here's the thing"): se empieza por lo que sigue.
- Preguntas retóricas con respuesta inmediata ("¿Por qué importa? Porque..."; "The catch?"):
  la respuesta sola.
- Cierres que resumen lo que se acaba de leer ("En resumen", "En definitiva", "Como se ve";
  "In summary", "Ultimately", "At the end of the day"): fuera, salvo que el documento sea largo
  y el resumen aporte algo que no estaba.
- Anuncio de estructura ("lo dividimos en tres partes: primero, segundo y por último"): las
  secciones ya enseñan la estructura.
- Conclusión con forma de esquema ("a pesar de X, quedan retos"; "despite these challenges"):
  se dice qué queda y quién lo hace.
- Intensificadores que fingen profundidad: "de verdad" ("donde de verdad se decide"),
  "realmente", "en el fondo", "literalmente"; "actually", "truly", "genuinely". Se quita o se
  sustituye por el dato que justifica el énfasis.
- Frase escindida por sistema ("que es lo que", "es donde", "lo que hace es"; "what really
  matters is", "this is where"). Una vale; tres en una página son ritmo de modelo. Se vuelve a
  sujeto y verbo.
- Sentencias que suenan profundas ("la verdadera pregunta es", "en el fondo", "at its core",
  "the heart of the matter"): se sustituye por la afirmación concreta.
- Discutir con nadie ("no digo que", "que nadie piense que", "I'm not saying", "don't get me
  wrong"): se quita la defensa; si escondía una afirmación, se dice la afirmación.

### 5. Ritmo por regla

- Listas de tres por sistema ("rápido, fiable y barato"). Si son dos cosas, dos; si son cinco,
  cinco. La tríada solo cuando de verdad son tres.
- Párrafos que empiezan igual, o frases de la misma longitud una tras otra. Se varía; la
  escritura real alterna corta y larga.
- Un mismo punto dicho varias veces con otras palabras, o ejemplos apilados como prueba. Se
  queda el mejor ejemplo y se dice por qué vale.
- Una metáfora estirada varios párrafos. Se usa una vez y luego se dice llano.
- Adjetivos y adverbios apilados ("una solución especialmente robusta y realmente escalable").
  Se deja uno o ninguno.
- Calificadores apilados ("podría potencialmente", "en cierto modo puede que"; "could
  potentially", "might arguably"). Se deja el que la fuente sostiene.
- Gerundios de adorno al final ("...mejorando así la precisión y garantizando la coherencia";
  "...highlighting", "...ensuring"). Se corta o se hace frase propia con sujeto.
- Pasiva o impersonal donde hay un sujeto claro ("se decidió que" cuando lo decidió alguien con
  nombre).
- Cosas que hacen lo que hace la gente ("el modelo decide", "la tabla reconoce"). Se nombra
  quién, o se quita la personificación.
- Cópula evitada ("actúa como", "funciona como", "supone", "constituye"; "serves as", "stands
  as") donde vale "es".
- Conector abriendo cada párrafo (Además, Asimismo, Por otro lado, Es decir; Additionally,
  Furthermore, Moreover). Uno suelto vale; en cadena, fuera.
- Equilibrio fabricado ("tiene ventajas e inconvenientes") cuando la fuente da un veredicto. Se
  da el veredicto.
- Pares con guion por todas partes en inglés ("high-quality", "data-driven"): el guion solo
  delante del nombre.

### 6. Inflación y autoridad prestada

- Léxico inflado en español: crucial, fundamental, esencial, clave (como adjetivo), potenciar,
  abordar, garantizar, fomentar, impulsar, ecosistema, paradigma, sinergia, holístico, integral,
  sólido, robusto, vibrante, fluido, sin fisuras, de extremo a extremo, en última instancia, en
  el marco de, de cara a, en aras de, poner en valor, hoja de ruta, desafío y reto por problema.
  En inglés: delve, robust, leverage, crucial, pivotal, landscape, seamless, tapestry,
  testament, vibrant, holistic, comprehensive, streamline, unlock, journey, navigate, foster,
  meticulous, intricate, interplay, actionable, insights, ecosystem, synergy, harness,
  underscore, showcase, enhance, "key" como adjetivo. Cada uno se cambia por la palabra
  corriente o se quita.
- Calcos del inglés en español: "corrida" por ejecución o pasada, "al final del día", "cuando se
  trata de", "asegúrate de", "hacer sentido", "es importante de mencionar", "en términos de",
  "dicho esto", "básicamente", "de forma eficiente" (sin decir en qué).
- Significación inflada: "un cambio fundamental", "un hito", "transformador", "un antes y un
  después"; "game-changer", "a testament to", "paves the way", "cannot be overstated". Se dice
  qué cambió y cuánto.
- Autoridad sin nombre: "los expertos", "la literatura", "es sabido que", "estudios muestran";
  "experts agree", "studies show", "best practices". O se cita la fuente o se quita.
- Lenguaje de venta: "boasts", "nestled", "stunning", "de referencia", "líder". Se dice qué es
  la cosa.
- Absolutos de adorno ("siempre", "nunca", "cada", "todo") donde la fuente dice "en 9 de 11".
  Se acota a lo que la fuente sostiene. Las reglas de un documento de reglas no cuentan.
- Cifras sin origen. Cada número que no venga de un fichero, un comando o un documento citado se
  marca como no verificado.

### 7. Formato por regla

- Negrita decorativa. Antes de quitar ninguna, distinguir la negrita que ancla de la que adorna.
  Se queda la que marca el término que la frase define o contrapone, la cifra que resume el
  párrafo, el símbolo que se presenta, el arranque de viñeta cuando el documento lo usa como
  título corrido de forma consistente, la etiqueta de figura y la cabecera de tabla. Se quita la
  que no señala ni un término ni un dato: un adjetivo o un adverbio, una frase entera, varias
  negritas en la misma frase que compiten entre sí, una palabra que ya va en `code`, o la
  negrita puesta por patrón (una por párrafo, la primera palabra de cada frase). Se decide una
  a una, leyendo la frase, nunca con una sustitución global; la lista de las quitadas va en el
  informe final para que el usuario pueda devolver alguna. Una pasada con script quitó 52
  negritas de un documento técnico y hubo que reponerlas todas.
- Títulos en mayúscula por palabra ("Análisis De La Elasticidad"): en español solo la primera;
  en inglés, la que use el documento.
- Emojis, flechas, reglas horizontales y símbolos en prosa se quitan.
- Listas de viñetas donde había un párrafo que se leía bien. No todo es una lista. Y al revés:
  una lista disfrazada de prosa ("primero... segundo... y por último...") se hace lista.
- Comillas tipográficas curvas mezcladas con rectas: las que ya use el documento.

### 8. Restos de borrador

- Residuos de chat: "Claro, aquí tienes", "Espero que sirva", "Como modelo de lenguaje"; "I
  hope this helps", "Great question", "Let me know".
- Avisos de conocimiento limitado ("hasta mi última actualización", "as of my last update") y
  suposiciones presentadas como hechos ("probablemente creció en"). Se dice qué no muestra la
  fuente, o se quita.
- Advertencias que nadie pidió: "Esto no es asesoramiento", "Consulta con un experto".
- Marcadores sin rellenar: `[TODO]`, `[insertar cifra]`, `XX`, y marcas de cita pegadas de un
  chat (`[cite: 1]`, `oaicite`, `turn0search0`).
- Cabeceras repetidas o secciones vacías que se quedaron de una plantilla, y la primera frase que
  repite el título.
- Referencias al proceso de escritura ("en la versión anterior de este documento").

## Tells débiles y tells fuertes

Un tell fuerte (los del punto 1, 2, 3, 4 y 8) es candidato con una sola aparición. Un tell
débil (intensificador, escindida, verbo blando, hedging, léxico, tríada, conector) puede ser
una elección a propósito, así que solo se toca cuando tiene compañía: otro tell, del tipo que
sea, en el mismo párrafo. El detector aplica esta regla solo: lista los fuertes siempre y los
débiles solo con compañía (`--all` los enseña todos).

## El detector

`tells.py` está al lado de este fichero, sin dependencias. Idioma por fichero (o `--lang`),
HTML con las etiquetas quitadas, `--count` para el recuento sin candidatos, `--ignore` para los
términos del dominio, y acepta directorios:

```
python ~/.claude/skills/humanizar/tells.py <fichero o carpeta> [--lang es|en] [--count] [--all] [--ignore a,b]
```

Lo que devuelve es una lista de candidatos, no de errores: cada uno pasa por las pruebas del
punto 1 o por el criterio de su patrón antes de tocarlo. Lo que el detector no ve (párrafos que
empiezan igual, el punto repetido, la metáfora estirada, la negrita que adorna) se busca leyendo.
Para un texto pegado en el chat, se guarda en un fichero temporal y se corre igual.

## Procedimiento

1. Leer el texto entero. Correr el detector y guardar el recuento: es el "antes".
2. Reescribir los candidatos fuertes, patrón a patrón, sin cambiar el sentido, las cifras ni las
   citas. Cada contraste pasa por las cuatro pruebas; cada fragmento se integra; cada raya se
   reescribe. Cuando una frase se puede leer de dos formas, se conserva la que estaba y se marca.
   La negrita no admite sustitución en bloque: cada una se juzga en su frase.
3. Pasar por los débiles con compañía y por lo que el detector no ve (punto 5 y 7). Al
   reescribir, decir la cosa llana en vez de parchear la frase marcada: si sigue rara, se
   reescribe el párrafo alrededor de su idea principal.
4. Releer una vez más buscando solo lo que más sobrevive: un contraste, un fragmento, una raya,
   un intensificador, una negrita de etiqueta. Lo que no se pueda arreglar sin decidir algo (una
   cifra que falta, un inciso ambiguo) se lista.
5. En español, comprobar tildes y ñ en todo lo tocado. En los dos idiomas, que no ha entrado
   ninguna raya nueva ni ningún contraste nuevo (el modelo los mete al reescribir).
6. Correr el detector otra vez y devolver: el recuento antes y después, la lista de lo que queda
   por decidir, la lista de las negritas quitadas (texto y motivo, una línea cada una) y el diff
   (no una copia entera del texto en el chat).

## Cuándo parar

Cuando la segunda relectura no encuentra nada nuevo. Una tercera pasada suele empezar a cambiar
el sentido por cambiar la forma, y a meter contrastes nuevos donde quitó los viejos.
