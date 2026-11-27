# Autonomía de `/mejora` (noviembre de 2026)

## Por qué

Del 31 de octubre al 21 de noviembre, `/mejora arreglar` corrió 6 veces y solo abrió un PR
(examtopics #10). Las otras cinco no encontraron nada que coger: los 9 issues `audit` abiertos
estaban todos en `audit-decision`, incluidos bugs claros como atril#167 (C6/9 no se reconoce) o
atril#171 (Cm7b5 con sostenidos), que solo eran `decision` por estar en una zona caliente. Y lo
que sí arreglaba se quedaba en draft esperando a la persona.

La persona lo dijo el 2026-11-27: lo más autónomo posible, salvo decisiones gordas de verdad.

## Lo decidido (2026-11-27)

- Tres niveles en vez de dos:
  - `audit-autonomo`: lo arregla el robot y el PR sale **listo**, así que lo fusiona y despliega
    el gate en verde. Sin revisión de la persona.
  - `audit-revision` (nuevo): lo arregla el robot, PR en draft. Zona caliente, o una elección
    de producto pequeña y reversible en la que el robot aplica su opción recomendada.
  - `audit-decision`: solo lo gordo (datos, infraestructura viva, gate o despliegue,
    credenciales, dinero o cuota, dependencias mayores, lo irreversible). El robot no lo toca.
- Ante la duda, el nivel menos restrictivo que no sea irreversible.
- `arreglar` pasa de dos veces los sábados a dos veces al día; `auditar`, a miércoles y sábado.
- Un resumen semanal (domingo) en español, con aviso al móvil: qué se fusionó solo, qué espera
  en draft y qué decisiones gordas quedan.
- El freno de dos PR abiertos del robot por repo se queda: con PR listos que se fusionan solos,
  el que frena son los drafts sin mirar.

## Criterio de aceptación

- `pick.py arreglar` coge issues `audit-autonomo` y `audit-revision` y dice `PR: listo` o
  `PR: draft` (tests en `hooks/tests/test_skill_scripts.py`).
- Tras reetiquetar, `pick.py arreglar` contra los repos reales devuelve un issue, no "NADA QUE
  ARREGLAR".

## Lo que no se hace aquí

- Moverlo a la nube o a la Raspberry (#38): sigue en este PC, y solo corre con la app abierta.
  Es una decisión con credenciales de por medio y queda en su issue.
- El candado contra dos auditorías a la vez (#37): con auditar en días distintos y una sola
  ejecución por hueco, sigue siendo poco probable.
- Comprobaciones automáticas tras cada despliegue con vuelta atrás: van repo a repo, aparte.
