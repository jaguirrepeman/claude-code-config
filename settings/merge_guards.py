"""Fusiona las guardas de git en ~/.claude/settings.json de una máquina que no lo tiene.

Para la nube: allí `install.sh` copia los hooks pero nadie fusiona `settings/*.snippet.json`, y
la sesión arranca sin guardas (probado el 2026-11-28 con Claude Code 2.1.332: un commit en main
entró sin bloqueo). Los hooks se recargan en caliente, así que basta con correr esto justo
después de `install.sh`, en la misma sesión.

Qué escribe:
- `hooks.PreToolUse` del snippet: commit en la rama protegida, push con verificación y borrado
  de ramas. Solo ese evento: los de `PostToolUse` y `Stop` no hacen falta para proteger git y
  cambiarían el comportamiento de una tarea desatendida.
- `permissions.deny` del snippet. En caliente no se aplica (en la misma prueba `git add -A` pasó
  tras fusionarlo); se escribe para que valga si la sesión se reinicia.

Nunca pisa un `settings.json` que ya tenga hooks: en el PC se fusiona a mano (ver README) y un
segundo arranque en la misma nube no tiene nada que hacer.

Uso: `python3 settings/merge_guards.py` (respeta `CLAUDE_CONFIG_DIR`).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("merge_guards")
SNIPPETS = Path(__file__).resolve().parent


def merge(dest: Path, snippets: Path = SNIPPETS) -> str:
    hooks = json.loads((snippets / "hooks.snippet.json").read_text(encoding="utf-8"))["hooks"]
    perms = json.loads((snippets / "permissions.snippet.json").read_text(encoding="utf-8"))
    deny = perms["permissions"]["deny"]

    current = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {}
    if current.get("hooks"):
        return f"sin cambios: {dest} ya tiene hooks"

    current["hooks"] = {"PreToolUse": hooks["PreToolUse"]}
    permissions = current.setdefault("permissions", {})
    permissions["deny"] = sorted(set(permissions.get("deny", [])) | set(deny))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    guards = sum(len(group["hooks"]) for group in hooks["PreToolUse"])
    return f"escrito {dest}: {guards} guardas en PreToolUse, {len(permissions['deny'])} reglas deny"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    logger.info(merge(base / "settings.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
