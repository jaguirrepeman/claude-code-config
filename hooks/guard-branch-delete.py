"""Pregunta antes de forzar el borrado de una rama sin fusionar. Hook `PreToolUse` sobre `Bash`, global.

`git branch -D` está en `allow` para que limpiar tras un PR no pida confirmación rama a rama.
Una regla de permisos no distingue una rama fusionada de una sin fusionar, y un hook no puede
saltarse una regla `ask` ("Deny and ask rules are still evaluated regardless of what the hook
returns", hooks.md). Por eso va al revés: la regla deja pasar y este hook devuelve `ask` cuando
no puede demostrar que el trabajo de la rama ya está a salvo en la rama base.

Una rama cuenta como fusionada si se cumple cualquiera de estas, contra `origin/HEAD`,
`origin/main`, `origin/master`, `main` o `master` (las que existan):

1. Su cabeza es antecesora de la base (merge normal o fast-forward).
2. Fusionarla en la base no cambia nada (`git merge-tree`): su contenido ya está dentro, que es
   lo que deja un squash.
3. En GitHub hay un PR fusionado cuya cabeza es exactamente la de la rama (`gh pr list`). Solo
   si `origin` apunta a GitHub y `gh` está instalado.

Solo mira el borrado forzado (`-D`, `--delete --force`, `-d -f`). El `-d` normal ya lo frena el
propio git si la rama no está fusionada.

**Falla cerrado**, al contrario que los otros hooks: si no hay base contra la que comprobar o
algo falla a mitad, pregunta. Aquí el coste de un falso positivo es una confirmación de más; el
de un falso negativo, commits perdidos. Si el hook ni siquiera arranca (sin `python`), Claude
Code sigue sin él y el borrado pasa sin preguntar: es el límite de poner la regla en `allow`.

Formato de entrada y salida contrastados contra https://code.claude.com/docs/en/hooks.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
from typing import Any

from _git_calls import git_calls
from _target_dir import target_dir

TIMEOUT_GIT = 5
TIMEOUT_GH = 10

BASE_CANDIDATES = ("origin/main", "origin/master", "main", "master")


def run(cmd: list[str], cwd: str | None, timeout: int) -> str | None:
    """Salida de un comando, o None si falla o tarda demasiado."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git(*args: str, cwd: str | None) -> str | None:
    return run(["git", *args], cwd, TIMEOUT_GIT)


def force_deleted_branches(command: str) -> list[str]:
    """Ramas locales que el comando borra a la fuerza, en todos sus subcomandos."""
    names: list[str] = []
    for sub, tokens in git_calls(command):
        if sub != "branch":
            continue
        long_flags = {t for t in tokens if t.startswith("--")}
        short = "".join(t[1:] for t in tokens if t.startswith("-") and not t.startswith("--"))
        if "r" in short or "--remotes" in long_flags:
            # Borrar una referencia remota (`origin/x`) no pierde trabajo: se recupera con un fetch.
            continue
        delete = "d" in short or "D" in short or "--delete" in long_flags
        force = "D" in short or "f" in short or "--force" in long_flags
        if delete and force:
            names += [t for t in tokens if not t.startswith("-")]
    return names


def bases(cwd: str | None) -> list[str]:
    """Las ramas base que existen en este repo, empezando por la por defecto del remoto."""
    found: list[str] = []
    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=cwd)
    for ref in ([head] if head else []) + list(BASE_CANDIDATES):
        if ref not in found and git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=cwd):
            found.append(ref)
    return found


def merged_pr_heads(name: str, cwd: str | None) -> set[str]:
    """Cabezas de los PR fusionados desde esta rama en GitHub. Vacío si no se puede consultar."""
    origin = git("remote", "get-url", "origin", cwd=cwd) or ""
    if "github.com" not in origin or not shutil.which("gh"):
        return set()
    query = ["--state", "merged", "--json", "headRefOid", "-q", ".[].headRefOid"]
    out = run(["gh", "pr", "list", "--head", name, *query], cwd, TIMEOUT_GH)
    return set(out.split()) if out else set()


def is_merged(sha: str, name: str, base_refs: list[str], cwd: str | None) -> bool:
    for base in base_refs:
        if run(["git", "merge-base", "--is-ancestor", sha, base], cwd, TIMEOUT_GIT) is not None:
            return True
        merged_tree = git("merge-tree", "--write-tree", base, sha, cwd=cwd)
        if merged_tree and merged_tree.splitlines()[0] == git("rev-parse", f"{base}^{{tree}}", cwd=cwd):
            return True
    return sha in merged_pr_heads(name, cwd)


def ask(reason: str) -> None:
    """Escribe la decisión de preguntar. Es lo único que puede salir por stdout."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(payload, ensure_ascii=False))


def check(command: str, cwd: str | None) -> None:
    names = force_deleted_branches(command)
    if not names:
        return
    cwd = target_dir(command, cwd)
    existing = {
        n: sha
        for n in names
        if (sha := git("rev-parse", "--verify", "--quiet", f"refs/heads/{n}^{{commit}}", cwd=cwd))
    }
    if not existing:
        # Ninguna existe: git dará error solo, no hay trabajo que perder.
        return
    base_refs = bases(cwd)
    if not base_refs:
        ask(
            "No encuentro rama base (origin/HEAD, main o master) para comprobar si "
            f"{', '.join(existing)} está fusionada. Confirma el borrado forzado."
        )
        return
    unmerged = [n for n, sha in existing.items() if not is_merged(sha, n, base_refs, cwd)]
    if unmerged:
        ask(
            f"{', '.join(unmerged)} no está fusionada en {base_refs[0]}: ni es antecesora, ni su "
            "contenido está ya dentro, ni hay un PR fusionado con esa cabeza. Borrarla con -D "
            "pierde esos commits. Si se fusionó hace poco, haz antes git fetch --prune."
        )


def main() -> None:
    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    if payload.get("tool_name") != "Bash":
        return
    command = payload.get("tool_input", {}).get("command", "")
    if not isinstance(command, str) or not force_deleted_branches(command):
        return
    try:
        check(command, payload.get("cwd") or None)
    except Exception:  # noqa: BLE001
        # Falla cerrado: cualquier fallo a mitad de un borrado forzado pregunta, sea cual sea.
        ask("No he podido comprobar si la rama está fusionada. Confirma el borrado forzado.")


if __name__ == "__main__":
    # Lo que falle antes de saber que es un borrado forzado no debe estorbar a ningún otro comando.
    with contextlib.suppress(Exception):
        main()
