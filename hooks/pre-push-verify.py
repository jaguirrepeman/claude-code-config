"""Exige la verificación del repo antes de dejar salir código. Hook `PreToolUse` sobre `Bash`, global.

Es el gate local que faltaba: `CLAUDE.md` pide "ruff y pytest antes de cada push", y una
instrucción se olvida. Este hook corre el comando de verificación del repo cuando el comando que
va a ejecutarse es un `git push`, y solo deja pasar el push si la verificación termina en 0.

Cada repo declara su comando en `.claude/verify-command`: una línea (las que empiezan por `#`
son comentarios), por ejemplo `cd backend && poetry run ruff check . && poetry run pytest -q`.
Sin ese fichero el hook no hace nada, así que activarlo en un repo es añadir el fichero. La
variable `CLAUDE_VERIFY_CMD` manda sobre el fichero, y `CLAUDE_SKIP_VERIFY=1` desactiva el hook
para una sesión (para un push de emergencia consciente, no como costumbre).

Tres decisiones de diseño, las mismas que en los otros hooks de este repo:

1. **Falla abierto.** Sin fichero, sin git, o si la verificación no termina en el tiempo
   (`CLAUDE_VERIFY_TIMEOUT`, 540 s por defecto), el push pasa. Solo se bloquea con la prueba de
   que algo falla: un exit distinto de 0.
2. **Devuelve la salida del fallo, no un "falló".** El modelo necesita el traceback o el aviso
   de ruff para arreglarlo sin volver a ejecutar; se le da la cola de la salida.
3. **Nunca sale con error.** Un problema en el hook no puede dejar la sesión atrapada.

Corre en el push y no en cada turno a propósito: un `Stop` hook que verifica en cada respuesta
tarda segundos y se acaba apagando (ver `docs/ways-of-working.md`, sección 7). El push es cuando
el código le llega a otra persona o al CI, y pasa pocas veces al día.

Formato de entrada y salida contrastados contra https://code.claude.com/docs/en/hooks.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TIMEOUT_GIT = 5
DEFAULT_TIMEOUT = 540
MAX_OUTPUT = 4000
VERIFY_FILE = Path(".claude") / "verify-command"

# `git push` con cualquier flag, también dentro de un comando compuesto y con opciones globales
# antes del subcomando (`git -C ruta push`).
GIT_PUSH = re.compile(r"\bgit\b(?:\s+-[cC]\s*\S+|\s+--\S+)*\s+push\b")


def git(*args: str, cwd: str | None) -> str | None:
    """Salida de un comando git, o None si falla o tarda demasiado."""
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=TIMEOUT_GIT, encoding="utf-8", cwd=cwd
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def verify_command(root: Path) -> str | None:
    """El comando de verificación: la variable de entorno, o la primera línea útil del fichero."""
    configured = os.environ.get("CLAUDE_VERIFY_CMD", "").strip()
    if configured:
        return configured
    path = root / VERIFY_FILE
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


def timeout_seconds() -> int:
    try:
        return max(1, int(os.environ.get("CLAUDE_VERIFY_TIMEOUT", DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT


def tail(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else "[...]\n" + text[-MAX_OUTPUT:]


def deny(reason: str) -> None:
    """Escribe la decisión de denegar. Es lo único que puede salir por stdout."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(payload, ensure_ascii=False))


def main() -> None:
    if os.environ.get("CLAUDE_SKIP_VERIFY", "").strip() in {"1", "true", "yes"}:
        return

    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    if payload.get("tool_name") != "Bash":
        return
    command = payload.get("tool_input", {}).get("command", "")
    if not isinstance(command, str) or not GIT_PUSH.search(command):
        return

    cwd = payload.get("cwd") or None
    top = git("rev-parse", "--show-toplevel", cwd=cwd)
    if top is None:
        return
    root = Path(top)
    cmd = verify_command(root)
    if cmd is None:
        return

    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds(),
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        # Sin veredicto no hay prueba de fallo: se deja pasar, y el CI sigue siendo el gate.
        return
    except OSError:
        return

    if r.returncode == 0:
        return

    output = tail(((r.stdout or "") + (r.stderr or "")).strip())
    deny(
        f"Push bloqueado: la verificación del repo ({cmd}) terminó con exit {r.returncode}. "
        "Arregla lo que falla y repite el push; no desactives el hook ni saltes tests.\n\n"
        f"{output}"
    )


if __name__ == "__main__":
    # Un fallo aquí jamás debe bloquear un push legítimo: sin salida, la herramienta sigue.
    with contextlib.suppress(Exception):
        main()
