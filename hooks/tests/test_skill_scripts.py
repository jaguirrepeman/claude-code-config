"""Tests de los scripts que acompañan a las skills. Van aquí, y no junto a la skill, porque
`install.sh` copia la carpeta de cada skill entera a `~/.claude/skills/` y los tests no se
instalan.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def test_tells_prints_arrows_and_emoji_when_stdout_is_not_utf8(tmp_path: Path) -> None:
    # En Windows, con la salida a una tubería (la herramienta Bash de Claude Code), Python escribe
    # en cp1252 y un `→` o un emoji en la línea citada tumbaban el script con UnicodeEncodeError.
    # PYTHONIOENCODING=cp1252 reproduce ese caso también en el CI de Linux.
    text = tmp_path / "texto.md"
    text.write_text("Esto es clave → y además ✅ lo cambia todo.\n", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    r = subprocess.run(
        [PYTHON, str(REPO / "skills" / "humanizar" / "tells.py"), str(text), "--all"],
        capture_output=True,
        env=env,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr.decode("utf-8", errors="replace")
    assert "→" in r.stdout.decode("utf-8")
