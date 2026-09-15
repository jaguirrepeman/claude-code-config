"""Impide commitear mientras la rama activa sea la protegida. Hook `PreToolUse` sobre `Bash`, global.

Es la red que no depende de que nadie se acuerde: la instrucción de abrir rama antes de tocar
código vive en `CLAUDE.md`, y una instrucción puede olvidarse, así que aquí se bloquea el commit
directamente. Regla: en la rama protegida no commitea nadie, el trabajo va en rama corta.

Generalizado desde el hook de un repo de equipo. La rama protegida se detecta sola: la por
defecto del remoto (`origin/HEAD`), y si no hay remoto, `main` o `master` si existen. Se puede
fijar a mano con la variable de entorno `CLAUDE_PROTECTED_BRANCHES` (nombres separados por
comas), que manda sobre la detección.

Dos decisiones de diseño:

1. **Falla abierto.** Si git no contesta, tarda demasiado o el directorio no es un repo, el
   commit pasa. Lo que se protege es un error humano frecuente, no un ataque, y el coste de un
   falso bloqueo (alguien que no puede trabajar y no entiende por qué) es mayor que el de un
   falso positivo.
2. **Mira la rama, no el comando.** El comando solo sirve para saber si esto es un commit; quién
   decide es `git rev-parse --abbrev-ref HEAD` sobre el directorio en el que se iba a ejecutar.

Un límite que hay que tener claro: bloquea que una sesión de Claude Code commitee en la rama
protegida; no impide que una persona lo haga a mano desde su terminal. Para eso está la
protección de rama del servidor.

Formato de entrada y salida contrastados contra https://code.claude.com/docs/en/hooks.
Nunca sale con error: un problema aquí no puede impedir trabajar.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from typing import Any

TIMEOUT_GIT = 5

# `git commit` con cualquier flag, y también dentro de un comando compuesto
# (`git add x && git commit -m ...`). Se admiten las opciones globales que van antes del
# subcomando, del estilo `git -c user.name=X commit` o `git -C ruta commit`.
GIT_COMMIT = re.compile(r"\bgit\b(?:\s+-[cC]\s*\S+|\s+--\S+)*\s+commit\b")


def git(*args: str, cwd: str | None) -> str | None:
    """Salida de un comando git, o None si falla o tarda demasiado."""
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=TIMEOUT_GIT, encoding="utf-8", cwd=cwd
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def protected_branches(cwd: str | None) -> set[str]:
    """Las ramas en las que no se commitea: la variable de entorno, o la detección automática."""
    configured = os.environ.get("CLAUDE_PROTECTED_BRANCHES", "")
    if configured.strip():
        return {b.strip() for b in configured.split(",") if b.strip()}
    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=cwd)
    if head:
        return {head.removeprefix("origin/")}
    return {
        name
        for name in ("main", "master")
        if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=cwd) is not None
    }


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
    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    if payload.get("tool_name") != "Bash":
        return

    command = payload.get("tool_input", {}).get("command", "")
    if not isinstance(command, str) or not GIT_COMMIT.search(command):
        return

    # El repo que importa es el del directorio en el que se iba a ejecutar el comando.
    cwd = payload.get("cwd") or None
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if branch is None:
        # No se pudo determinar la rama: se deja pasar, nunca se bloquea por un fallo de detección.
        return

    if branch in protected_branches(cwd):
        deny(
            f"Commit bloqueado: la rama activa es {branch}, y en {branch} no commitea nadie. "
            "Abre una rama corta con el prefijo que toque (claude/tema, feature/tema, fix/tema o "
            "docs/tema), repite el commit ahí e integra con squash cuando la verificación esté "
            "en verde."
        )


if __name__ == "__main__":
    # Un fallo aquí jamás debe bloquear una acción legítima: sin salida, la herramienta sigue.
    with contextlib.suppress(Exception):
        main()
