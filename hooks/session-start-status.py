"""Estado del repo al empezar una sesión. Solo informa, no toca nada. Hook `SessionStart`, global.

Contesta lo que se olvida al abrir una sesión: en qué rama estás, si el árbol está sucio, si
estás en un worktree o en el checkout principal, y cuánto te separa de `origin`. Lo que
imprime entra en el contexto de la sesión (en `SessionStart` la salida estándar se añade al
contexto, a diferencia de otros hooks).

Generalizado desde el hook de un repo de equipo. La rama protegida se detecta sola: la rama por
defecto del remoto (`origin/HEAD`), y si no hay remoto, `main` o `master` si existen.

Tres decisiones de diseño:

1. **No hace `git pull`.** Un pull automático sobre la rama en la que estés es justo lo que no
   quieres a mitad de un cambio: o falla, o te mete una fusión que no elegiste.
2. **No espera al `fetch`.** Tras un proxy corporativo un fetch tarda unos 10 s, inaceptable en
   cada arranque. El informe sale de las referencias locales (menos de 1 s) y el fetch se lanza
   suelto por detrás, para que la sesión siguiente ya lea referencias frescas. Por eso el
   informe dice de cuándo son los datos.
3. **No fuerza nada, solo avisa.** Un hook no puede cambiar el directorio de la sesión ni
   obligarla a abrir un worktree. Lo que hace que eso pase es la regla de `CLAUDE.md`; esto es
   la red de visibilidad.

Nunca sale con error: un problema aquí no puede impedir trabajar.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT_GIT = 5


def git(*args: str) -> str | None:
    """Salida de un comando git, o None si falla o tarda demasiado."""
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=TIMEOUT_GIT, encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def default_branch() -> str | None:
    """La rama protegida: la por defecto del remoto, o `main`/`master` si existen en local."""
    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head.removeprefix("origin/")
    for name in ("main", "master"):
        if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}") is not None:
            return name
    return None


def divergence(a: str, b: str) -> tuple[int, int] | None:
    """Commits que tiene `a` y no `b`, y al revés. None si alguna referencia no existe."""
    out = git("rev-list", "--left-right", "--count", f"{a}...{b}")
    if not out:
        return None
    try:
        left, right = out.split()
        return int(left), int(right)
    except ValueError:
        return None


def refs_age() -> str:
    """Hace cuánto se actualizaron las referencias del remoto, en texto corto."""
    git_dir = git("rev-parse", "--git-common-dir") or ".git"
    marker = Path(git_dir) / "FETCH_HEAD"
    if not marker.exists():
        return "sin fetch previo"
    hours = (time.time() - marker.stat().st_mtime) / 3600
    if hours < 1:
        return "al día"
    if hours < 48:
        return f"de hace {int(hours)} h"
    return f"de hace {int(hours / 24)} días"


def background_fetch() -> None:
    """Lanza el fetch y no lo espera: refresca las referencias para la sesión siguiente."""
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    with contextlib.suppress(OSError, ValueError):
        subprocess.Popen(  # noqa: S603
            ["git", "fetch", "--quiet", "origin"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )


def in_worktree() -> bool:
    """El checkout principal tiene `.git` como directorio; un worktree lo tiene como fichero."""
    return Path(".git").is_file()


def main() -> None:
    if git("rev-parse", "--git-dir") is None:
        return

    lines: list[str] = []
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    protected = default_branch()

    dirty = git("status", "--porcelain")
    n_dirty = len(dirty.splitlines()) if dirty else 0
    suffix = f", {n_dirty} ficheros sin commitear" if n_dirty else ", limpio"
    where = "worktree" if in_worktree() else "checkout principal"
    lines.append(f"Rama: {branch}{suffix} ({where})")

    if protected and branch == protected:
        lines.append(
            f"AVISO: estás en {protected}. El trabajo va en una rama corta propia, en su worktree; "
            "el commit en la rama protegida está bloqueado por hook."
        )

    d = divergence(f"origin/{branch}", branch)
    if d is not None:
        behind, ahead = d
        if behind or ahead:
            lines.append(f"Frente a origin/{branch}: {ahead} commits por delante, {behind} por detrás.")

    if git("remote", "get-url", "origin") is not None:
        background_fetch()

    if lines:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(f"Estado del repo (referencias del remoto {refs_age()}):")
        for line in lines:
            print(f"  {line}")


if __name__ == "__main__":
    # Un fallo aquí jamás debe romper el arranque de la sesión.
    with contextlib.suppress(Exception):
        main()
