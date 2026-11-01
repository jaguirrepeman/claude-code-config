"""Cola de la mejora programada: qué repo toca auditar y qué issue toca arreglar.

Lo llama la skill `/mejora`. Determinista: la elección no depende de que un modelo se acuerde de
mirar todos los repos. Los repos candidatos son los de `--root` que tienen
`.claude/verify-command` (sin él no hay forma de comprobar un arreglo antes del PR), o los que se
pasen con `--repos`.

    pick.py auditar [--root R] [--repos a,b]   el repo con la auditoría más antigua (o ninguna)
    pick.py marcar <repo> [--state F]           apunta que <repo> se auditó hoy
    pick.py arreglar [--root R] [--repos a,b]   el issue `audit-autonomo` más grave que se puede
                                                 coger sin pasar de `--max-drafts` PR abiertos

El estado de la rotación vive en `~/.claude/state/mejora.json`. Si se pierde, la rotación empieza
de nuevo; no es una decisión, solo un turno. Nunca sale con error: la skill que lo llama aborta
entera si un comando `!` falla.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_GIT = 20
TIMEOUT_GH = 30
LABEL_AUTONOMOUS = "audit-autonomo"
BRANCH_PREFIX = "claude/audit-"
SEVERITIES = ("P0", "P1", "P2", "P3")
DEFAULT_STATE = Path.home() / ".claude" / "state" / "mejora.json"


@dataclass
class Repo:
    path: Path
    slug: str  # owner/name en GitHub, que no siempre coincide con la carpeta (portfolio_tracker)

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class Candidate:
    repo: str
    number: int
    title: str
    severity: str
    created: str


def run(cmd: list[str], cwd: Path | None = None, timeout: int = TIMEOUT_GIT) -> str | None:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def slug_from_url(url: str) -> str | None:
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def find_repos(root: Path, only: list[str]) -> list[Repo]:
    repos = []
    for d in sorted(root.iterdir()):
        # En un worktree `.git` es un fichero: sería el mismo repo dos veces en la rotación.
        if not (d / ".git").is_dir():
            continue
        if only and d.name not in only:
            continue
        if not only and not (d / ".claude" / "verify-command").is_file():
            continue
        url = run(["git", "remote", "get-url", "origin"], cwd=d)
        slug = slug_from_url(url) if url else None
        if slug:
            repos.append(Repo(path=d, slug=slug))
    return repos


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def pick_audit(names: list[str], audited: dict[str, str]) -> str | None:
    """El nunca auditado primero; después, el de fecha más antigua. Empate: orden de la lista."""
    if not names:
        return None
    return min(names, key=lambda n: (n in audited, audited.get(n, ""), names.index(n)))


def severity_of(labels: list[str]) -> str:
    for s in SEVERITIES:
        if s in labels:
            return s
    return "P3"  # sin etiqueta de severidad cuenta como la menor, no se cuela delante


def pick_fix(
    issues: dict[str, list[dict]], prs: dict[str, list[dict]], max_drafts: int
) -> tuple[list[Candidate], list[str]]:
    """Candidatos ordenados por severidad y antigüedad, y los repos saltados con su motivo."""
    candidates: list[Candidate] = []
    skipped: list[str] = []
    for repo, repo_issues in issues.items():
        heads = [p.get("headRefName", "") for p in prs.get(repo, [])]
        own = [h for h in heads if h.startswith(BRANCH_PREFIX)]
        if len(own) >= max_drafts:
            skipped.append(f"{repo}: {len(own)} PR de la mejora abiertos (máximo {max_drafts})")
            continue
        for issue in repo_issues:
            n = issue["number"]
            if any(h.startswith(f"{BRANCH_PREFIX}{n}-") for h in heads):
                continue  # ya tiene su PR abierto
            labels = [lb["name"] for lb in issue.get("labels", [])]
            candidates.append(
                Candidate(repo, n, issue["title"], severity_of(labels), issue.get("createdAt", ""))
            )
    candidates.sort(key=lambda c: (SEVERITIES.index(c.severity), c.created, c.repo, c.number))
    return candidates, skipped


def gh_json(args: list[str]) -> list[dict] | None:
    out = run(["gh", *args], timeout=TIMEOUT_GH)
    if out is None:
        return None
    try:
        return json.loads(out or "[]")
    except ValueError:
        return None


def cmd_audit(repos: list[Repo], state: dict) -> None:
    audited = state.get("audited", {})
    name = pick_audit([r.name for r in repos], audited)
    if name is None:
        print("Sin repos candidatos (ninguno con .claude/verify-command en la carpeta).")
        return
    repo = next(r for r in repos if r.name == name)
    print(f"REPO: {repo.name}")
    print(f"RUTA: {repo.path.as_posix()}")
    print(f"GITHUB: {repo.slug}")
    print(f"ÚLTIMA AUDITORÍA: {audited.get(name, 'nunca')}")
    print("ROTACIÓN: " + ", ".join(f"{r.name}={audited.get(r.name, 'nunca')}" for r in repos))


def cmd_fix(repos: list[Repo], max_drafts: int) -> None:
    issues: dict[str, list[dict]] = {}
    prs: dict[str, list[dict]] = {}
    unavailable = []
    for r in repos:
        i = gh_json(
            [
                "issue",
                "list",
                "-R",
                r.slug,
                "--state",
                "open",
                "--label",
                LABEL_AUTONOMOUS,
                "--json",
                "number,title,labels,createdAt",
                "--limit",
                "50",
            ]
        )
        p = gh_json(["pr", "list", "-R", r.slug, "--state", "open", "--json", "headRefName"])
        if i is None or p is None:
            unavailable.append(r.name)
            continue
        issues[r.name], prs[r.name] = i, p
    candidates, skipped = pick_fix(issues, prs, max_drafts)
    by_name = {r.name: r for r in repos}
    if candidates:
        top = candidates[0]
        print(f"REPO: {top.repo}")
        print(f"RUTA: {by_name[top.repo].path.as_posix()}")
        print(f"GITHUB: {by_name[top.repo].slug}")
        print(f"ISSUE: #{top.number} [{top.severity}] {top.title}")
        print(f"RAMA: {BRANCH_PREFIX}{top.number}-<descripción-corta>")
    else:
        print("NADA QUE ARREGLAR: no hay issues audit-autonomo abiertos que se puedan coger.")
    if len(candidates) > 1:
        print("SIGUIENTES:")
        for c in candidates[1:6]:
            print(f"  {c.repo} #{c.number} [{c.severity}] {c.title}")
    for s in skipped:
        print(f"SALTADO: {s}")
    for u in unavailable:
        print(f"SIN GH: {u} (no se pudo leer; no cuenta como vacío)")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=["auditar", "marcar", "arreglar"])
    parser.add_argument("repo", nargs="?", help="con `marcar`: la carpeta del repo auditado")
    parser.add_argument("--root", default=os.environ.get("CLAUDE_REPOS_ROOT") or str(Path.cwd().parent))
    parser.add_argument(
        "--repos", default="", help="lista separada por comas; por defecto, los que tienen verify-command"
    )
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--max-drafts", type=int, default=2)
    args = parser.parse_args()
    state_path = Path(args.state)
    state = load_state(state_path)

    if args.mode == "marcar":
        if not args.repo:
            print("marcar necesita el nombre del repo")
            return 0
        state.setdefault("audited", {})[args.repo] = dt.date.today().isoformat()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Apuntado: {args.repo} auditado el {state['audited'][args.repo]}")
        return 0

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"No existe la carpeta de repos: {root}")
        return 0
    only = [x.strip() for x in args.repos.split(",") if x.strip()]
    repos = find_repos(root, only)
    if args.mode == "auditar":
        cmd_audit(repos, state)
    else:
        cmd_fix(repos, args.max_drafts)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - es la salida de una skill: nunca abortar la skill entera
        print(f"pick.py falló: {exc!r}")
        sys.exit(0)
