# HiveCell — Roadmap

Curated, prioritized view of the work. The **live state** (status, discussion,
who's on what) lives in [GitHub Issues](https://github.com/StrayEddy/HiveCell/issues);
this file is the versioned narrative that indexes them. One source of truth per
item: the issue.

Guiding thesis: at this stage the highest-value work is **reducing uncertainty**,
not more CAD. The concept is plausible; the open question is whether the control
logic and the force budget can be made trustworthy. See
[`SAFETY.md`](SAFETY.md) and [`DECISIONS.md`](DECISIONS.md).

## Now (high priority)

| # | Item | Area | Why |
|---|------|------|-----|
| [#1](https://github.com/StrayEddy/HiveCell/issues/1) | Formal verification of the interlock invariant (model checking) | sim | Prove the headline safety claim over *all* reachable states, not just hand-written scenarios. Biggest assurance jump per hour — the FSM is already small and pure. |
| [#2](https://github.com/StrayEddy/HiveCell/issues/2) | Safety requirements + traceability/verification matrix + FTA | safety | Link existing hazards/FMEA/tests into an auditable Hazard→Requirement→Design→Test→Result chain — the artifact a reviewer actually asks for. |

## Next (medium priority)

| # | Item | Area | Why |
|---|------|------|-----|
| [#3](https://github.com/StrayEddy/HiveCell/issues/3) | Randomized fault-injection on interlock timing | sim | Stress the timing/continuous layer the pure FSM abstracts away (dropouts, races, stall, power-loss position). Complements #1. |
| [#4](https://github.com/StrayEddy/HiveCell/issues/4) | Occupancy sensing tradeoff review (sensor table + fusion rationale) | sensing | Document *why* the ADR-0012 diverse suite is right. Architecture is decided; the justifying review is the gap. |
| [#5](https://github.com/StrayEddy/HiveCell/issues/5) | First-order reliability models (no hardware required) | reliability | Spring fatigue, cycle life, tolerance stack, ingress. Builds design rationale from the desk. |
| [#6](https://github.com/StrayEddy/HiveCell/issues/6) | Serviceability / manufacturability pass on the CAD | cad | Optimize, don't add: part count, single-side access, seal-swap time. |

## Critical-path experiment (not desk work)

The master uncertainty is **seal drag** — it couples SF3 ↔ SF4 ↔ actuator and is
currently a ~40× estimate (~16–700 N/m). No desk model retires it; it needs the
~$200 bench measurement in [`seal_drag_bench_test.md`](seal_drag_bench_test.md)
(ADR-0011), tracked as [#9](https://github.com/StrayEddy/HiveCell/issues/9). Keep it
visible so the paperwork above never quietly defers it. It is also the best first
hardware contribution — see [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Physical validation & certification (hardware / context gated)

The [`SAFETY.md`](SAFETY.md) **Open items** — the work that must happen before any
real hardware, mostly blocked on a prototype, an install context, or lab data. Not
desk work, so held apart from the desk-work backlog above; #9 is the exception that
gates several of these and sits on the critical path.

| # | Item | Area | Gate |
|---|------|------|------|
| [#9](https://github.com/StrayEddy/HiveCell/issues/9) | Measure seal drag on a real sample (ADR-0011) — **critical path** | cad | ~$200 bench sample; retires the master variable and feeds #11 |
| [#7](https://github.com/StrayEddy/HiveCell/issues/7) | SF1 real-sensing validation + ISO 13849 PL e dossier (ADR-0012) | sensing | sensor hardware; radar-through-bedding + small-animal tests |
| [#8](https://github.com/StrayEddy/HiveCell/issues/8) | SF2 real force limit from injury data + drive force-limitability | safety | injury data (desk) + real drive characterization |
| [#11](https://github.com/StrayEddy/HiveCell/issues/11) | SF4 return element + back-drive verification + actuator re-run (ADR-0009) | cad | desk re-run now; back-drive check needs hardware; coupled to #9 |
| [#10](https://github.com/StrayEddy/HiveCell/issues/10) | H4 siting sign-off vs local code + commissioning check (ADR-0013) | safety | real install context, local code, named sign-off |

## Explicitly deprioritized

Cheap to change later, so not worth effort now: photorealistic renders, marketing
video, interior aesthetics/comfort, colour schemes. Keep one good hero render;
stop iterating on lighting detail.

## Conventions

- Every roadmap item is a GitHub Issue labelled `roadmap` + an `area:*` + a `priority:*`.
- A decision that changes the design gets an ADR in [`DECISIONS.md`](DECISIONS.md).
- A change to a safety function or hazard updates [`SAFETY.md`](SAFETY.md).
