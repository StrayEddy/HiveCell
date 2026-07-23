# Contributing to HiveCell

Thanks for your interest. HiveCell is an open-source hardware project aiming at
safe, reusable public sleeping infrastructure, and it moves forward fastest with
more hands and more scrutiny — especially on the safety side.

## Before anything else: read the safety context

This project designs a machine that moves a heavy powered piston through a space a
person occupies. Safety is the first design constraint, not a feature. Please read
[`docs/SAFETY.md`](docs/SAFETY.md) and the decision log
[`docs/DECISIONS.md`](docs/DECISIONS.md) before proposing changes. The core
invariant — **the clearing sweep never advances while life is detected** — is
non-negotiable and is enforced by a headless self-test.

This is **uncertified research**. Nothing here is validated hardware. Do not
represent it as safe to deploy, and see the safety notice in [`LICENSE`](LICENSE).

## Ways to help (most useful first)

- **Physical de-risking.** The single biggest unknown is **seal drag** (SF3), which
  is currently estimated across a ~40× range and drives the whole force chain. A
  bench measurement on a real seal sample is the highest-value contribution anyone
  can make right now (see ADR-0011 in `docs/DECISIONS.md`).
- **Safety review.** Independent eyes on the FMEA and the safety functions.
- **SF1 sensing.** Prototyping the diverse-redundant occupancy suite (radar vitals,
  thermal, CO₂, load/BCG — ADR-0012).
- **Simulation / twin.** Improvements to the Godot digital twin and its self-tests.
- **CAD / mechanism.** Parametric FreeCAD work (the CAD is the source of truth — see
  ADR-0002).

## How the project is organized

- Decisions are recorded as ADRs in `docs/DECISIONS.md`. **If you change a design
  choice, add or amend an ADR** explaining why.
- The FreeCAD model is code-first and parametric (`scripts/`, ADR-0002).
- The safety interlock is a headless-testable state machine; run the self-tests with
  `./scripts/run_selftest.sh` and enable the pre-push hook with
  `git config core.hooksPath .githooks`.

## Workflow

1. Open an issue describing the problem or idea before large changes, so we can agree
   on direction (and check it doesn't weaken a safety function).
2. Keep pull requests focused; explain the reasoning, not just the change.
3. Make sure the self-tests pass.

## Licensing of contributions

By contributing you agree that your contributions are licensed under the project's
licenses (see [`LICENSE`](LICENSE)): `CERN-OHL-S-2.0` for hardware, `CC-BY-4.0` for
documentation, and `Apache-2.0` for software. Under the Apache-2.0 terms this
includes a patent grant for any code you contribute.
