"""Las llamadas a git que ejecuta de verdad un comando de shell, y el directorio de cada una.

Los hooks buscaban `git commit`, `git push` o `git branch -D` con una regex sobre el texto entero
del comando, así que saltaban también cuando esas palabras iban dentro de un texto: el cuerpo de
un `gh issue create --body "..."`, un heredoc que escribe unas notas, un `echo` (issue #19).
Aquí el comando se parte en subcomandos como lo haría el shell (comillas, `&&`, `||`, `;`, `|`,
saltos de línea, heredocs) y solo cuenta un subcomando cuyo ejecutable es `git`.

El directorio importa tanto como el subcomando: la sesión puede estar en `main` de un repo y el
commit ir a la rama de trabajo de otro (`cd ../otro && git commit`, `git -C ../otro commit`).
Mirar el `cwd` de la sesión daba falsos bloqueos y, peor, un `git branch -D` que se comprobaba en
el repo equivocado y pasaba sin preguntar (issue #21). Por eso se sigue el directorio subcomando
a subcomando: un `cd` en cualquier posición, `git -C` (solo para su llamada), los subshells
`( ... )` (el `cd` de dentro no sale de ellos) y las variables asignadas en el mismo comando
(`R=...; cd "$R"`). Las rutas al estilo Git Bash en Windows (`/d/x`) se convierten a `D:/x`,
porque el hook corre con el Python de Windows.

Un `cd` a un directorio que no existe no cambia nada, salvo que el propio comando lo cree antes.
Qué se mira entonces depende de cómo lo crea, porque el hook corre antes y no lo puede abrir:
con `mkdir`, el directorio sigue dentro del repo que lo rodea (git sube hasta él), así que se
mira ese repo. Con `git worktree add`, el worktree comparte las ramas del repo de origen. Con
`git init` o `git clone` es un repo nuevo: la llamada se marca así, con la rama que diga el
propio comando (`-b`, un `checkout -b` posterior, o la por defecto del remoto en un clon).
Nunca se inventa un directorio.

Lo que se deja fuera a propósito: un git dentro de `bash -c "..."`, `ssh host '...'` o `$(...)`
no cuenta. En el caso de `ssh` es lo correcto (ese push no sale de esta máquina); en los demás
es un falso negativo aceptado, porque los hooks protegen de un error frecuente, no de alguien
que quiera esquivarlos. Si el comando no se puede tokenizar (comillas sin cerrar), se parte
solo por operadores y espacios, sin seguir subshells.
"""

from __future__ import annotations

import os
import re
import shlex
from typing import NamedTuple

# Cuerpo de un heredoc (`<<EOF`, `<<'EOF'`, `<<-EOF`) hasta su línea de cierre. Se conserva el
# resto de la línea que lo abre, que puede seguir con `&& git ...`.
HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2[^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.DOTALL)
CONTROL = re.compile(r"^[;&|()]+$")
REDIRECT = re.compile(r"^[<>&]+$")
ASSIGNMENT = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.DOTALL)
VARIABLE = re.compile(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))")
MSYS_DRIVE = re.compile(r"^/([a-zA-Z])/")
FALLBACK_SPLIT = re.compile(r"&&|\|\||[;|()]")

OPEN, CLOSE = "(", ")"


# Rama de un clon recién hecho sin `-b`: la por defecto del remoto, protegida por definición.
REMOTE_DEFAULT = "<rama por defecto del remoto>"


class GitCall(NamedTuple):
    sub: str
    args: list[str]
    # Directorio existente desde el que git buscará el repo: el de la llamada, o el antecesor más
    # cercano si el propio comando lo crea con `mkdir`. En un worktree nuevo, el repo de origen.
    cwd: str | None
    # "init", "clone" o "worktree" si la llamada va a un repo que crea el mismo comando, que aún
    # no existe cuando corre el hook; su rama, si el comando la dice, va en `branch`.
    new_repo: str | None = None
    branch: str | None = None


def _tokens(text: str) -> list[str]:
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    # Sin comentarios: con los saltos de línea ya convertidos en `;`, un `#` se comería el resto.
    lex.commenters = ""
    return list(lex)


def _segments(command: str) -> list[list[str] | str]:
    """Subcomandos en orden, con `OPEN`/`CLOSE` donde se abre o se cierra un subshell."""
    text = HEREDOC.sub(r"\1", command).replace("\\\n", " ").replace("\n", " ; ")
    try:
        tokens = _tokens(text)
    except ValueError:
        return [part.split() for part in FALLBACK_SPLIT.split(text)]
    segments: list[list[str] | str] = [[]]
    for token in tokens:
        if CONTROL.match(token):
            segments += [c for c in token if c in "()"]
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def _resolve(path: str, here: str | None, variables: dict[str, str]) -> str | None:
    """Ruta absoluta de `path` vista desde `here`, o None si lleva una variable desconocida."""
    unknown = False

    def value(m: re.Match[str]) -> str:
        nonlocal unknown
        name = m.group(1) or m.group(2)
        if name in variables:
            return variables[name]
        if name in os.environ:
            return os.environ[name]
        unknown = True
        return ""

    path = os.path.expanduser(VARIABLE.sub(value, path))
    if unknown:
        return None
    if os.name == "nt":
        path = MSYS_DRIVE.sub(lambda m: f"{m.group(1).upper()}:/", path)
    if not os.path.isabs(path) and here:
        path = os.path.join(here, path)
    return os.path.normpath(path)


# Opciones que llevan valor, para no confundir ese valor con una ruta o una rama.
VALUED = {
    "init": {"-b", "--initial-branch", "--template", "--separate-git-dir", "--object-format", "--ref-format"},
    "clone": {
        "-b",
        "--branch",
        "-o",
        "--origin",
        "-u",
        "--upload-pack",
        "--reference",
        "--reference-if-able",
        "--depth",
        "--shallow-since",
        "--shallow-exclude",
        "-c",
        "--config",
        "-j",
        "--jobs",
        "--template",
        "--separate-git-dir",
        "--filter",
        "--server-option",
        "--bundle-uri",
        "--revision",
    },
    "worktree": {"-b", "-B", "--reason"},
    "checkout": {"-b", "-B", "--orphan"},
    "switch": {"-c", "-C", "--create", "--force-create", "--orphan"},
}
NEW_BRANCH = {
    "checkout": ("-b", "-B", "--orphan"),
    "switch": ("-c", "-C", "--create", "--force-create", "--orphan"),
}


def _options(sub: str, args: list[str]) -> tuple[list[str], dict[str, str]]:
    """Posicionales y opciones (con su valor, si lo llevan) de una llamada a git."""
    valued = VALUED.get(sub, set())
    positional: list[str] = []
    options: dict[str, str] = {}
    rest = iter(args)
    for arg in rest:
        if arg == "--":
            positional += list(rest)
        elif arg.startswith("-") and arg != "-":
            name, eq, value = arg.partition("=")
            options[name] = value if eq else (next(rest, "") if name in valued else "")
        else:
            positional.append(arg)
    return positional, options


def _first(options: dict[str, str], *names: str) -> str | None:
    return next((options[n] for n in names if n in options), None)


class _NewRepo:
    """Un repo que crea el propio comando y que aún no existe cuando corre el hook."""

    def __init__(self, kind: str, stand_in: str | None, branch: str | None) -> None:
        self.kind = kind
        self.stand_in = stand_in
        self.branch = branch


def _existing(path: str | None) -> str | None:
    """`path`, o su antecesor más cercano que exista: el sitio desde el que git buscará el repo."""
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent
    return path or None


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def git_calls(command: str, cwd: str | None = None) -> list[GitCall]:
    """Cada `git` que ejecuta el comando, en orden, con el directorio en el que correrá."""
    calls: list[GitCall] = []
    here = previous = os.path.normpath(cwd) if cwd else cwd
    stack: list[str | None] = []
    variables: dict[str, str] = {}
    created: set[str] = set()
    new_repos: dict[str, _NewRepo] = {}

    def move(path: str, base: str | None) -> str | None:
        """El directorio al que lleva `path` desde `base`, o `base` si no existe ni se crea."""
        target = _resolve(path, base, variables)
        if target is None:
            return base
        if os.path.isdir(target) or any(_inside(p, target) or _inside(target, p) for p in created):
            return target
        if any(_inside(target, p) for p in new_repos):
            return target
        return base

    def new_repo_at(path: str | None) -> _NewRepo | None:
        roots = [p for p in new_repos if path and _inside(path, p)]
        return new_repos[max(roots, key=len)] if roots else None

    for segment in _segments(command):
        if segment == OPEN:
            stack.append(here)
            continue
        if segment == CLOSE:
            here = stack.pop() if stack else here
            continue
        words = list(segment)
        if words[:1] == ["export"]:
            words = words[1:]
        assignments = []
        while words and (m := ASSIGNMENT.match(words[0])):
            assignments.append(m.groups())
            words = words[1:]
        if not words:
            # Asignación sola (`R=...`): vale para el resto del comando.
            for name, raw in assignments:
                variables[name] = VARIABLE.sub(
                    lambda m: variables.get(m.group(1) or m.group(2), m.group(0)), raw
                )
            continue
        program = os.path.basename(words[0]).lower()
        if program == "cd":
            target = words[1] if len(words) > 1 else "~"
            here, previous = (previous, here) if target == "-" else (move(target, here), here)
            continue
        if program == "mkdir":
            created.update(
                p for a in words[1:] if not a.startswith("-") and (p := _resolve(a, here, variables))
            )
            continue
        if program not in {"git", "git.exe"}:
            continue
        call_dir = here
        i = 1
        # Opciones globales antes del subcomando: `-C ruta`, `-c clave=valor`, `--no-pager`...
        while i < len(words) and words[i].startswith("-"):
            if words[i] == "-C" and i + 1 < len(words):
                call_dir = move(words[i + 1], call_dir)
            i += 2 if words[i] in {"-C", "-c"} else 1
        if i >= len(words):
            continue
        args = words[i + 1 :]
        for j, arg in enumerate(args):
            if REDIRECT.match(arg):
                # `2>/dev/null`: el `2` y lo que sigue son del shell, no de git.
                args = args[: j - 1] if j and args[j - 1].isdigit() else args[:j]
                break
        sub = words[i]
        fresh = new_repo_at(call_dir)
        # Un subdirectorio que crea el comando sigue dentro del repo que lo rodea: git sube hasta
        # él. Un repo que crea el comando (init, clone, worktree) no se puede mirar todavía.
        real_dir = fresh.stand_in if fresh else _existing(call_dir)
        kind, branch = (fresh.kind, fresh.branch) if fresh else (None, None)
        calls.append(GitCall(sub, args, real_dir, kind, branch))
        _track(sub, args, call_dir, real_dir, fresh, new_repos, variables)
    return calls


def _track(
    sub: str,
    args: list[str],
    call_dir: str | None,
    real_dir: str | None,
    fresh: _NewRepo | None,
    new_repos: dict[str, _NewRepo],
    variables: dict[str, str],
) -> None:
    """Apunta los repos que crea esta llamada y los cambios de rama dentro de ellos."""
    positional, options = _options(sub, args)
    if sub == "init":
        target = _resolve(positional[0], call_dir, variables) if positional else call_dir
        # Reinicializar un repo que ya existe no cambia nada: sigue siendo ese repo.
        if target and not os.path.exists(os.path.join(target, ".git")):
            branch = _first(options, "-b", "--initial-branch")
            new_repos[target] = _NewRepo("init", _existing(target), branch)
    elif sub == "clone" and positional:
        if len(positional) > 1:
            name = positional[1]
        else:
            name = positional[0].rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        if target := _resolve(name, call_dir, variables):
            branch = _first(options, "-b", "--branch") or REMOTE_DEFAULT
            new_repos[target] = _NewRepo("clone", _existing(target), branch)
    elif sub == "worktree" and positional[:1] == ["add"] and len(positional) > 1:
        if target := _resolve(positional[1], call_dir, variables):
            # Sin `-b` ni `--detach`, git usa la rama que se le pasa o crea una con el nombre de
            # la carpeta.
            branch = _first(options, "-b", "-B")
            if branch is None and "--detach" not in options:
                branch = positional[2] if len(positional) > 2 else os.path.basename(target)
            # Un worktree comparte las ramas del repo desde el que se crea.
            new_repos[target] = _NewRepo("worktree", real_dir, branch)
    elif fresh and sub in NEW_BRANCH:
        created_branch = _first(options, *NEW_BRANCH[sub])
        if created_branch:
            fresh.branch = created_branch
        elif "--detach" in options or "-d" in options:
            fresh.branch = None
        elif positional:
            fresh.branch = positional[0]
