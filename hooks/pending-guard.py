"""No dejar cerrar un hilo con pendientes sueltos. Hook `Stop`, global.

El fallo que corrige: el mensaje de cierre dice "hecho, fusionado y desplegado... quedan X e Y
pendientes", el hilo se archiva y X e Y se pierden. La regla de convertirlos en issues vive en
`CLAUDE.md` y en `/cierre`, pero una instrucción puede saltarse; esto no.

Cómo decide, solo mirando el texto del último mensaje (`last_assistant_message`), sin git ni red,
en milisegundos:

1. El mensaje parece un cierre (empieza por "Hecho", dice "fusionado por el gate", "en
   producción", "MERGED" o "ARCHIVABLE").
2. Menciona pendientes ("pendiente", "queda por", "sin verificar", "no he tocado").
3. No lleva ningún enlace o referencia a un issue, y no es el veredicto "NO ARCHIVABLE" de
   `/cierre` (ese ya está tratando el asunto).

Si se dan las tres, devuelve `decision: block` con el motivo: Claude no termina el turno, ve el
motivo y convierte los pendientes en issues (o dice explícitamente que no hay nada que guardar).
Solo bloquea una vez por turno: con `stop_hook_active` a true, calla, que es lo que la
documentación pide para no entrar en bucle.

Es distinto del hook de `Stop` que se descartó en `docs/ways-of-working.md` (sección 7): aquel
corría la verificación del repo en cada turno y tardaba segundos; este no ejecuta nada.

Formato de entrada y salida contrastados contra https://code.claude.com/docs/en/hooks.
Falla abierto y nunca sale con error. `CLAUDE_SKIP_PENDING_GUARD=1` lo apaga para una sesión.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from typing import Any

CLOSING = re.compile(
    r"(?m)^\W{0,3}Hecho\b"
    r"|\bfusionad[oa]s?\s+(?:por el gate|e instalad|y desplegad|y en producci)"
    r"|\ben producci[oó]n\b"
    r"|\bMERGED\b"
    r"|\bARCHIVABLE\b",
    re.IGNORECASE,
)
PENDING = re.compile(
    r"\bpendientes?\b|\bqueda(?:n|r[ií]a)?\s+(?:por|sin)\b|\bsin verificar\b|\bno he (?:tocado|podido)\b",
    re.IGNORECASE,
)
ISSUE_REF = re.compile(
    r"github\.com/[^\s)]+/issues/\d+|\bissues?\s+#\d+|\bissue\b.{0,40}\bcread[oa]s?\b", re.IGNORECASE
)
NOT_ARCHIVABLE = re.compile(r"\bNO ARCHIVABLE\b")
# La frase de escape que pide el motivo del bloqueo: decir explícitamente que no hay nada.
NO_PENDING = re.compile(r"\bsin pendientes\b", re.IGNORECASE)


def should_block(message: str) -> bool:
    if not message or NOT_ARCHIVABLE.search(message) or ISSUE_REF.search(message):
        return False
    if NO_PENDING.search(message):
        return False
    return bool(CLOSING.search(message) and PENDING.search(message))


def main() -> None:
    if os.environ.get("CLAUDE_SKIP_PENDING_GUARD") == "1":
        return
    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    if payload.get("stop_hook_active"):
        return
    message = payload.get("last_assistant_message", "")
    if not isinstance(message, str) or not should_block(message):
        return
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "El mensaje de cierre deja pendientes sin guardar. Antes de terminar: crea un issue "
                    "por cada pendiente en el repo (`gh issue create --title ... --body ...` con el "
                    "contexto: PR, commit, qué falta y por qué se dejó) y repite el cierre con los enlaces "
                    "a los issues. Si de verdad no hay nada que guardar, dilo con esas palabras: "
                    "'sin pendientes que guardar'."
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    # Un fallo aquí jamás debe impedir cerrar un turno: sin salida, la herramienta sigue.
    with contextlib.suppress(Exception):
        main()
