---
name: hivecell-safety-review
description: Use before merging or pushing any change that touches HiveCell's safety-critical logic or docs — godot/safety_interlock.gd, spec/HiveCellInterlock.tla, occupancy/force-limit logic, or docs/SAFETY.md / docs/TRACEABILITY.md — or when asked to review/audit such a change for safety-gate readiness.
---

# hivecell-safety-review

## Overview
HiveCell's safety interlock is enforced by a headless self-test and a TLA+
model check, both gated in CI (`.github/workflows/safety.yml`, "safety gate")
and locally by the `.githooks/pre-push` hook
(`git config core.hooksPath .githooks`). This skill is the pre-merge
checklist for verifying a change hasn't weakened that gate. It assumes the
change was *made* following `hivecell-design-change` (ADR -> CAD -> twin ->
safety docs) — this skill only covers verifying it before merge.

## When to use
Before merging/pushing a change to: `godot/safety_interlock.gd` or other
twin logic implementing SF1-SF5, `spec/HiveCellInterlock.tla` or its `.cfg`
files, force/occupancy parameters (`SAFE_CONTACT_N`, sensor voting, etc.), or
`docs/SAFETY.md` / `docs/TRACEABILITY.md`. Also use when asked to audit a PR
or diff for safety-gate readiness.

## Procedure
1. **Run the full self-test locally**: `./scripts/run_selftest.sh`. It runs
   the Godot headless tests under `godot/tests/*.gd` and then the TLA+ model
   check (`scripts/run_modelcheck.sh`), unless
   `HIVECELL_SKIP_MODELCHECK=1` is set — do not merge on a run that skipped
   the model check for convenience; that only bypasses the gate that CI
   itself does not skip. If the model check skips locally for lack of a JRE,
   let CI's `safety gate / formal verification` job be the real check.
2. **Confirm the TLA+ spec still holds** (`spec/HiveCellInterlock.tla`,
   checked against `spec/Safety.cfg`, `spec/Liveness.cfg`,
   `spec/Blackout.cfg`). If you changed interlock behavior, the model
   (`spec/HiveCellInterlock.tla`) must be updated to match the GDScript —
   it's hand-written and can drift (see `docs/TRACEABILITY.md` gap G11).
   Also run `./scripts/run_modelcheck.sh --mutants` to confirm injected
   defects are still caught (a spec that can't fail proves nothing).
3. **Check `docs/TRACEABILITY.md` is current**: does every changed/added
   safety behavior have an SR requirement (§2), a traceability-matrix row
   (§3) citing real evidence (a V-MC property, a V-ST scenario name, a V-AN
   script), and — if the change closes or opens a gap — an updated §6 gap
   register entry? A change that alters behavior without a matching §3 row
   is a traceability break, not just a doc-lag issue.
4. **Check `docs/SAFETY.md` is current**: hazard register, safety-function
   status tags (`[sim]`/`[todo]`), FMEA rows, and "Open items" should reflect
   the change. Confirm the invariant framing still holds: *the clearing sweep
   never advances while life is detected*, and SF2's contact reaction remains
   independent of SF1.
5. **Confirm the ADR trail exists** — per `hivecell-design-change`, a
   behavior change should cite an ADR in `docs/DECISIONS.md`; if reviewing
   someone else's change and no ADR is referenced, send it back rather than
   approving it.
6. **CI must be green on the `safety gate` workflow** (jobs `model-check` and
   `twin-tests`) before merge — this is enforced on every push and PR,
   including forks, and cannot be skipped the way the local hook's model
   check can.

## Common mistakes
- Treating a green local `run_selftest.sh` as sufficient when it silently
  skipped the model check (no JRE) — always confirm CI's `model-check` job
  ran and passed too.
- Updating `godot/safety_interlock.gd` without updating
  `spec/HiveCellInterlock.tla` to match — the model then verifies a machine
  that no longer exists (gap G11 in `docs/TRACEABILITY.md`).
- Treating "VERIFIED (sim)" in `docs/TRACEABILITY.md` as a hardware safety
  claim — it means the logic is exhaustively checked, not that real sensors,
  seals, or springs behave as modeled. Don't let a doc update overstate this.
- Merging a safety-relevant change with no corresponding ADR — the decision
  log is expected to explain *why* before the *what* lands.
- Forgetting `./scripts/run_modelcheck.sh --mutants` — a model check that
  never fails on injected defects isn't evidence of anything.
