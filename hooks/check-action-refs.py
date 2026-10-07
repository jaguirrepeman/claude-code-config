"""Comprueba que existen las versiones de GitHub Actions del workflow recién editado. Hook
`PostToolUse` sobre `Edit|Write`, global.

Por qué existe: dos migraciones a uv fallaron en CI por `astral-sh/setup-uv@v10`, una etiqueta
que no existía. La regla escrita ("fijar la versión") no lo evitó, porque el modelo escribe la
versión que cree recordar. Esto lo comprueba contra GitHub en el momento de editar.

Qué hace: si el fichero es un workflow (`.github/workflows/*.yml`) o una action compuesta
(`action.yml`), saca cada `uses: dueño/repo[/ruta]@ref` y pregunta a la API de GitHub con
`gh api repos/<dueño>/<repo>/commits/<ref>`, que resuelve etiquetas, ramas y SHA en una sola
llamada. Las actions locales (`./`) y las imágenes `docker://` no se comprueban. Las consultas
van en paralelo; cada una tarda dos o tres segundos.

Por qué `gh` y no `git ls-remote`: en Windows, `ls-remote` contra un repo inexistente tardaba
diez segundos (el gestor de credenciales intentaba autenticarse), y al cortarlo por timeout
seguía vivo el proceso hijo que hace la conexión, así que el hook llegó a tardar 35 segundos.
`gh` es un solo proceso, contesta con un mensaje distinto para "no existe el repo" y "no existe
la ref", y va con la sesión del usuario, así que también ve sus repos privados.

Qué devuelve: si alguna referencia no existe, lo dice como `additionalContext` (igual que
`lint-check.py`), para que Claude la corrija antes de que lo descubra el CI. Si todo existe,
calla.

Falla abierto: sin `gh`, sin sesión, sin red o con cualquier respuesta que no sea un "no existe"
claro, no dice nada. `ACTION_REFS_GH` (lista JSON) sustituye al comando `gh`; lo usan los tests
para no salir a la red.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

TIMEOUT = 10
USES = re.compile(r"""^\s*(?:-\s*)?uses:\s*["']?([^\s"'#]+)""", re.MULTILINE)
# Lo que contesta la API cuando la ref no existe y cuando el repo no existe (o no se ve).
REF_MISSING = re.compile(r"No commit found")
REPO_MISSING = re.compile(r"Not Found|HTTP 404")


def is_workflow(path: Path) -> bool:
    if path.suffix.lower() not in {".yml", ".yaml"}:
        return False
    parts = [p.lower() for p in path.parts]
    in_workflows = len(parts) >= 3 and parts[-3:-1] == [".github", "workflows"]
    return in_workflows or path.stem.lower() == "action"


def refs(text: str) -> set[tuple[str, str]]:
    """Pares (dueño/repo, ref) de cada `uses:` remoto."""
    found = set()
    for spec in USES.findall(text):
        if spec.startswith(("./", "docker://")) or "@" not in spec:
            continue
        target, ref = spec.rsplit("@", 1)
        segments = target.split("/")
        if len(segments) < 2 or not ref:
            continue
        found.add(("/".join(segments[:2]), ref))
    return found


def gh_command() -> list[str]:
    override = os.environ.get("ACTION_REFS_GH")
    return json.loads(override) if override else ["gh"]


def missing(repo: str, ref: str) -> str | None:
    """Motivo si `ref` no existe en `repo`; None si existe o no se pudo saber."""
    cmd = [*gh_command(), "api", f"repos/{repo}/commits/{quote(ref, safe='')}", "--jq", ".sha"]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 0:
        return None
    answer = (r.stdout or "") + (r.stderr or "")
    if REF_MISSING.search(answer):
        return "no existe esa etiqueta, rama ni commit"
    if REPO_MISSING.search(answer):
        return "no existe el repositorio (o no tienes acceso)"
    return None


def main() -> None:
    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    file_path = payload.get("tool_input", {}).get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return
    path = Path(file_path)
    if not is_workflow(path) or not path.is_file():
        return

    pairs = sorted(refs(path.read_text(encoding="utf-8", errors="replace")))
    if not pairs:
        return
    with ThreadPoolExecutor(max_workers=8) as pool:
        reasons = list(pool.map(lambda p: missing(*p), pairs))
    bad = [f"- `{repo}@{ref}`: {why}" for (repo, ref), why in zip(pairs, reasons, strict=True) if why]
    if not bad:
        return

    context = (
        f"Versiones de GitHub Actions que no existen en {path.name}:\n\n"
        + "\n".join(bad)
        + "\n\nUsa una etiqueta que exista (mírala con `gh api repos/<dueño>/<repo>/tags --jq '.[].name'`)."
    )
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
