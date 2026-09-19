---
name: deploy-pi
description: Despliega la rama actual al Raspberry Pi de este proyecto y verifica en vivo con evidencia real. Úsalo cuando el usuario pida "despliega a la Pi", "sube esto a producción" o "verifica que está en producción" en un repo que se auto-hospeda en el Pi.
user-invocable: true
disable-model-invocation: true
---

# /deploy-pi: deploy al Raspberry Pi y verificación en vivo

Arguments passed: `$ARGUMENTS` (opcional: rama a desplegar; si está vacío, la
rama actual).

**No hay un pipeline único**: cada repo tiene su propio script de deploy y
endpoint de salud. Antes de nada, mira `CLAUDE.md`, `WORKFLOW.md`,
`deploy/README.md` o `deploy/*.sh` del repo para encontrar el script y el
endpoint reales; no los inventes ni asumas los de otro proyecto.

## Estado actual (automático)

```!
git branch --show-current 2>/dev/null || echo "(no es un repo git)"
git status --short 2>/dev/null | head -10
git log --oneline -3 2>/dev/null
```

Si hay cambios sin commitear o la rama difiere de lo esperado, dilo antes de
seguir; no despliegues sobre un estado que no coincide con lo anterior.

## Pasos

1. **Confirma que la rama está lista:** `git fetch origin`, comprueba que el
   SHA local coincide con `origin/<rama>` (o que el PR ya se fusionó). No
   despliegues código sin pushear.
2. **Lint/tests locales primero**, si el repo los tiene y esta máquina puede
   correrlos (revisa si hay Node/Poetry disponibles antes de asumirlo; en
   esta máquina normalmente no hay Node local).
3. **Ejecuta el script de deploy del repo** (`deploy/update.sh`,
   `deploy/deploy_api.sh` o el que corresponda) sobre la Pi, vía SSH:
   `ssh pi@<host> 'bash -lc "cd <ruta_repo> && ./deploy/update.sh"'`
   Nunca sintaxis PowerShell dentro de ese comando remoto.
4. **Si el script no tiene rollback automático**, guarda el SHA anterior
   antes de desplegar para poder revertir a mano si algo falla.

## Verificación (obligatoria, no opcional)

No digas "desplegado" ni "funciona" sin esto:

- El SHA que corre en el Pi coincide con el SHA de `origin/<rama>` que
  querías desplegar (compáralo explícitamente, no lo asumas).
- Un `curl`/petición real al endpoint de salud o a una página real de la app,
  con la respuesta pegada tal cual, no solo el código HTTP, sino un valor de
  negocio real (p. ej. una cifra de cartera, un rating, un anuncio concreto).
- Si el cambio toca varios dispositivos/clientes (iPad, móvil, Kindle
  Scribe...), verifica que los otros no se rompieron, no solo el que motivó
  el cambio. En Kindle y Kobo, cache bust del service worker antes de mirar.
- Si el cambio es de interfaz, además del curl: abre la página en el
  navegador integrado, captura de pantalla de la vista que cambió, y compara
  lo que se ve con lo que el cambio prometía. La captura es la evidencia.
- Si algo de esto no se puede verificar de verdad, dilo explícitamente
  ("sin verificar: ...") en vez de reportar éxito.

Termina el mensaje con un bloque VERIFICACIÓN: comandos ejecutados, su output
real, SHA local vs SHA en Pi, y qué queda sin verificar si algo queda.
