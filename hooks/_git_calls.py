"""Las llamadas a git que ejecuta de verdad un comando de shell.

Los hooks buscaban `git commit`, `git push` o `git branch -D` con una regex sobre el texto entero
del comando, así que saltaban también cuando esas palabras iban dentro de un texto: el cuerpo de
un `gh issue create --body "..."`, un heredoc que escribe unas notas, un `echo` (issue #19).
Aquí el comando se parte en subcomandos como lo haría el shell (comillas, `&&`, `||`, `;`, `|`,
saltos de línea, heredocs) y solo cuenta un subcomando cuyo ejecutable es `git`.

Lo que se deja fuera a propósito: un git dentro de `bash -c "..."`, `ssh host '...'` o `$(...)`
no cuenta. En el caso de `ssh` es lo correcto (ese push no sale de esta máquina); en los demás
es un falso negativo aceptado, porque los hooks protegen de un error frecuente, no de alguien
que quiera esquivarlos. Si el comando no se puede tokenizar (comillas sin cerrar), se parte
solo por operadores y espacios, que es lo que hacía la regex de antes.
"""

from __future__ import annotations

import os
import re
import shlex

# Cuerpo de un heredoc (`<<EOF`, `<<'EOF'`, `<<-EOF`) hasta su línea de cierre. Se conserva el
# resto de la línea que lo abre, que puede seguir con `&& git ...`.
HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2[^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.DOTALL)
CONTROL = re.compile(r"^[;&|()]+$")
REDIRECT = re.compile(r"^[<>&]+$")
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
FALLBACK_SPLIT = re.compile(r"&&|\|\||[;|()]")


def _tokens(text: str) -> list[str]:
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    # Sin comentarios: con los saltos de línea ya convertidos en `;`, un `#` se comería el resto.
    lex.commenters = ""
    return list(lex)


def _segments(command: str) -> list[list[str]]:
    text = HEREDOC.sub(r"\1", command).replace("\\\n", " ").replace("\n", " ; ")
    try:
        tokens = _tokens(text)
    except ValueError:
        return [part.split() for part in FALLBACK_SPLIT.split(text)]
    segments: list[list[str]] = [[]]
    for token in tokens:
        if CONTROL.match(token):
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def git_calls(command: str) -> list[tuple[str, list[str]]]:
    """(subcomando, argumentos) de cada `git` que ejecuta el comando, en orden."""
    calls: list[tuple[str, list[str]]] = []
    for segment in _segments(command):
        words = segment
        while words and ASSIGNMENT.match(words[0]):
            words = words[1:]
        if not words or os.path.basename(words[0]).lower() not in {"git", "git.exe"}:
            continue
        i = 1
        # Opciones globales antes del subcomando: `-C ruta`, `-c clave=valor`, `--no-pager`...
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in {"-C", "-c"} else 1
        if i >= len(words):
            continue
        args = words[i + 1 :]
        for j, arg in enumerate(args):
            if REDIRECT.match(arg):
                # `2>/dev/null`: el `2` y lo que sigue son del shell, no de git.
                args = args[: j - 1] if j and args[j - 1].isdigit() else args[:j]
                break
        calls.append((words[i], args))
    return calls
