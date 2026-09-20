"""Estado de todos los repos de una carpeta, de una vez: git, PR, CI, issues y pendientes de sesiones.

Lo llama la skill `/repos`. Es determinista y de solo lectura (el único efecto es `git fetch`),
para que "qué hay pendiente en cada repo" no dependa de que un modelo se acuerde de mirar todo.

Por repo:
- git: rama, ficheros sin commitear, commits por delante o detrás de `origin`, worktrees vivos,
  ramas locales ya fusionadas (por `merge-base` o por PR fusionado) que siguen sin borrar.
- GitHub (vía `gh`): PR abiertos con draft, estado de checks y edad; issues abiertos; último
  run del CI en la rama por defecto.
- Sesiones recientes de Claude Code: las transcripciones viven en `~/.claude/projects/<ruta
  codificada>/*.jsonl`. Del último mensaje del asistente de cada sesión de los últimos N días
  se sacan las líneas que hablan de pendientes. Es la red de seguridad para hilos cerrados sin
  `/cierre`; la fuente fiable son los issues.

Sin `gh` o sin red, las secciones de GitHub dicen "no disponible" y el resto sigue. Nunca sale
con error: la skill que lo llama aborta entera si un comando `!` falla.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT_GIT = 20
TIMEOUT_GH = 30
PENDING = re.compile(
    r"\bpendientes?\b|\bqueda(?:n|r[ií]a)?\s+(?:por|sin)\b|\bsin verificar\b|\bno he (?:tocado|podido)\b",
    re.IGNORECASE,
)
# Líneas que hablan de pendientes para decir que no hay: se descartan, no son pendientes.
NOTHING_PENDING = re.compile(
    r"nada pendiente|sin pendientes|no queda nada|0 cambios pendientes|no tareas pendientes", re.IGNORECASE
)
MAX_PENDING_LINES = 6


def run(args: list[str], cwd: Path, timeout: int) -> str | None:
    """stdout de un comando, o None si falla, no existe o tarda demasiado."""
    try:
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git(cwd: Path, *args: str) -> str | None:
    return run(["git", *args], cwd, TIMEOUT_GIT)


def gh_json(cwd: Path, *args: str) -> list | dict | None:
    out = run(["gh", *args], cwd, TIMEOUT_GH)
    if out is None:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


@dataclass
class Repo:
    path: Path
    branch: str = "?"
    dirty: int = 0
    ahead: int = 0
    behind: int = 0
    worktrees: int = 0
    merged_branches: list[str] = field(default_factory=list)
    open_prs: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    ci_main: str = "no disponible"
    gh_ok: bool = True
    sessions: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = []
        if self.dirty:
            parts.append(f"{self.dirty} sin commitear")
        if self.ahead:
            parts.append(f"{self.ahead} sin push")
        if self.behind:
            parts.append(f"{self.behind} por detrás de origin")
        if self.worktrees:
            parts.append(f"{self.worktrees} worktree(s)")
        if self.merged_branches:
            parts.append(f"{len(self.merged_branches)} rama(s) fusionada(s) sin borrar")
        if self.open_prs:
            parts.append(f"{len(self.open_prs)} PR abierto(s)")
        if self.issues:
            parts.append(f"{len(self.issues)} issue(s)")
        if self.ci_main.startswith("failure"):
            parts.append("CI de main en rojo")
        if self.pending:
            parts.append(f"{len(self.pending)} línea(s) de pendientes en sesiones")
        return ", ".join(parts) if parts else "nada pendiente"


def default_branch(cwd: Path) -> str:
    head = git(cwd, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return head.removeprefix("origin/") if head else "main"


def collect_git(repo: Repo, fetch: bool) -> None:
    cwd = repo.path
    if fetch:
        git(cwd, "fetch", "--prune", "--quiet")
    repo.branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    status = git(cwd, "status", "--porcelain", "--untracked-files=no")
    repo.dirty = len(status.splitlines()) if status else 0
    counts = git(cwd, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts:
        a, b = counts.split()
        repo.ahead, repo.behind = int(a), int(b)
    wt = git(cwd, "worktree", "list", "--porcelain") or ""
    repo.worktrees = max(0, wt.count("worktree ") - 1)
    base = default_branch(cwd)
    branches = git(cwd, "for-each-ref", "--format=%(refname:short)", "refs/heads/") or ""
    for name in branches.splitlines():
        if name in (base, repo.branch):
            continue
        if run(["git", "merge-base", "--is-ancestor", name, f"origin/{base}"], cwd, TIMEOUT_GIT) is not None:
            repo.merged_branches.append(name)
    return None


def collect_gh(repo: Repo) -> None:
    cwd = repo.path
    prs = gh_json(
        cwd, "pr", "list", "--state", "open", "--json", "number,title,isDraft,createdAt,statusCheckRollup"
    )
    if prs is None:
        repo.gh_ok = False
        return
    for pr in prs:
        checks = [c.get("conclusion") or c.get("state") or "" for c in pr.get("statusCheckRollup") or []]
        red = sum(1 for c in checks if c in ("FAILURE", "ERROR", "TIMED_OUT"))
        pending = sum(1 for c in checks if c in ("", "PENDING", "IN_PROGRESS", "QUEUED"))
        state = "rojo" if red else ("en curso" if pending else "verde")
        days = _age_days(pr.get("createdAt"))
        draft = " draft" if pr.get("isDraft") else ""
        repo.open_prs.append(f"#{pr['number']}{draft} {state}, {days} d: {pr['title'][:60]}")
    merged = gh_json(cwd, "pr", "list", "--state", "merged", "--limit", "40", "--json", "headRefName") or []
    merged_heads = {m.get("headRefName") for m in merged}
    branches = git(cwd, "for-each-ref", "--format=%(refname:short)", "refs/heads/") or ""
    for name in branches.splitlines():
        if name in merged_heads and name not in repo.merged_branches and name != repo.branch:
            repo.merged_branches.append(name)
    issues = (
        gh_json(cwd, "issue", "list", "--state", "open", "--limit", "15", "--json", "number,title,createdAt")
        or []
    )
    repo.issues = [f"#{i['number']} ({_age_days(i.get('createdAt'))} d): {i['title'][:70]}" for i in issues]
    runs = gh_json(
        cwd,
        "run",
        "list",
        "--branch",
        default_branch(cwd),
        "--limit",
        "1",
        "--json",
        "conclusion,name,updatedAt",
    )
    if runs:
        r = runs[0]
        repo.ci_main = (
            f"{r.get('conclusion') or 'en curso'} ({r.get('name')}, hace {_age_days(r.get('updatedAt'))} d)"
        )


def _age_days(iso: str | None) -> int:
    if not iso:
        return 0
    try:
        t = time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return 0
    return max(0, int((time.time() - t) / 86400))


def encode_project_path(path: Path) -> str:
    """Así nombra Claude Code la carpeta de transcripciones de un proyecto: todo lo que no es
    alfanumérico pasa a guion (`D:\\A\\b_c` -> `D--A-b-c`)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def last_assistant_text(transcript: Path) -> str:
    last = ""
    try:
        with transcript.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if o.get("type") != "assistant":
                    continue
                for c in o.get("message", {}).get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                        last = c["text"]
    except OSError:
        return ""
    return last


def collect_sessions(repo: Repo, projects: Path, days: int) -> None:
    key = encode_project_path(repo.path)
    cutoff = time.time() - days * 86400
    dirs = [d for d in projects.iterdir() if d.is_dir() and (d.name == key or d.name.startswith(key + "--"))]
    transcripts = sorted(
        (t for d in dirs for t in d.glob("*.jsonl") if t.stat().st_mtime >= cutoff),
        key=lambda t: t.stat().st_mtime,
        reverse=True,
    )
    for t in transcripts:
        when = time.strftime("%Y-%m-%d", time.localtime(t.stat().st_mtime))
        text = last_assistant_text(t)
        lines = [
            ln.strip(" -*")
            for ln in text.splitlines()
            if PENDING.search(ln) and not NOTHING_PENDING.search(ln)
        ]
        repo.sessions.append(f"{when} {t.stem[:8]}")
        for ln in lines[:MAX_PENDING_LINES]:
            repo.pending.append(f"{when} ({t.stem[:8]}): {ln[:160]}")


def collect(repo: Repo, projects: Path, days: int, fetch: bool) -> Repo:
    collect_git(repo, fetch)
    collect_gh(repo)
    if projects.is_dir():
        collect_sessions(repo, projects, days)
    return repo


def render(repo: Repo) -> str:
    out = [f"## {repo.path.name}: {repo.summary}"]
    out.append(
        f"- rama `{repo.branch}`, CI de main: {repo.ci_main}" + ("" if repo.gh_ok else " (gh no disponible)")
    )
    if repo.merged_branches:
        out.append("- ramas fusionadas sin borrar: " + ", ".join(repo.merged_branches))
    for pr in repo.open_prs:
        out.append(f"- PR {pr}")
    for issue in repo.issues:
        out.append(f"- issue {issue}")
    if repo.sessions:
        shown = ", ".join(repo.sessions[:4]) + ("..." if len(repo.sessions) > 4 else "")
        out.append(f"- sesiones recientes: {len(repo.sessions)} ({shown})")
    for p in repo.pending:
        out.append(f"- pendiente en sesión {p}")
    return "\n".join(out)


def find_repos(root: Path) -> list[Repo]:
    repos = []
    for d in sorted(root.iterdir()):
        if not (d / ".git").is_dir():
            continue
        if git(d, "remote", "get-url", "origin") is None:
            continue
        repos.append(Repo(path=d))
    return repos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=os.environ.get("CLAUDE_REPOS_ROOT") or str(Path.cwd().parent))
    parser.add_argument("--days", type=int, default=14, help="sesiones de los últimos N días (14)")
    parser.add_argument(
        "--no-fetch", action="store_true", help="no hacer git fetch (más rápido, datos locales)"
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"No existe la carpeta de repos: {root}")
        return 0
    projects = Path.home() / ".claude" / "projects"
    repos = find_repos(root)
    if not repos:
        print(f"Sin repos con remoto en {root}")
        return 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(repos))) as pool:
        done = list(pool.map(lambda r: collect(r, projects, args.days, not args.no_fetch), repos))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"# Repos en {root} ({len(done)}), sesiones de los últimos {args.days} días\n")
    for repo in done:
        print(render(repo))
        print()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - es la salida de una skill: nunca abortar la skill entera
        print(f"status.py falló: {exc!r}")
        sys.exit(0)
