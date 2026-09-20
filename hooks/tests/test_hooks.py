"""Tests de los hooks: cada uno se ejecuta como lo ejecutaría Claude Code (proceso aparte, JSON
por stdin, decisión por stdout). Offline y deterministas; crean repos git temporales.

Lo que fijan es el contrato de cada hook: cuándo bloquea, cuándo calla y que nunca sale con
error. Un cambio en un hook que rompa uno de estos tests cambia el comportamiento de todas las
sesiones de todas las máquinas, que es justo lo que no debe pasar sin verlo.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_hook(name: str, payload: dict, cwd: Path, env: dict[str, str] | None = None) -> tuple[int, str]:
    """Ejecuta un hook con el JSON dado por stdin y devuelve (exit code, stdout)."""
    full_env = {**os.environ, **(env or {})}
    r = subprocess.run(
        [PYTHON, str(HOOKS / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(cwd),
        env=full_env,
        timeout=60,
    )
    return r.returncode, r.stdout.strip()


def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(cwd), check=True)
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repo git con un commit en `main` y sin remoto."""
    git("init", "-q", "-b", "main", cwd=tmp_path)
    git("config", "user.email", "test@example.com", cwd=tmp_path)
    git("config", "user.name", "Test", cwd=tmp_path)
    (tmp_path / "README.md").write_text("hola\n", encoding="utf-8")
    git("add", "README.md", cwd=tmp_path)
    git("commit", "-q", "-m", "init", cwd=tmp_path)
    return tmp_path


def bash(command: str, cwd: Path) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}


def decision(stdout: str) -> str | None:
    if not stdout:
        return None
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"]


# --- block-commit-on-protected -------------------------------------------------------------


def test_commit_blocked_on_main(repo: Path) -> None:
    code, out = run_hook("block-commit-on-protected.py", bash("git commit -m x", repo), repo)
    assert code == 0
    assert decision(out) == "deny"
    assert "main" in json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]


def test_commit_allowed_on_feature_branch(repo: Path) -> None:
    git("checkout", "-q", "-b", "claude/tema", cwd=repo)
    code, out = run_hook("block-commit-on-protected.py", bash("git add x && git commit -m x", repo), repo)
    assert (code, out) == (0, "")


def test_non_commit_commands_pass_on_main(repo: Path) -> None:
    for cmd in ("git status", "git log --oneline", "echo commit"):
        code, out = run_hook("block-commit-on-protected.py", bash(cmd, repo), repo)
        assert (code, out) == (0, ""), cmd


def test_protected_branches_env_overrides_detection(repo: Path) -> None:
    git("checkout", "-q", "-b", "release", cwd=repo)
    env = {"CLAUDE_PROTECTED_BRANCHES": "main,release"}
    _, out = run_hook("block-commit-on-protected.py", bash("git commit -m x", repo), repo, env)
    assert decision(out) == "deny"


def test_commit_hook_fails_open_outside_git(tmp_path: Path) -> None:
    code, out = run_hook("block-commit-on-protected.py", bash("git commit -m x", tmp_path), tmp_path)
    assert (code, out) == (0, "")


@pytest.fixture
def other_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Segundo repo, en una rama de trabajo, para comandos que van a otro directorio."""
    root = tmp_path_factory.mktemp("other")
    git("init", "-q", "-b", "main", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt", cwd=root)
    git("commit", "-q", "-m", "init", cwd=root)
    git("checkout", "-q", "-b", "claude/x", cwd=root)
    return root


def test_commit_looks_at_cd_target_not_session_cwd(repo: Path, other_repo: Path) -> None:
    # La sesión está en `main` de un repo, pero el commit va a la rama de trabajo de otro:
    # mirar el cwd de la sesión daba un falso bloqueo.
    cmd = f'cd "{other_repo}" && git add a.txt && git commit -m x'
    code, out = run_hook("block-commit-on-protected.py", bash(cmd, repo), repo)
    assert (code, out) == (0, "")


def test_commit_looks_at_git_C_target(repo: Path, other_repo: Path) -> None:
    cmd = f'git -C "{other_repo}" commit -m x'
    code, out = run_hook("block-commit-on-protected.py", bash(cmd, repo), repo)
    assert (code, out) == (0, "")


def test_commit_blocked_when_cd_target_is_on_main(repo: Path, other_repo: Path) -> None:
    # Y al revés: la sesión en una rama de trabajo, el commit a un repo que está en main.
    cmd = f'cd "{repo}" && git commit -m x'
    code, out = run_hook("block-commit-on-protected.py", bash(cmd, other_repo), other_repo)
    assert code == 0
    assert decision(out) == "deny"


def test_cd_to_missing_dir_falls_back_to_session_cwd(repo: Path) -> None:
    cmd = "cd /no/existe && git commit -m x"
    code, out = run_hook("block-commit-on-protected.py", bash(cmd, repo), repo)
    assert decision(out) == "deny"


# --- session-start-status -------------------------------------------------------------------


def test_session_start_reports_branch_and_dirty_files(repo: Path) -> None:
    (repo / "nuevo.txt").write_text("x", encoding="utf-8")
    code, out = run_hook("session-start-status.py", {"hook_event_name": "SessionStart"}, repo)
    assert code == 0
    assert "Estado del repo" in out
    assert "Rama: main, 1 ficheros sin commitear (checkout principal)" in out
    assert "AVISO: estás en main" in out


def test_session_start_silent_outside_git(tmp_path: Path) -> None:
    code, out = run_hook("session-start-status.py", {"hook_event_name": "SessionStart"}, tmp_path)
    assert (code, out) == (0, "")


# --- lint-check -----------------------------------------------------------------------------

needs_ruff = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff no está en el PATH")


def edit(path: Path) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}, "cwd": str(path.parent)}


@needs_ruff
def test_lint_reports_ruff_findings_as_additional_context(tmp_path: Path) -> None:
    (tmp_path / "ruff.toml").write_text('[lint]\nselect = ["F"]\n', encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("import os\n", encoding="utf-8")
    code, out = run_hook("lint-check.py", edit(bad), tmp_path)
    assert code == 0
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "F401" in context and "bad.py" in context


@needs_ruff
def test_lint_silent_on_clean_file(tmp_path: Path) -> None:
    (tmp_path / "ruff.toml").write_text('[lint]\nselect = ["F"]\n', encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text('print("hola")\n', encoding="utf-8")
    code, out = run_hook("lint-check.py", edit(good), tmp_path)
    assert (code, out) == (0, "")


def test_lint_ignores_non_code_files(tmp_path: Path) -> None:
    doc = tmp_path / "notas.md"
    doc.write_text("# hola\n", encoding="utf-8")
    code, out = run_hook("lint-check.py", edit(doc), tmp_path)
    assert (code, out) == (0, "")


UV_PYPROJECT = '[project]\nname = "demo"\nversion = "0"\n\n[tool.ruff.lint]\nselect = ["F"]\n'


@needs_ruff
@pytest.mark.parametrize("project_dir", ["", "backend"])
def test_lint_uses_the_repo_venv_created_by_uv(tmp_path: Path, project_dir: str) -> None:
    # `uv sync` deja el venv en `.venv` junto al pyproject (en la raíz o en `backend/`), y ruff
    # como binario dentro. El hook tiene que usar ese ruff, no uno global: se vacía el PATH y
    # se copia el ruff real dentro del venv simulado. Sin venv y sin PATH, calla (falla abierto).
    project = tmp_path / project_dir if project_dir else tmp_path
    (project / "app").mkdir(parents=True)
    (project / "pyproject.toml").write_text(UV_PYPROJECT, encoding="utf-8")
    bad = project / "app" / "bad.py"
    bad.write_text("import os\n", encoding="utf-8")
    no_ruff_in_path = {"PATH": str(tmp_path / "empty-bin")}
    (tmp_path / "empty-bin").mkdir()

    code, out = run_hook("lint-check.py", edit(bad), tmp_path, no_ruff_in_path)
    assert (code, out) == (0, "")

    venv_ruff = project / ".venv" / ("Scripts/ruff.exe" if os.name == "nt" else "bin/ruff")
    venv_ruff.parent.mkdir(parents=True)
    shutil.copy(shutil.which("ruff"), venv_ruff)
    code, out = run_hook("lint-check.py", edit(bad), tmp_path, no_ruff_in_path)
    assert code == 0
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "F401" in context and "bad.py" in context


# --- pre-push-verify ------------------------------------------------------------------------


def write_verify(repo: Path, command: str) -> None:
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "verify-command").write_text(f"# comentario\n{command}\n", encoding="utf-8")


def test_push_blocked_when_verification_fails(repo: Path) -> None:
    write_verify(repo, f'"{PYTHON}" -c "import sys; print(\'2 failed\'); sys.exit(1)"')
    code, out = run_hook("pre-push-verify.py", bash("git push -u origin claude/x", repo), repo)
    assert code == 0
    assert decision(out) == "deny"
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "2 failed" in reason and "exit 1" in reason


def test_push_allowed_when_verification_passes(repo: Path) -> None:
    write_verify(repo, f'"{PYTHON}" -c "print(\'ok\')"')
    code, out = run_hook("pre-push-verify.py", bash("git push", repo), repo)
    assert (code, out) == (0, "")


def test_push_allowed_without_verify_file(repo: Path) -> None:
    code, out = run_hook("pre-push-verify.py", bash("git push", repo), repo)
    assert (code, out) == (0, "")


def test_push_verifies_cd_target_repo(repo: Path, other_repo: Path) -> None:
    # La sesión no tiene verify-command; el repo al que va el push sí, y falla: se bloquea.
    write_verify(other_repo, f'"{PYTHON}" -c "import sys; print(\'rojo\'); sys.exit(3)"')
    code, out = run_hook("pre-push-verify.py", bash(f'cd "{other_repo}" && git push', repo), repo)
    assert code == 0
    assert decision(out) == "deny"
    assert "rojo" in json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]


def test_push_hook_ignores_other_commands(repo: Path) -> None:
    write_verify(repo, f'"{PYTHON}" -c "import sys; sys.exit(1)"')
    for cmd in ("git status", "git pull", "echo push"):
        code, out = run_hook("pre-push-verify.py", bash(cmd, repo), repo)
        assert (code, out) == (0, ""), cmd


def test_push_hook_can_be_skipped_for_a_session(repo: Path) -> None:
    write_verify(repo, f'"{PYTHON}" -c "import sys; sys.exit(1)"')
    env = {"CLAUDE_SKIP_VERIFY": "1"}
    code, out = run_hook("pre-push-verify.py", bash("git push", repo), repo, env)
    assert (code, out) == (0, "")


def test_push_hook_fails_open_on_timeout(repo: Path) -> None:
    write_verify(repo, f'"{PYTHON}" -c "import time; time.sleep(5)"')
    env = {"CLAUDE_VERIFY_TIMEOUT": "1"}
    code, out = run_hook("pre-push-verify.py", bash("git push", repo), repo, env)
    assert (code, out) == (0, "")


def test_env_command_overrides_file(repo: Path) -> None:
    write_verify(repo, f'"{PYTHON}" -c "print(\'ok\')"')
    env = {"CLAUDE_VERIFY_CMD": f'"{PYTHON}" -c "import sys; sys.exit(3)"'}
    _, out = run_hook("pre-push-verify.py", bash("git push", repo), repo, env)
    assert decision(out) == "deny"
    assert "exit 3" in json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]


# --- pending-guard ---------------------------------------------------------------------------


def stop(message: str, active: bool = False) -> dict:
    return {"hook_event_name": "Stop", "last_assistant_message": message, "stop_hook_active": active}


CLOSING_WITH_PENDING = (
    "Hecho y en producción. PR #31 fusionado por el gate y desplegado.\n\n"
    "Pendiente: la limpieza del cache del sitemap y el rating que sigue sin verificar."
)


def test_pending_guard_blocks_closing_message_with_pending_items(tmp_path: Path) -> None:
    code, out = run_hook("pending-guard.py", stop(CLOSING_WITH_PENDING), tmp_path)
    assert code == 0
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "gh issue create" in payload["reason"]


def test_pending_guard_blocks_only_once_per_turn(tmp_path: Path) -> None:
    code, out = run_hook("pending-guard.py", stop(CLOSING_WITH_PENDING, active=True), tmp_path)
    assert (code, out) == (0, "")


def test_pending_guard_passes_when_pending_items_are_issues(tmp_path: Path) -> None:
    msg = CLOSING_WITH_PENDING + "\n\nIssues creados: https://github.com/u/r/issues/12"
    code, out = run_hook("pending-guard.py", stop(msg), tmp_path)
    assert (code, out) == (0, "")


def test_pending_guard_passes_when_nothing_pending(tmp_path: Path) -> None:
    msg = "Hecho y en producción. PR #31 fusionado por el gate. Sin pendientes que guardar."
    code, out = run_hook("pending-guard.py", stop(msg), tmp_path)
    assert (code, out) == (0, "")


def test_pending_guard_ignores_mid_task_messages(tmp_path: Path) -> None:
    msg = "Queda por revisar el parser; sigo con el siguiente fichero, pendiente el test."
    code, out = run_hook("pending-guard.py", stop(msg), tmp_path)
    assert (code, out) == (0, "")


def test_pending_guard_ignores_cierre_not_archivable_verdict(tmp_path: Path) -> None:
    msg = "NO ARCHIVABLE: hay 2 commits sin push y un pendiente sin issue. PR fusionado por el gate."
    code, out = run_hook("pending-guard.py", stop(msg), tmp_path)
    assert (code, out) == (0, "")


def test_pending_guard_can_be_skipped_for_a_session(tmp_path: Path) -> None:
    env = {"CLAUDE_SKIP_PENDING_GUARD": "1"}
    code, out = run_hook("pending-guard.py", stop(CLOSING_WITH_PENDING), tmp_path, env)
    assert (code, out) == (0, "")


def test_pending_guard_never_fails_on_bad_input(tmp_path: Path) -> None:
    r = subprocess.run(
        [PYTHON, str(HOOKS / "pending-guard.py")],
        input="esto no es json",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=30,
    )
    assert (r.returncode, r.stdout.strip()) == (0, "")
