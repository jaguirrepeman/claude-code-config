"""Tests de los scripts que acompañan a las skills. Van aquí, y no junto a la skill, porque
`install.sh` copia la carpeta de cada skill entera a `~/.claude/skills/` y los tests no se
instalan.
"""

from __future__ import annotations

import importlib.util
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


def _load_pick():
    spec = importlib.util.spec_from_file_location(
        "pick_mejora", REPO / "skills" / "mejora" / "scripts" / "pick.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # las dataclasses buscan su módulo aquí
    spec.loader.exec_module(module)
    return module


def test_pick_audits_never_audited_first_then_oldest() -> None:
    q = _load_pick()
    names = ["atril", "gymapp", "finance"]
    assert q.pick_audit(names, {"atril": "2026-10-10"}) == "gymapp"
    assert (
        q.pick_audit(names, {"atril": "2026-10-10", "gymapp": "2026-10-03", "finance": "2026-10-17"})
        == "gymapp"
    )
    assert q.pick_audit([], {}) is None


def _issue(n: int, labels: list[str], created: str = "2026-10-01") -> dict:
    return {"number": n, "title": f"issue {n}", "labels": [{"name": x} for x in labels], "createdAt": created}


def test_pick_fix_orders_by_severity_and_skips_issues_with_open_pr() -> None:
    q = _load_pick()
    issues = {
        "atril": [_issue(4, ["audit-autonomo", "P2"]), _issue(7, ["audit-autonomo", "P1"])],
        "gymapp": [_issue(2, ["audit-autonomo", "P1"], created="2026-09-01"), _issue(9, ["audit-autonomo"])],
    }
    prs = {"atril": [{"headRefName": "claude/audit-7-algo"}], "gymapp": []}
    candidates, skipped = q.pick_fix(issues, prs, max_drafts=2)
    assert [(c.repo, c.number) for c in candidates] == [("gymapp", 2), ("atril", 4), ("gymapp", 9)]
    assert skipped == []


def test_pick_fix_takes_review_issues_as_draft_and_autonomous_as_ready() -> None:
    # audit-revision también lo arregla el robot, pero su PR va en draft para que lo mire la
    # persona; audit-autonomo sale listo y lo fusiona el gate. Un P1 de revisión va antes que un P3
    # autónomo: manda la severidad, no el modo.
    q = _load_pick()
    issues = {"atril": [_issue(3, ["audit-autonomo", "P3"]), _issue(8, ["audit-revision", "P1"])]}
    candidates, _ = q.pick_fix(issues, {"atril": []}, max_drafts=2)
    assert [(c.number, c.pr_mode) for c in candidates] == [(8, "draft"), (3, "listo")]


def test_merge_issue_lists_dedupes_issue_with_both_labels() -> None:
    q = _load_pick()
    a = [_issue(1, ["audit-autonomo"]), _issue(2, ["audit-autonomo", "audit-revision"])]
    b = [_issue(2, ["audit-autonomo", "audit-revision"]), _issue(5, ["audit-revision"])]
    assert [i["number"] for i in q.merge_issue_lists(a, b)] == [1, 2, 5]
    # Con las dos etiquetas gana la prudente: draft.
    candidates, _ = q.pick_fix({"r": q.merge_issue_lists(a, b)}, {"r": []}, max_drafts=2)
    assert {c.number: c.pr_mode for c in candidates}[2] == "draft"


def test_repos_for_place_splits_pc_and_cloud() -> None:
    # gymapp va solo en la nube; el resto en el PC, y la nube los coge solo si el PC no ha pasado
    # en las últimas horas. Sin latido (nunca pasó o no se pudo leer) cuenta como viejo.
    q = _load_pick()
    names = ["atril", "finance", "gymapp"]
    policy = {"gymapp": "nube"}
    now = q.dt.datetime(2026, 11, 28, 14, 30, tzinfo=q.dt.timezone.utc)
    fresh = "2026-11-28T13:05:00+00:00"
    stale = "2026-11-28T09:00:00+00:00"
    assert q.repos_for_place(names, policy, "pc", fresh, now) == ["atril", "finance"]
    assert q.repos_for_place(names, policy, "nube", fresh, now) == ["gymapp"]
    assert q.repos_for_place(names, policy, "nube", stale, now) == names
    assert q.repos_for_place(names, policy, "nube", None, now) == names
    assert q.repos_for_place(names, policy, "nube", "basura", now) == names


def test_parse_rest_issues_drops_pull_requests() -> None:
    # La API REST de issues devuelve también los PR; no son issues que arreglar.
    q = _load_pick()
    raw = [
        {"number": 3, "title": "a", "labels": [{"name": "P1"}], "created_at": "2026-11-01T00:00:00Z"},
        {"number": 4, "title": "pr", "labels": [], "created_at": "x", "pull_request": {"url": "u"}},
    ]
    assert q.parse_rest_issues(raw) == [
        {"number": 3, "title": "a", "labels": [{"name": "P1"}], "createdAt": "2026-11-01T00:00:00Z"}
    ]


def test_pick_fix_skips_repo_at_draft_limit() -> None:
    # El freno de PR abiertos: sin él, un sábado tras otro se apilan drafts que nadie revisa.
    q = _load_pick()
    issues = {"atril": [_issue(1, ["audit-autonomo", "P0"])], "gymapp": [_issue(3, ["audit-autonomo", "P3"])]}
    prs = {
        "atril": [{"headRefName": "claude/audit-5-a"}, {"headRefName": "claude/audit-6-b"}],
        "gymapp": [{"headRefName": "claude/otra-cosa"}],
    }
    candidates, skipped = q.pick_fix(issues, prs, max_drafts=2)
    assert [(c.repo, c.number) for c in candidates] == [("gymapp", 3)]
    assert len(skipped) == 1 and skipped[0].startswith("atril")


def test_pick_mark_then_audit_rotates(tmp_path: Path) -> None:
    root = tmp_path / "repos"
    for name in ("alfa", "beta"):
        d = root / name
        (d / ".claude").mkdir(parents=True)
        (d / ".claude" / "verify-command").write_text("true\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(d)], check=True, timeout=30)
        subprocess.run(
            ["git", "-C", str(d), "remote", "add", "origin", f"https://github.com/yo/{name}.git"],
            check=True,
            timeout=30,
        )
    (root / "sin-verify").mkdir()
    subprocess.run(["git", "init", "-q", str(root / "sin-verify")], check=True, timeout=30)
    state = tmp_path / "state.json"
    script = str(REPO / "skills" / "mejora" / "scripts" / "pick.py")

    def run(*args: str) -> str:
        r = subprocess.run(
            [PYTHON, script, *args, "--root", str(root), "--state", str(state), "--sin-github"],
            capture_output=True,
            timeout=60,
        )
        assert r.returncode == 0
        return r.stdout.decode("utf-8")

    first = run("auditar")
    assert "REPO: alfa" in first and "sin-verify" not in first
    run("marcar", "alfa")
    assert "REPO: beta" in run("auditar")


def test_pick_ignores_worktree_folders(tmp_path: Path) -> None:
    # Un worktree hermano (idealista_bot-map) tiene `.git` como fichero y el mismo remoto: si
    # cuenta como repo, el mismo repo entra dos veces en la rotación.
    root = tmp_path / "repos"
    main = root / "bot"
    (main / ".claude").mkdir(parents=True)
    (main / ".claude" / "verify-command").write_text("true\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(main)], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(main), "remote", "add", "origin", "https://github.com/yo/bot.git"],
        check=True,
        timeout=30,
    )
    subprocess.run(["git", "-C", str(main), "add", "."], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(main), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"],
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-q", str(root / "bot-map")], check=True, timeout=30
    )
    r = subprocess.run(
        [
            PYTHON,
            str(REPO / "skills" / "mejora" / "scripts" / "pick.py"),
            "auditar",
            "--root",
            str(root),
            "--state",
            str(tmp_path / "s.json"),
            "--sin-github",
        ],
        capture_output=True,
        timeout=60,
    )
    out = r.stdout.decode("utf-8")
    assert "ROTACIÓN: bot=nunca" in out and "bot-map" not in out, out
