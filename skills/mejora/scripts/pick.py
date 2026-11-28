"""Cola de la mejora programada: qué repo toca auditar y qué issue toca arreglar.

Lo llama la skill `/mejora`. Determinista: la elección no depende de que un modelo se acuerde de
mirar todos los repos. Los repos candidatos son los de `--root` que tienen
`.claude/verify-command` (sin él no hay forma de comprobar un arreglo antes del PR), o los que se
pasen con `--repos`.

    pick.py auditar [--root R] [--repos a,b]   el repo con la auditoría más antigua (o ninguna)
    pick.py marcar <repo> [--state F]           apunta que <repo> se auditó hoy
    pick.py arreglar [--root R] [--repos a,b]   el issue `audit-autonomo` o `audit-revision` más
                                                 grave que se puede coger sin pasar de
                                                 `--max-drafts` PR abiertos, y si su PR sale listo
                                                 (autónomo) o en draft (revisión)

`--donde pc|nube` reparte el trabajo (ver `docs/plan-2026-11-nube.md`): `../repos.json` marca los
repos que van solo en la nube; el resto va en el PC, y la nube los coge solo si el PC no ha pasado
en las últimas `LATIDO_HORAS` horas. En el PC, cada llamada apunta ese latido.

El estado (rotación y latido) vive en el cuerpo de un issue abierto con la etiqueta
`mejora-estado` en el repo `claude-code-config` del mismo dueño, para que el PC y la nube vean lo
mismo. No en variables de Actions: la nube no las puede leer (probado el 2026-11-28). Si el issue
no se puede leer, se usa `~/.claude/state/mejora.json`. Si se pierde, la rotación empieza de
nuevo; no es una decisión, solo un turno. Todo GitHub va por `gh api` (REST): en la nube el
proxy rechaza `gh issue` y `gh pr`. Nunca sale con error: la skill que lo llama aborta entera si
un comando `!` falla.
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
LABEL_REVIEW = "audit-revision"
BRANCH_PREFIX = "claude/audit-"
SEVERITIES = ("P0", "P1", "P2", "P3")
DEFAULT_STATE = Path.home() / ".claude" / "state" / "mejora.json"
POLICY_FILE = Path(__file__).resolve().parent.parent / "repos.json"
STATE_REPO_NAME = "claude-code-config"
STATE_LABEL = "mejora-estado"
STATE_TITLE = "mejora: estado de la rotación y latido del PC (lo escribe el robot)"
LATIDO_HORAS = 3


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
    pr_mode: str = "listo"  # "listo" lo fusiona el gate; "draft" espera a la persona


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


def load_policy(path: Path = POLICY_FILE) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and not k.startswith("_")}


def repos_for_place(
    names: list[str], policy: dict[str, str], where: str, heartbeat: str | None, now: dt.datetime
) -> list[str]:
    """Qué repos le tocan a `where`. Un latido ilegible o ausente cuenta como PC no disponible."""
    cloud_only = [n for n in names if policy.get(n) == "nube"]
    pc = [n for n in names if n not in cloud_only]
    if where == "pc":
        return pc
    try:
        last = dt.datetime.fromisoformat(heartbeat) if heartbeat else None
    except ValueError:
        last = None
    pc_alive = last is not None and now - last < dt.timedelta(hours=LATIDO_HORAS)
    return cloud_only if pc_alive else names


def parse_rest_issues(raw: list[dict]) -> list[dict]:
    """Issues de la API REST con la forma que usa `pick_fix`, sin los PR que la API mezcla."""
    return [
        {
            "number": i["number"],
            "title": i.get("title", ""),
            "labels": [{"name": lb["name"]} for lb in i.get("labels", [])],
            "createdAt": i.get("created_at", ""),
        }
        for i in raw
        if "pull_request" not in i
    ]


def render_state_body(state: dict) -> str:
    return (
        "Lo escribe `/mejora` (`skills/mejora/scripts/pick.py`). No lo edites a mano: es la rotación"
        " de auditorías y el último paso del PC, que leen a la vez el PC y la tarea en la nube.\n\n"
        "```json\n" + json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n```\n"
    )


def parse_state_body(body: str) -> dict:
    m = re.search(r"```json\s*\n(.*?)\n```", body or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def read_shared(state_repo: str) -> tuple[int | None, dict | None]:
    """El issue de estado y su contenido. (None, {}) si no existe; (None, None) si no se pudo leer."""
    raw = gh_json(["api", f"repos/{state_repo}/issues?labels={STATE_LABEL}&state=open&per_page=5"])
    if raw is None:
        return None, None
    issues = [i for i in raw if "pull_request" not in i]
    if not issues:
        return None, {}
    first = min(issues, key=lambda i: i["number"])
    return first["number"], parse_state_body(first.get("body") or "")


def write_shared(state_repo: str, number: int | None, state: dict) -> bool:
    body = render_state_body(state)
    if number is None:
        cmd = ["gh", "api", "--silent", f"repos/{state_repo}/issues", "-f", f"title={STATE_TITLE}"]
        cmd += ["-f", f"body={body}", "-f", f"labels[]={STATE_LABEL}"]
    else:
        cmd = [
            "gh",
            "api",
            "--silent",
            "-X",
            "PATCH",
            f"repos/{state_repo}/issues/{number}",
            "-f",
            f"body={body}",
        ]
    return run(cmd, timeout=TIMEOUT_GH) is not None


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


def merge_issue_lists(*lists: list[dict]) -> list[dict]:
    """Une las listas de cada etiqueta sin repetir el issue que lleva las dos."""
    seen: dict[int, dict] = {}
    for lst in lists:
        for issue in lst:
            seen.setdefault(issue["number"], issue)
    return [seen[n] for n in sorted(seen)]


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
            mode = "draft" if LABEL_REVIEW in labels else "listo"
            candidates.append(
                Candidate(repo, n, issue["title"], severity_of(labels), issue.get("createdAt", ""), mode)
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


def cmd_audit(repos: list[Repo], audited: dict[str, str]) -> None:
    name = pick_audit([r.name for r in repos], audited)
    if name is None:
        print("Sin repos candidatos (ninguno con .claude/verify-command, o ninguno le toca a este sitio).")
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
        # `--label` repetido es Y, no O: una consulta por etiqueta.
        by_label = [
            gh_json(["api", f"repos/{r.slug}/issues?state=open&labels={label}&per_page=50"])
            for label in (LABEL_AUTONOMOUS, LABEL_REVIEW)
        ]
        p = gh_json(["api", f"repos/{r.slug}/pulls?state=open&per_page=100"])
        if any(i is None for i in by_label) or p is None:
            unavailable.append(r.name)
            continue
        issues[r.name] = merge_issue_lists(*(parse_rest_issues(i) for i in by_label))
        prs[r.name] = [{"headRefName": x.get("head", {}).get("ref", "")} for x in p]
    candidates, skipped = pick_fix(issues, prs, max_drafts)
    by_name = {r.name: r for r in repos}
    if candidates:
        top = candidates[0]
        print(f"REPO: {top.repo}")
        print(f"RUTA: {by_name[top.repo].path.as_posix()}")
        print(f"GITHUB: {by_name[top.repo].slug}")
        print(f"ISSUE: #{top.number} [{top.severity}] {top.title}")
        print(f"RAMA: {BRANCH_PREFIX}{top.number}-<descripción-corta>")
        print(f"PR: {top.pr_mode}")
    else:
        print(
            "NADA QUE ARREGLAR: no hay issues audit-autonomo ni audit-revision abiertos que se puedan coger."
        )
    if len(candidates) > 1:
        print("SIGUIENTES:")
        for c in candidates[1:6]:
            print(f"  {c.repo} #{c.number} [{c.severity}] ({c.pr_mode}) {c.title}")
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
    parser.add_argument("--donde", choices=["pc", "nube"], default="pc")
    parser.add_argument(
        "--state-repo", default=os.environ.get("MEJORA_STATE_REPO", ""), help="owner/claude-code-config"
    )
    parser.add_argument("--sin-github", action="store_true", help="estado solo en el fichero local (tests)")
    args = parser.parse_args()
    state_path = Path(args.state)
    state = load_state(state_path)

    root = Path(args.root).resolve()
    only = [x.strip() for x in args.repos.split(",") if x.strip()]
    repos = find_repos(root, only) if root.is_dir() else []
    state_repo = "" if args.sin_github else args.state_repo
    if not state_repo and not args.sin_github and repos:
        state_repo = f"{repos[0].slug.split('/')[0]}/{STATE_REPO_NAME}"

    # Lo de GitHub manda sobre el fichero local: es lo que ven a la vez el PC y la nube.
    number, shared = read_shared(state_repo) if state_repo else (None, None)
    readable = shared is not None
    shared = dict(shared or {})
    audited = dict(state.get("audited", {}))
    audited.update(shared.get("audited", {}))

    if args.mode == "marcar":
        if not args.repo:
            print("marcar necesita el nombre del repo")
            return 0
        audited[args.repo] = dt.date.today().isoformat()
        state["audited"] = audited
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        shared["audited"] = audited
        ok = bool(state_repo) and readable and write_shared(state_repo, number, shared)
        print(f"Apuntado: {args.repo} auditado el {audited[args.repo]}" + ("" if ok else " (solo en local)"))
        return 0

    if not root.is_dir():
        print(f"No existe la carpeta de repos: {root}")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    heartbeat = shared.get("latido_pc")
    if args.donde == "pc" and state_repo and readable:
        # Sin leer antes no se escribe: un PATCH a ciegas borraría la rotación de la nube.
        write_shared(state_repo, number, {**shared, "latido_pc": now.isoformat(timespec="seconds")})
    names = repos_for_place([r.name for r in repos], load_policy(), args.donde, heartbeat, now)
    print(f"DÓNDE: {args.donde} (último paso del PC: {heartbeat or 'desconocido'})")
    repos = [r for r in repos if r.name in names]
    if args.mode == "auditar":
        cmd_audit(repos, audited)
    else:
        cmd_fix(repos, args.max_drafts)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - es la salida de una skill: nunca abortar la skill entera
        print(f"pick.py falló: {exc!r}")
        sys.exit(0)
