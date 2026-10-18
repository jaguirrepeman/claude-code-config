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

Un `cd` a un directorio que no existe no cambia nada, salvo que el propio comando lo cree antes
(`mkdir`, `git init`, `git clone`, `git worktree add`): entonces la llamada se marca con ese
directorio aunque aún no exista, y los hooks, que no pueden mirar su rama, la dejan pasar.
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


class GitCall(NamedTuple):
    sub: str
    args: list[str]
    cwd: str | None


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


def _created_by_git(sub: str, args: list[str]) -> list[str]:
    """Directorios que crea una llamada a git: `init <dir>`, `clone <url> [dir]`, `worktree add <dir>`."""
    positional = [a for a in args if not a.startswith("-")]
    if sub == "init":
        return positional[:1]
    if sub == "clone" and positional:
        default = positional[0].rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        return [positional[1] if len(positional) > 1 else default]
    if sub == "worktree" and positional[:1] == ["add"] and len(positional) > 1:
        return [positional[1]]
    return []


def git_calls(command: str, cwd: str | None = None) -> list[GitCall]:
    """Cada `git` que ejecuta el comando, en orden, con el directorio en el que correrá."""
    calls: list[GitCall] = []
    here = cwd
    stack: list[str | None] = []
    variables: dict[str, str] = {}
    created: set[str] = set()

    def move(path: str, base: str | None) -> str | None:
        """El directorio al que lleva `path` desde `base`, o `base` si no existe ni se crea."""
        target = _resolve(path, base, variables)
        if target and (os.path.isdir(target) or target in created):
            return target
        return base

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
            if target != "-":
                here = move(target, here)
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
        created.update(p for d in _created_by_git(sub, args) if (p := _resolve(d, call_dir, variables)))
        calls.append(GitCall(sub, args, call_dir))
    return calls
