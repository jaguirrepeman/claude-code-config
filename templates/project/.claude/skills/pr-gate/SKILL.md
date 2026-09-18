---
name: pr-gate
description: Revisión propia de este repo antes del auto-merge. La ejecuta el job `review` del CI con la GitHub Action de Claude sobre el PR abierto, y su veredicto decide si el PR se fusiona. No arregla nada. No invocar a mano.
argument-hint: [número de PR]
allowed-tools: Bash, Read, Grep, Glob, Write
disable-model-invocation: true
---

# /pr-gate: veredicto sobre el PR $ARGUMENTS

Eres el último filtro antes de que este PR se fusione y, en los repos que despliegan solos, llegue
a producción. Nadie lo va a leer después de ti. Intenta refutar el cambio; no lo apruebes por
defecto. Pero solo bloqueas con prueba: un comando que falla, un número que cambia sin test que
lo justifique, un fichero de zona caliente tocado sin test. Una duda sin prueba no bloquea: se
deja escrita en el veredicto.

Los tests y el lint del repo ya han corrido en el job `tests` de este mismo CI; no los repitas
enteros. Tu valor está en lo que un test genérico no ve: la zona caliente, el comportamiento en
marcha y el diff leído con criterio.

## Diff del PR frente a la base (automático)

```!
BASE="origin/${PR_BASE:-main}"
git fetch -q origin "${PR_BASE:-main}" 2>/dev/null || true
echo "base: $BASE  head: $(git rev-parse --short HEAD)"
git diff --stat "$BASE...HEAD" | tail -40
echo "--- ficheros:"
git diff --name-only "$BASE...HEAD"
```

```!
BASE="origin/${PR_BASE:-main}"
git diff "$BASE...HEAD" | head -c 80000
```

Si el diff aparece recortado, vuelve a pedirlo por ficheros con `git diff origin/<base>...HEAD -- <ruta>`.

## Qué comprobar en este repo

<!-- ADAPTAR: esta sección es la única que cambia entre repos. Cada punto debe ser una
comprobación con comando y resultado esperado, no una intención. Ejemplos: -->

1. **Zonas calientes** (las de `.claude/rules/zonas-calientes.md`): si el diff toca alguna,
   tiene que haber un test nuevo o modificado que la cubra en el mismo PR, y tienes que
   ejecutarlo y verlo pasar: `uv run pytest -q <fichero de test>` desde el directorio del
   `pyproject.toml` (el CI ya ha hecho `uv sync --locked --dev` ahí). Sin test, bloquea.
2. **La aplicación arranca**: `<comando de arranque>` en segundo plano y `curl -fsS
   <endpoint de salud>` devuelve 200 en menos de 30 s. Si no arranca, bloquea con la salida.
3. **Contratos**: si cambia una firma pública, un esquema de API o un formato de fichero,
   comprueba que todos los usos del repo se han actualizado (`grep`), no solo el que toca el PR.

## Veredicto (obligatorio)

Escribe con la herramienta Write el fichero `/tmp/pr-gate-verdict.json` con exactamente esta
forma, y nada más en ese fichero:

```json
{
  "verdict": "pass",
  "summary": "Una o dos frases para el comentario del PR.",
  "findings": [
    {"file": "ruta", "severity": "block", "what": "qué está mal", "proof": "comando y salida"}
  ]
}
```

- `verdict` es `block` solo si hay al menos un finding con `severity: block` y su `proof` es un
  comando ejecutado con su salida real. Cualquier otra cosa es `pass`, con las dudas como
  findings de `severity: note`.
- Si no puedes terminar (falta una dependencia, se agota el tiempo), escribe `pass` con un
  finding `note` que diga qué no pudiste comprobar. El job falla solo con `block`.
