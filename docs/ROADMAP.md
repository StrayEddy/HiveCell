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

Nothing. Both former "Now" items are done — and the second of them says what should
replace them.

**What the [#2](https://github.com/StrayEddy/HiveCell/issues/2) fault trees recommend
promoting** (a recommendation, not a re-prioritisation — the call is yours):

- **[#9](https://github.com/StrayEddy/HiveCell/issues/9) seal drag** — gap **G1**. The
  FTA showed it is not an isolated unknown: a high drag defeats the SF4 return element
  *and* raises the force SF2 must bound, so it weakens TE-2 and TE-3 **together**. The
  order-6 cut set protecting against a sustained pin is optimistic under exactly this
  condition. It is already the roadmap's named critical path, below.
- ~~**[#8](https://github.com/StrayEddy/HiveCell/issues/8) SF2 force limit**~~ — the
  injury-data half is done, see below. What remains is hardware: the drive's real
  force-limitability under a jam.

Everything that could be verified from a desk about the *logic* now has been. What is
left in the safety case is physics, and it is the physics that is unmeasured — mostly.

**Done (desk half):** [#8](https://github.com/StrayEddy/HiveCell/issues/8) SF2 real
force limit — [`force_limit_injury_data.md`](force_limit_injury_data.md) +
**ADR-0024**. `SAFE_CONTACT_N` moved 120 N → 100 N, sourced from FMVSS 118 (child-finger
pinch, 100 N) and ISO/TS 15066's abdomen pain-onset limit (110 N) — replacing an uncited
"~150 N powered-door limit" comparison that turned out to be wrong (the real door
standard caps at 67 N). Closes the FTA's **B7** branch on the desk side; the hardware
half — can the real drive actually *hold* the cap under a jam — stays open, folded into
gap **G2** below.

**Done:** [#2](https://github.com/StrayEddy/HiveCell/issues/2) safety requirements +
traceability matrix + FTA — [`TRACEABILITY.md`](TRACEABILITY.md). 21 numbered
requirements (SR-001…021), every hazard resolved to ≥1 requirement and ≥1 test, three
qualitative fault trees with minimal cut sets, and an 11-row gap register. It also
caught a stale figure: `SAFETY.md` still quoted the pre-SF4 design force (2411 N) when
`actuator_sizing.py` had moved to 5546 N.

**Done:** [#1](https://github.com/StrayEddy/HiveCell/issues/1) formal verification of
the interlock invariants — TLA+ model in [`../spec/`](../spec/README.md), gated on
every push. Proves the headline claim (and SF4's pin relief) over all reachable
states, with a mutation suite so the green result means something. It paid for itself
immediately: finding **F-1**, a real latency defect in `CLEARED_HOLD` that review and
scenario testing had both missed, now fixed under **ADR-0022**.

It also closed a gap it had itself exposed: `safety_interlock.gd` had no E-stop and no
notion of power, so the spec's SF4 claims were verified against *intent*. Modelling them
forced the unanswered question of what the E-stop actually does — now **ADR-0023**
(Category 0, into the fail-open path) — and the twin implements it, so every claim in
the spec is checked against shipped code.

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
| [#8](https://github.com/StrayEddy/HiveCell/issues/8) | SF2 drive force-limitability under a real jam (injury-data half done, ADR-0024) | safety | real drive characterization |
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
