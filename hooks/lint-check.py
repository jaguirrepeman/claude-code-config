"""Lint informativo del fichero recién editado. Hook `PostToolUse` sobre `Edit|Write`, global.

Sustituye al `lint-check.ps1` anterior: Group Policy bloquea los `.ps1` en la máquina
corporativa, y Python está en todas.

Qué hace: lee por stdin el fichero que acaba de tocar la herramienta y, solo sobre ese fichero,
corre `ruff check` y `ruff format --check` si es Python, o `eslint` si es JS/TS y el repo tiene
uno instalado en `node_modules`. Acotado a un fichero es sub-segundo, que es lo que puede
permitirse un hook que corre en cada edición. `ruff check .` entero no.

Qué devuelve: si hay avisos, los mete en el contexto del modelo como `additionalContext`, que
es lo que hace que Claude los vea y los arregle. Un `print` suelto con exit 0 solo sale en el
transcript, no llega al modelo, que era el fallo del script anterior. Si está limpio, calla.

Tres decisiones de diseño:

1. **Nunca bloquea.** Es informativo. Un hook que bloquea ediciones por lint acaba apagado.
2. **Falla abierto.** Si no encuentra ruff, ni eslint, ni el fichero, ni el repo, no dice nada.
3. **Usa el linter del repo, no uno global.** Primero `.venv/Scripts/ruff.exe` (o `bin/ruff`),
   luego el `ruff` del PATH. Nunca `uvx`, que descargaría algo en mitad de una edición.

Formato de entrada y salida contrastados contra https://code.claude.com/docs/en/hooks.
Nunca sale con error: un problema aquí no puede impedir trabajar.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TIMEOUT = 20
MAX_OUTPUT = 3000
PY_SUFFIXES = {".py", ".pyi"}
JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def find_root(start: Path, markers: tuple[str, ...]) -> Path | None:
    """Sube desde el fichero hasta encontrar un directorio con alguno de los marcadores."""
    for candidate in (start, *start.parents):
        if any((candidate / m).exists() for m in markers):
            return candidate
    return None


def ruff_binary(root: Path) -> str | None:
    """El ruff del repo si lo hay; si no, el del PATH; si no, ninguno."""
    for rel in ("Scripts/ruff.exe", "bin/ruff"):
        if (p := root / ".venv" / rel).exists():
            return str(p)
    return shutil.which("ruff")


def eslint_binary(root: Path) -> str | None:
    """El eslint instalado en el repo. Nunca uno global, que no tendría la config del repo."""
    for rel in ("node_modules/.bin/eslint.cmd", "node_modules/.bin/eslint"):
        if (p := root / rel).exists():
            return str(p)
    return None


def run(cmd: list[str], cwd: Path) -> str:
    """Salida combinada del comando, o vacío si pasó limpio o no se pudo ejecutar."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if r.returncode == 0:
        return ""
    return ((r.stdout or "") + (r.stderr or "")).strip()


def tail(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else "[...]\n" + text[-MAX_OUTPUT:]


def lint(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PY_SUFFIXES:
        root = find_root(path.parent, ("pyproject.toml", "ruff.toml", ".ruff.toml"))
        if root is None or (ruff := ruff_binary(root)) is None:
            return ""
        parts = [
            run([ruff, "check", "--output-format", "concise", str(path)], root),
            run([ruff, "format", "--check", str(path)], root),
        ]
        return "\n".join(p for p in parts if p)
    if suffix in JS_SUFFIXES:
        root = find_root(path.parent, ("package.json",))
        if root is None or (eslint := eslint_binary(root)) is None:
            return ""
        return run([eslint, "--format", "compact", str(path)], root)
    return ""


def main() -> None:
    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    file_path = payload.get("tool_input", {}).get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return
    path = Path(file_path)
    if not path.is_file():
        return

    output = lint(path)
    if not output:
        return

    context = f"Lint del fichero que acabas de editar ({path.name}), informativo:\n\n{tail(output)}"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    # Un fallo aquí jamás debe molestar: sin salida, la edición sigue.
    with contextlib.suppress(Exception):
        main()
