"""Directorio real en el que va a correr un comando git.

Los hooks reciben el `cwd` de la sesión, pero el comando puede ir a otro repo: `cd ../otro &&
git commit` o `git -C ../otro push`. Mirar la rama o el `verify-command` del `cwd` de la sesión
en esos casos produce falsos positivos (un commit en una rama de trabajo de otro repo bloqueado
porque la sesión está en `main`) y falsos negativos (verificar el repo equivocado antes del
push). Aquí se resuelve una sola vez para los dos hooks.

Se contempla solo lo que aparece en la práctica: un `cd` al principio del comando (con `&&` o
`;` detrás) y `git -C ruta`. Las rutas al estilo Git Bash en Windows (`/d/x`) se convierten a
`D:/x`, porque el hook corre con el Python de Windows. Si la ruta no existe, se devuelve el
`cwd` original: nunca se inventa un directorio.
"""

from __future__ import annotations

import os
import re

_QUOTED = r"""(?:"([^"]+)"|'([^']+)'|(\S+))"""
CD_PREFIX = re.compile(r"^\s*cd\s+" + _QUOTED + r"\s*(?:&&|;)")
GIT_C = re.compile(r"\bgit\s+-C\s*" + _QUOTED)
MSYS_DRIVE = re.compile(r"^/([a-zA-Z])/")


def _normalize(path: str, cwd: str | None) -> str:
    path = os.path.expandvars(os.path.expanduser(path))
    if os.name == "nt":
        path = MSYS_DRIVE.sub(lambda m: f"{m.group(1).upper()}:/", path)
    if not os.path.isabs(path) and cwd:
        path = os.path.join(cwd, path)
    return os.path.normpath(path)


def target_dir(command: str, cwd: str | None) -> str | None:
    """El directorio del `cd` inicial o del `git -C`; si no hay o no existe, `cwd`."""
    m = CD_PREFIX.match(command) or GIT_C.search(command)
    if not m:
        return cwd
    candidate = _normalize(next(g for g in m.groups() if g), cwd)
    return candidate if os.path.isdir(candidate) else cwd
