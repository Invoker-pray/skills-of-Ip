#!/usr/bin/env python3
"""Small dependency-free coordinator for repository-scoped AI work."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(*args: str, check: bool = True) -> str:
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False)
    if check and p.returncode:
        raise SystemExit(f"command failed: {' '.join(args)}\n{p.stderr.strip()}")
    return p.stdout.strip()


def root() -> Path:
    return Path(run("git", "rev-parse", "--show-toplevel"))


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dirs(repo: Path) -> tuple[Path, Path]:
    base = repo / ".projsync"
    claims = base / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    return base, claims


def load_claims(repo: Path) -> list[tuple[Path, dict]]:
    _, d = dirs(repo)
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as e:
            raise SystemExit(f"invalid claim {p}: {e}")
    return out


def tracked_dirty() -> list[str]:
    # Do not use run(): its strip() would remove the leading status column
    # and turn `` M path`` into ``M path``.
    p = subprocess.run(("git", "status", "--porcelain"), text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=False)
    if p.returncode:
        raise SystemExit(p.stderr.strip())
    raw = p.stdout
    return [line[3:] for line in raw.splitlines()
            if len(line) >= 3 and line[:2] != "??"]


def branch_state() -> tuple[str, str, str]:
    branch = run("git", "branch", "--show-current")
    remote = run("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                 "@{u}", check=False)
    head = run("git", "rev-parse", "HEAD")
    return branch, remote, head


def overlap(a: str, b: str) -> bool:
    a = a.rstrip("/") or "."
    b = b.rstrip("/") or "."
    return a == b or a == "." or b == "." or a.startswith(b + "/") or b.startswith(a + "/")


def cmd_status(args: argparse.Namespace) -> None:
    repo = root()
    branch, upstream, head = branch_state()
    print(f"repo={repo}\nbranch={branch}\nhead={head}")
    if upstream:
        counts = run("git", "rev-list", "--left-right", "--count",
                     f"HEAD...{upstream}", check=False)
        print(f"upstream={upstream}\ndivergence={counts or 'unknown'}")
    dirty = tracked_dirty()
    untracked = [line[3:] for line in run("git", "status", "--porcelain").splitlines()
                 if line.startswith("?? ")]
    print("tracked_dirty=" + (", ".join(dirty) if dirty else "none"))
    print("untracked=" + (", ".join(untracked) if untracked else "none"))
    claims = load_claims(repo)
    active = [(p, c) for p, c in claims if c.get("status") == "active"]
    print(f"claims={len(claims)} active={len(active)}")
    for p, c in active:
        print(f"  ACTIVE {c.get('id')} owner={c.get('owner')} scope={','.join(c.get('scope', []))} file={p}")


def cmd_sync(args: argparse.Namespace) -> None:
    """Fetch the shared remote, then print the complete synchronization state."""
    run("git", "fetch", "--prune", "origin")
    cmd_status(args)


def owner() -> str:
    return (os.environ.get("PROJSYNC_OWNER") or
            run("git", "config", "user.name", check=False) or "unknown-agent")


def cmd_start(args: argparse.Namespace) -> None:
    repo = root()
    if not args.id or "/" in args.id or ".." in args.id:
        raise SystemExit("--id must be a unique simple path-safe identifier")
    dirty = tracked_dirty()
    if dirty:
        raise SystemExit("tracked worktree is dirty; synchronize or checkpoint it first: " + ", ".join(dirty))
    branch, upstream, head = branch_state()
    if not upstream:
        raise SystemExit("current branch has no upstream; configure the shared base branch first")
    counts = run("git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    behind, ahead = [int(x) for x in counts.split()]
    if behind or ahead:
        raise SystemExit(f"branch is not synchronized with {upstream}: behind={behind} ahead={ahead}")
    scope = sorted({x.strip().rstrip("/") for x in args.scope.split(",") if x.strip()})
    if not scope:
        raise SystemExit("--scope must contain at least one repository-relative path")
    for _, claim in load_claims(repo):
        if claim.get("status") != "active":
            continue
        for requested in scope:
            if any(overlap(requested, held) for held in claim.get("scope", [])):
                raise SystemExit(f"scope conflict with active claim {claim.get('id')}: {requested}")
    _, claim_dir = dirs(repo)
    path = claim_dir / f"{args.id}.json"
    if path.exists():
        raise SystemExit(f"claim already exists: {path}")
    data = {"schema": 1, "id": args.id, "owner": args.owner or owner(),
            "task": args.task, "scope": scope, "base_sha": head,
            "branch": branch, "status": "active", "created_at": now(),
            "updated_at": now(), "review_rounds": 0,
            "resources": sorted(set(args.resource or [])), "checkpoints": []}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"created {path}\nbase_sha={head}\nNext: update handle.md, commit this claim, then begin edits.")


def get_claim(repo: Path, ident: str) -> tuple[Path, dict]:
    path = dirs(repo)[1] / f"{ident}.json"
    if not path.exists():
        raise SystemExit(f"claim not found: {ident}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def save_claim(path: Path, data: dict) -> None:
    data["updated_at"] = now()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_checkpoint(args: argparse.Namespace) -> None:
    path, data = get_claim(root(), args.id)
    if data.get("status") != "active":
        raise SystemExit(f"claim {args.id} is {data.get('status')}, not active")
    if not args.evidence:
        raise SystemExit("--evidence is required")
    data.setdefault("checkpoints", []).append({"at": now(), "evidence": args.evidence})
    if args.review_round is not None:
        data["review_rounds"] = int(args.review_round)
    save_claim(path, data)
    print(f"checkpoint recorded for {args.id}")


def cmd_finish(args: argparse.Namespace) -> None:
    path, data = get_claim(root(), args.id)
    if data.get("status") != "active":
        raise SystemExit(f"claim {args.id} is {data.get('status')}, not active")
    if not data.get("checkpoints"):
        raise SystemExit("finish requires at least one checkpoint")
    if not args.result:
        raise SystemExit("--result is required")
    data["status"] = "done"
    data["result"] = args.result
    data["finished_at"] = now()
    save_claim(path, data)
    print(f"finished {args.id}; commit the claim transition with code and handle updates")


def cmd_abort(args: argparse.Namespace) -> None:
    path, data = get_claim(root(), args.id)
    if not args.reason:
        raise SystemExit("--reason is required")
    data["status"] = "aborted"
    data["reason"] = args.reason
    data["finished_at"] = now()
    save_claim(path, data)
    print(f"aborted {args.id}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    sub.add_parser("status")
    p = sub.add_parser("start"); p.add_argument("--id", required=True); p.add_argument("--scope", required=True); p.add_argument("--task", required=True); p.add_argument("--owner"); p.add_argument("--resource", action="append", help="exclusive resource reservation (repeatable)")
    p = sub.add_parser("checkpoint"); p.add_argument("--id", required=True); p.add_argument("--evidence", required=True); p.add_argument("--review-round", type=int)
    p = sub.add_parser("finish"); p.add_argument("--id", required=True); p.add_argument("--result", required=True)
    p = sub.add_parser("abort"); p.add_argument("--id", required=True); p.add_argument("--reason", required=True)
    args = ap.parse_args()
    {"sync": cmd_sync, "status": cmd_status, "start": cmd_start, "checkpoint": cmd_checkpoint,
     "finish": cmd_finish, "abort": cmd_abort}[args.command](args)


if __name__ == "__main__":
    main()
