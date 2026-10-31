# Projsync protocol

## Purpose and source of truth

AI multiplies edits and review attempts, so synchronization is a state problem. Every contributor must see the same base commit, claimed scope, current handoff, verification evidence, known risks, and resource reservations. `docs/handle.md` is the narrative source of truth; `.projsync/claims/` is the auditable ownership and evidence layer. If they disagree, stop and reconcile them before editing.

The protocol applies the layered review principles described in [Addy Osmani's summary of the Claude Code review process](https://x.com/addyosmani/status/2114604912520921136): executable evidence beats an agent's assertion, review with fresh context, classify findings, scale human ownership with blast radius, bound review loops, maintain rollback, and turn incidents into checks.

## Repository bootstrap and handoff

A project using `/projsync` should have a human-readable `docs/handle.md` (or a path named by the project). If `docs/project-overrides.md` exists, read it before applying defaults. Explicit entries override only the corresponding default rules; unspecified rules remain unchanged. The file cannot bypass explicit user instructions, credential protection, protection of others' uncommitted work, or explicit push authorization. At the beginning of each session, first check whether the upstream has new commits, then read the handle, repository memory, relevant pitfalls, and recent commits. Record the current branch, `HEAD` commit, upstream divergence, and worktree state in the initial projsync status or checkpoint before editing. Keep these sections current:

- current baseline: branch, commit/tag, worktree state, and known divergence;
- project state and design decisions, including rejected approaches;
- active members, claims, and exclusive resources;
- chronological commit log with author, date, hash, behavior, verification, and release/board status;
- known risks, pitfalls, and limitations;
- next actions ordered by expected value, with quantitative evidence and prerequisites;
- exact handoff commands and result paths.

The handle is updated before every commit or push and immediately after a meaningful interruption. Do not store secrets in it. Keep non-reproducible evidence in versioned, uniquely named archives; keep generated build output out of documentation unless the project explicitly tracks it.

## Claims and scope

The helper creates `.projsync/claims/<id>.json`:

```json
{
  "schema": 1,
  "id": "20261031-router-fix",
  "owner": "agent-or-person",
  "task": "short objective",
  "scope": ["src/router", "docs/handle.md"],
  "base_sha": "commit used to start",
  "branch": "develop",
  "status": "active",
  "created_at": "UTC ISO-8601",
  "updated_at": "UTC ISO-8601",
  "review_rounds": 0,
  "resources": [],
  "checkpoints": [
    {"at": "UTC ISO-8601", "evidence": "command => result"}
  ]
}
```

Statuses are `active`, `blocked`, `done`, and `aborted`; completed claims remain as a short audit trail. Do not reuse an id. A directory claims all descendants. Coordination files are part of the scope whenever they change. Two active claims overlap when either path is equal, is an ancestor of the other, or is the repository root. Claims do not grant permission to edit outside the repository or to push.

`start` requires a clean tracked worktree, an upstream branch with zero ahead/behind divergence, a unique id, and no overlapping active claim. Before editing, create a local synchronization commit containing the reservation and handle update so the state is saved; this commit is not a push. If a claim becomes stale, do not silently take it over: record an abort or human-approved reassignment in the handle.

## State transitions and evidence

- `sync`: fetch and inspect remote state before reading or changing code.
- `start`: reserve scope and record the base SHA.
- `checkpoint`: append an observable command/result, failure, artifact, resource change, or handoff note. Never replace a failed checkpoint with a success claim.
- `finish`: require at least one verification checkpoint, a final result, and a clean review decision; mark the claim done.
- `abort`: mark intentionally abandoned work and explain what remains safe to reuse.

A checkpoint should include the command, exit/result text, input revision, and durable output path when one exists. For external evaluation or board tests, record the evaluator version and leave `[待补充]` until the result is actually received. Board, license, and deployment resources must be declared before use; parallel experiments use isolated worktrees. Credentials and API keys never enter files, logs, or Git. Copy long-lived evidence out of `/tmp`, and never reset or overwrite another member's uncommitted work.

## Verification profiles and adapters

`projsync` does not hard-code a language or hardware toolchain. Each repository declares a profile in `handle.md` or a project reference. A profile names required gates, pass criteria, evidence locations, and the owner who may waive a gate. Typical adapters include:

- HDL/FPGA: golden model, lint warning diff, simulator regression, full bit-exact case matrix, synthesis/timing/DRC, and board evidence;
- software: unit, integration, static analysis, packaging, and deployment smoke checks;
- data/ML: deterministic fixtures, metric thresholds, reproducibility, and artifact hashes.

Run cheap local checks first, then integration and deployment checks in order. Keep A/B experiments single-variable and use isolated worktrees for ablations or candidate comparisons. Never present mock, simulation, hardware, and external evaluation as one result or one metric.

## Review, risk, and ownership

| Risk | Examples | Required gate |
|---|---|---|
| Low | prose, comments, isolated reports | syntax/format check and one fresh-context diff review |
| Medium | source, tests, tools, data formats | targeted tests, integration check, fresh-context review, handle update |
| High | routing, Docker, CI, scoring, auth, release, coordination files, shared-resource changes | targeted and end-to-end checks, independent review, explicit human owner, rollback instruction |

Review rounds are bounded at three. After three rounds, review only the new diff unless a human authorizes more. Findings are `introduced`, `pre-existing`, `intentional`, or `false-positive`; blocking findings require a fix or a recorded reason. The contributor who lands a change owns its rollback and incident follow-up.

## Branch and release conventions

By default, `develop` contains all development material, including source, simulation, testbench, and test scripts. `master` contains only the final signed-off, board-ready and exportable result. Projects may customize the names in `handle.md`, but must preserve the distinction between a rigorous development branch and a clean release branch. The selected policy must state gates before merging or tagging, whether generated artifacts are ignored, and how a release is rolled back. Never force-push a shared branch. Rebase or merge the latest remote base before push, then re-run affected gates.

Keep local persistence and remote publication separate: `git commit` is an ordinary local save point and must not imply `git push`. A push requires an explicit user request. Immediately before a requested push, fetch the upstream, verify the branch and divergence, update the handle with the final commit and remote target, and commit that update before pushing. If the handle update changes the commit hash, use the newest hash as the push target. Record the post-push remote state in a checkpoint or handle entry.

For hardware or other artifact-producing projects, use a two-stage evidence record when useful: land verified source with a pending deployment status, then append the external result and release status in a separate handle/record update. This is a synchronization pattern; the domain skill supplies the actual build and deployment commands.

## Handoff checklist

Every handoff answers:

1. What changed and why?
2. Which files, claims, and exclusive resources are active?
3. Which exact commands passed, failed, or were not run?
4. What is uncertain, externally blocked, or unsafe to assume?
5. What is the next safe action and rollback point?

Use a small explainer or diagram for an unfamiliar module when that reduces repeated context loading. Feed confirmed incidents into a pitfalls record and, when repeatable, into a verification adapter or script.
