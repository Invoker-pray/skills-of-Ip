---
name: projsync
description: Start and enforce a repository's multi-agent synchronization workflow when the user invokes /projsync. It coordinates remote state, scoped claims, handle.md handoffs, configurable verification gates, bounded AI review, and safe commit or push.
metadata:
  short-description: Coordinate multi-agent repository work
---

# Project synchronization

Use this skill when the user explicitly invokes `/projsync` or asks to start the project synchronization mechanism. It is the coordination layer for human and AI contributors; domain skills provide the actual build, simulation, or deployment commands.

The repository has two synchronized layers:

- `docs/handle.md` is the human-readable source of truth. Read it before editing. Update current status, design decisions, verification evidence, known risks, ownership, and the next step before committing or pushing.
- `.projsync/` is the machine-readable layer. Claims reserve file scope and checkpoints preserve commands, results, and handoff state. Keep it in the repository when the team needs shared coordination; do not treat a chat transcript as state.

Read [references/protocol.md](references/protocol.md) for schemas, state transitions, risk tiers, review limits, resource locks, and verification adapters. Use the helper instead of hand-editing claim JSON:

```bash
python3 .codex/skills/projsync/scripts/projsync.py sync
python3 .codex/skills/projsync/scripts/projsync.py status
python3 .codex/skills/projsync/scripts/projsync.py start --id <work-id> --scope path/a.py,path/b.md --task "short objective"
python3 .codex/skills/projsync/scripts/projsync.py checkpoint --id <work-id> --evidence "pytest: 12 passed"
python3 .codex/skills/projsync/scripts/projsync.py finish --id <work-id> --result "implemented and verified"
```

At session start:

1. Locate the repository root and fetch the shared remote base (`sync` or equivalent). Read every relevant handoff file, recent commits, and current claims.
2. Stop if the branch diverges from its upstream, a tracked dirty change is not yours, or the requested scope overlaps an active claim. Preserve unrelated work; never reset or force-push it.
3. Create and publish a claim before editing. It records owner, objective, exact scope, base commit, branch, and initial handoff. Include `docs/handle.md` whenever the task changes project behavior or evidence.
4. Declare shared resource use (board, license, deployment slot, or other exclusive service) in the claim or handle before starting it. A script lock does not replace a human-visible reservation.

While working:

- Stay inside the claimed scope. Expand it only by updating the claim and `handle.md`, synchronizing, and recording why.
- Make small reversible commits. Record both successful and failed checks as checkpoints; a failed command is evidence, not something to erase.
- Select verification gates from the project's adapter/profile. Hardware projects may attach Python golden, lint, simulator, bit-exact matrix, synthesis/timing, and board evidence; software projects may attach unit, integration, packaging, and deployment checks. Do not claim a gate passed without a command and durable artifact or output.
- Use a fresh-context review for source, tests, tooling, packaging, coordination, CI, scoring, authentication, and release changes. Classify findings as introduced, pre-existing, intentional, or false-positive. Review no more than three rounds unless a human explicitly expands the investigation.
- For high-blast-radius changes, name the human owner and write a rollback command or commit in the handoff before landing.

Before commit or push:

1. Run the relevant verification profile and record exact commands, results, and artifact paths with `checkpoint`.
2. Update `docs/handle.md`: current baseline and worktree, changed behavior, commit log entry, verification evidence, limitations, active reservations, and the next optimization or action. External results remain `[待补充]` until verified.
3. Finish the claim only after review findings are resolved or explicitly classified. Commit code, handle, claim transition, and required evidence together when the repository tracks them.
4. Inspect `git diff --check`, staged paths, branch divergence, and rollback instructions. Push only with the user's authorization; the helper never pushes automatically.
5. After push, run `status` again and report the commit, remote state, checks, known risks, and next safe action. Never add an AI co-author.

When a task is abandoned, use `abort` with a reason and leave enough checkpoint evidence for another member to resume. Feed confirmed incidents and repeated review findings back into `handle.md`, a project pitfalls file, or the selected verification adapter.
