# HiveCell — Safety requirements, traceability & fault trees

Roadmap [#2](https://github.com/StrayEddy/HiveCell/issues/2). The auditable chain a
safety reviewer asks for: **Hazard → Requirement → Design → Verification → Result**.

The hazards (H1–H8), FMEA (F1–F7) and safety functions (SF1–SF5) live in
[`SAFETY.md`](SAFETY.md); the decisions behind them in [`DECISIONS.md`](DECISIONS.md).
This document adds the layer that was missing — numbered requirements, what discharges
each one, and what is *not* discharged.

**Status of this document.** Desk analysis of a design with no built hardware. Nothing
here is a certification, a performance-level claim, or a substitute for testing. Its
value is that every claim points at a re-runnable command or an explicitly named gap.

---

## 1. How to read it

Verification methods, in descending order of strength:

| Code | Method | What it establishes |
|------|--------|---------------------|
| **V-MC** | Model checking (TLA+/TLC) | the property holds in **every reachable state** of the logic |
| **V-ST** | Twin self-test | the behaviour holds in a named scenario, re-checked on every push |
| **V-AN** | First-order analysis script | a number, from stated assumptions, re-derivable |
| **V-CAD** | Parametric CAD assertion | a geometric fact holds in the model |
| **V-INS** | Installation / commissioning check | an obligation on the installer, not the device |
| **V-HW** | Hardware test | **nothing yet — no hardware exists** |

Requirement status:

| Status | Meaning |
|--------|---------|
| **VERIFIED (sim)** | discharged by V-MC and/or V-ST, at the logic level |
| **ANALYSED** | a V-AN number supports it, on assumptions that are flagged |
| **ASSERTED** | believed on design reasoning; no verification yet |
| **OPEN** | known not to be discharged; see §6 |

> **The recurring caveat.** *VERIFIED (sim)* means the **logic** is right, exhaustively.
> It says nothing about whether a sensor detects a hypothermic human through a blanket,
> whether a lip seal shears a finger, or whether a spring returns. Those are V-HW rows,
> and they are all open. Do not read §3 as a safety case for hardware.

---

## 2. Safety requirements

Derived from the hazard register and the design principle (PREVENT → REACT → INHERENT).
IDs are stable; do not renumber.

### Prevention — SF1

| ID | Requirement | From |
|----|-------------|------|
| **SR-001** | The system shall not initiate inward (clearing) motion unless occupancy is positively proven absent. | H1, H4, H6 |
| **SR-002** | Any sensor fault, stale sample, or out-of-range reading shall be treated as *occupied*. Absence of proof-of-emptiness shall never be treated as proof of emptiness. | H6, F1 |
| **SR-003** | Occupancy detection shall use physically diverse redundant channels. "Empty" shall require **every** channel to positively read clear; no single channel shall be able to unlock motion. | H1, H6, ADR-0012 |
| **SR-004** | Inward motion in progress shall stop and reverse to the deployed position on any life indication. | H1 |
| **SR-005** | The occupancy check shall be continuous for a defined dwell before motion is permitted, not a single sample. | H1, H6 |

### Reaction — SF2

| ID | Requirement | From |
|----|-------------|------|
| **SR-006** | Inward motion shall stop and reverse when contact force exceeds the safe cap, by a path **functionally independent** of SR-001…005. | H3, H5, H8, F1→F2 |
| **SR-007** | Contact force shall be capped below the injury threshold (**≤120 N**, cf. the ~150 N powered-door limit). | H3 |
| **SR-008** | The contact reaction shall act in **every** state the piston can occupy, including closed-and-flush. | H8, ADR-0022 |
| **SR-009** | A sweep shall not start while a contact trip is already asserted. | H3, H8 |

### Inherent — SF3, geometry

| ID | Requirement | From |
|----|-------------|------|
| **SR-010** | The moving piston-to-bore gap shall be filled by a compliant element, so a finger, hair or clothing **deflects** it rather than being sheared or drawn in. | H2 |
| **SR-011** | Seal drag shall be low enough that the fail-open relief of SR-013 remains achievable. | H7, ADR-0011 |
| **SR-012** | The piston shall never enclose an occupant behind it: it shall sweep only toward the open mouth. | F5, F4 |

### Fail-safe — SF4

| ID | Requirement | From |
|----|-------------|------|
| **SR-013** | Loss of drive power shall not sustain a holding force anywhere an occupant can be. | H7, F3 |
| **SR-014** | The pod may be held closed without power **only** at the flush end, where SR-012 makes occupant presence impossible. | H7, ADR-0009 |
| **SR-015** | Restoring power, or releasing the E-stop, shall not resume an interrupted sweep. The cycle shall re-enter through a fresh occupancy check. | H1, H7, ADR-0023 |
| **SR-016** | The external E-stop shall **remove drive power** (Category 0), inheriting the SR-013 relief path. | ADR-0023 |
| **SR-017** | No occupant-operated release or interior E-stop shall be fitted. | F7, ADR-0009 |
| **SR-018** | The fail-open release path shall be periodically self-tested. | F6 |

### Defence in depth — SF5, siting

| ID | Requirement | From |
|----|-------------|------|
| **SR-019** | Motion shall be signalled before and during movement, and a refusal-to-move state shall raise an alarm to a human. | H5, H8 |
| **SR-020** | Approach speed shall be reduced over the final stretch of travel. | H8 |
| **SR-021** | The mouth sill shall be ≤~500 mm above a clear, non-slip, forgiving surface, and shall never open over a real drop. | H4, ADR-0013 |

---

## 3. Traceability matrix

Every requirement to its design feature, verification method, and current result.
Evidence identifiers are re-runnable — see §5 for the commands.

### SF1 — prevention

| SR | Design feature | V | Evidence | Result |
|----|----------------|---|----------|--------|
| SR-001 | `LIFE_CHECK` gate before `CLEARING`; `life_present()` | **V-MC** | `Inv_NoAdvanceWhileOccupied`, `P_NoAdvanceUnderLife` | holds over all 29,892 reachable states — **VERIFIED (sim)** |
| SR-001 | " | **V-ST** | `test_interlock.gd` S2 (occupied), S4 (fault) | pass |
| SR-002 | `Channel.faulted()` = unhealthy ∨ implausible ∨ stale; fault ⇒ occupied | **V-MC** | `Inv_FaultMeansNoSweep` | holds — **VERIFIED (sim)** |
| SR-002 | " | **V-ST** | `OccupancyFusion.self_test()` — all 3⁴ = 81 vote combinations | pass |
| SR-003 | 4 diverse channels (radar vitals, thermal IR, NDIR CO₂, load/BCG); AND-toward-clear | **V-MC** | `Inv_SweepNeedsAllChannelsClear` | holds — **VERIFIED (sim)** |
| SR-003 | *physical* diversity of the 4 channels | **V-HW** | — | **OPEN** — part numbers unselected (#7) |
| SR-004 | `CLEARING` → `REDEPLOY` on life | **V-MC** | `P_NoAdvanceUnderLife` | holds — **VERIFIED (sim)** |
| SR-004 | " | **V-ST** | S3 mid-sweep intrusion | pass — reverses fully |
| SR-005 | `clear_dwell` ≥ `life_check_seconds`, reset on any life reading | **V-MC** | encoded as `DwellTicks` in `LifeCheck` | holds — **VERIFIED (sim)** |

### SF2 — reaction

| SR | Design feature | V | Evidence | Result |
|----|----------------|---|----------|--------|
| SR-006 | `contact_over_limit` trip, separate from `life_present()` | **V-MC** | `Inv_NoSweepWhileContact`, `P_NoAdvanceUnderContact` | holds — **VERIFIED (sim)** |
| SR-006 | independence *proven*: piston never passes a real occupant with **all four** SF1 channels blind | **V-MC** | **`Inv_NoCrush`** (over a ground-truth occupant) | holds — **VERIFIED (sim)**; the FMEA F1→F2 chain |
| SR-006 | " | **V-ST** | S5 (SF1 blind, SF2 catches) | pass |
| SR-007 | `SAFE_CONTACT_N` = 120 N | **V-ST** | `physics_demo.gd`: trash pile peaks ~63 N (yields, bounded); non-yielding body ~138 N → trips | pass — discriminates yield vs magnitude |
| SR-007 | the cap being *safe for tissue* | **V-HW** | — | **OPEN** — needs injury data (#8) |
| SR-008 | `CLEARED_HOLD` exits on either trip (ADR-0022) | **V-MC** | `Inv_NoTripHeldAtFlush` | holds — **VERIFIED (sim)** |
| SR-008 | " | **V-ST** | S6, + `hold-ignores-trips` mutant | pass; mutant caught |
| SR-009 | `LIFE_CHECK` holds while contact asserted | **V-MC** | `Inv_NoSweepWhileContact` | holds — **VERIFIED (sim)** |

### SF3 / geometry

| SR | Design feature | V | Evidence | Result |
|----|----------------|---|----------|--------|
| SR-010 | two compliant lip rings filling the 3 mm gap | **V-CAD** | `build_model.py` — lips touch bore, hug piston, ~0 overlap | geometry holds — **ANALYSED** |
| SR-010 | **compliance** (deflect, not shear) | **V-HW** | — | **OPEN** — a material property, asserted only |
| SR-011 | low-friction lip specified (ADR-0011) | **V-AN** | `seal_drag.py`: 16 / 150 / 700 N/m for lubricated / dry elastomer / dry+grit | **ANALYSED** — ~44× spread; **the master uncertainty** (#9) |
| SR-012 | syringe topology; piston sweeps toward the mouth | **V-CAD** | cavity/piston geometry; FMEA F4/F5 | **ASSERTED** by topology — no state can place an occupant behind the face |

### SF4 — fail-safe

| SR | Design feature | V | Evidence | Result |
|----|----------------|---|----------|--------|
| SR-013 | `UNPOWERED` state; return element relieves in the occupant zone | **V-MC** | `P_PinRelieves`, `P_NoAdvanceUnpowered` (Blackout run = FMEA F3) | holds — **VERIFIED (sim)** |
| SR-013 | " | **V-ST** | S7 blackout mid-sweep | pass — relieves to deployed |
| SR-013 | *passive* back-drive alone | **V-AN** | `pin_relief.py`: stalls at 1206 N resisting → residual pin **1206 N ≈ 10× the 120 N target** | **FAILS** — passive relief insufficient |
| SR-013 | ⇒ stored-energy return element | **V-AN** | `pin_relief.py`: **1567 N** required (≥ resisting ×1.3) | **ANALYSED** — drives closing force to 5546 N design (§4.3) |
| SR-014 | passive flush latch | **V-MC** | `FailOpen` holds position at `Flush` only | holds — **VERIFIED (sim)** |
| SR-014 | " | **V-ST** | S8 blackout at flush | pass — latch holds |
| SR-015 | `_recover()` → `REDEPLOY`/`AVAILABLE`, never `CLEARING` | **V-MC** | `P_NoAutoRestart` | holds — **VERIFIED (sim)** |
| SR-015 | " | **V-ST** | S9 E-stop release | pass |
| SR-016 | `drive_powered()` = `powered ∧ ¬estop` | **V-MC** | `Inv_EStopHalts` | holds — **VERIFIED (sim)** |
| SR-017 | no release device in the design | — | ADR-0009 / FMEA F7 | **VERIFIED by absence** — nothing to test |
| SR-018 | periodic self-test of the release path | — | — | **OPEN** — not designed (F6) |

### SF5 / siting

| SR | Design feature | V | Evidence | Result |
|----|----------------|---|----------|--------|
| SR-019 | `signal_level()`: green / red / orange / flashing-red; beacon in both twins | **V-ST** | `test_soft_profile.gd`; `signal_level()` maps `UNPOWERED`+`BLOCKED_OCCUPIED` → ALARM | pass — **VERIFIED (sim)** |
| SR-020 | `soft_profile.gd` reduced final approach | **V-ST** | `test_soft_profile.gd` — shape, monotonicity, completion, timing | pass — **VERIFIED (sim)** |
| SR-021 | sitting-height sill, forgiving drop zone | **V-INS** | ADR-0013 siting rules | **OPEN** — installer obligation; needs local-code check + named sign-off (#10) |

### Hazard coverage check

The issue's done-criterion: every hazard resolves to ≥1 requirement **and** ≥1 test.

| H | Requirements | Verified by | Covered |
|---|--------------|-------------|---------|
| H1 push-out/crush of non-reacting occupant | SR-001…005, 015 | V-MC ×5, V-ST S2/S3/S4 | ✅ |
| H2 shear / draw-in at the gap | SR-010 | V-CAD (geometry) | ⚠️ geometry only — **compliance unproven** |
| H3 crush by force | SR-006, 007 | V-MC `Inv_NoCrush`, V-ST S5 | ✅ logic; cap value open |
| H4 fall from elevated mouth | SR-001, 021 | V-MC (SR-001), V-INS | ⚠️ single-layer by accepted trade |
| H5 reach-in during motion | SR-006, 008, 019 | V-MC `Inv_NoCrush`/`Inv_NoTripHeldAtFlush`, V-ST S6 | ✅ logic |
| H6 moves while occupied (fault) | SR-002, 003 | V-MC `Inv_FaultMeansNoSweep`, V-ST 81-combo | ✅ logic |
| H7 trapped under self-locking hold | SR-013…016, 018 | V-MC `P_PinRelieves`, V-ST S7/S8/S9 | ⚠️ logic verified; **relies on an unbuilt spring** |
| H8 pinch at the mouth lip | SR-008, 020 | V-MC `Inv_NoTripHeldAtFlush`, V-ST S6 | ✅ logic |

No hazard is unmapped. Three carry a ⚠️ — see §6.

---

## 4. Fault tree analysis

Qualitative FTA (minimal cut sets). **Not quantified**: no failure-rate data exists for
any component, and MTTFd/DC/CCF figures are exactly what the ISO 13849 dossier (#7) has
to produce. Cut-set *order* is the assurance argument available today.

Notation: `AND` = all inputs required (this is where redundancy lives), `OR` = any input
suffices. `[Fn]` cites the FMEA row, `[SR-nnn]` the requirement that defends the branch.

### 4.1 TE-1 — Piston advances into an occupant (H1, H6)

```
TE-1  Piston advances inward while a person is inside
│
└── AND ─────────────────────────────────────────────────────
    │
    ├── E1  A person is inside                        (enabling condition, not a fault)
    │
    └── E2  SF1 reports "empty"                                          [SR-001..003]
        │
        └── AND ── all four diverse channels must fail together ─────────
            ├── B1  radar vitals false-negative   (still/covered occupant, mis-cal)
            ├── B2  thermal IR false-negative     (hypothermic, blanketed, warm room)
            ├── B3  NDIR CO2 false-negative       (ventilation, sensor drift)
            └── B4  load/BCG false-negative       (light occupant, off-plate, drift)
```

**Minimal cut set:** `{B1, B2, B3, B4}` — order 4.

Two structural facts do the work. The voter is **AND-toward-clear**, so a *single*
channel reading clear can never unlock motion — this is why the gate is AND and the cut
set is order 4 rather than order 1. And a *faulted* channel votes occupied, so failures
of the "dead sensor" kind do not contribute to this tree at all; they move the machine
to the safe side. Only silent **false-negatives** are cut-set members.

The residual risk is therefore **common-cause failure**, which no AND gate defends
against and which is precisely why ADR-0012 chose four *different physical principles*.
Untested: a single environmental condition that blinds all four at once (a thick
insulating blanket on a hypothermic, motionless occupant in a well-ventilated cell is
the worst credible candidate, and is the specific hardware test #7 must run).

> A logic defect that bypasses the voter would be an order-1 cut set. That branch is
> closed by V-MC — `Inv_SweepNeedsAllChannelsClear` — and by the `sf1-ignored`,
> `fault-reads-clear` and `majority-vote` mutants, which are exactly this failure
> injected deliberately. It is omitted from the tree above as *verified absent*.

### 4.2 TE-2 — Occupant is injured by contact force (H3, H5, H8)

```
TE-2  Contact force on an occupant exceeds the injury threshold
│
└── AND ─────────────────────────────────────────────────────
    │
    ├── TE-1  the piston advanced into them            (order 4, above)
    │
    └── E3  SF2 fails to bound the force                                 [SR-006..008]
        │
        └── OR ─────────────────────────────────────────────
            ├── B5  safety edge fails to sense contact       (blind/damaged/mis-routed)
            ├── B6  drive force monitoring fails or is mis-calibrated
            ├── B7  the 120 N cap is itself above the injury threshold      ← ***
            └── B8  reaction acts too late in some state                 [ADR-0022]
```

**Minimal cut sets:** `{B1,B2,B3,B4,B5}`, `{B1..B4,B6}`, `{B1..B4,B7}`, `{B1..B4,B8}` —
all order 5.

**B7 is the branch that deserves attention.** It is not a random failure — it is a
*wrong number*. If 120 N is above the real injury threshold for the vulnerable users
this machine assumes (intoxicated, unconscious, elderly), then SF2 bounds the force to a
value that still injures, and no amount of redundancy elsewhere helps. It is a
**systematic** error, present in every unit, correlated across the whole fleet, and it
would not be caught by any test the project currently runs. Issue #8 is the only thing
that closes it.

B8 was a live defect until ADR-0022 — `CLEARED_HOLD` ignored the trip for up to 2 s.
Model checking found it. It is now closed by `Inv_NoTripHeldAtFlush` and guarded by a
mutant.

### 4.3 TE-3 — Occupant held under a sustained pin (H7, F3)

```
TE-3  Occupant is held under sustained force with no relief
│
└── AND ─────────────────────────────────────────────────────
    │
    ├── TE-1  the piston advanced into them            (order 4)
    │
    └── E4  no relief path acts
        │
        └── AND ── both the powered and unpowered paths must fail ───────
            ├── E5  powered reverse fails
            │   └── OR ── B5/B6 (SF2 blind, above)  ∨  B9 drive cannot reverse
            │
            └── E6  unpowered relief fails                                [SR-013,018]
                └── OR ─────────────────────────────────────
                    ├── B10  return element absent, under-sized or failed        ← ***
                    ├── B11  transmission not back-drivable in the occupant zone [F6]
                    └── B12  flush latch engages inside the occupant zone   [design error, SR-014]
```

**Minimal cut sets:** order 6, e.g. `{B1..B4, B5, B10}`.

Deepest tree in the analysis — this is the F3 design-out working. Two notes:

**B10 is load-bearing and unbuilt.** `pin_relief.py` shows passive back-drive **does not
work**: it stalls at 1206 N of seal drag, flooring the residual pin at ~10× the 120 N
target. So the entire unpowered branch rests on a **1567 N stored-energy return element
that does not exist yet** and has never been sized against a measured seal drag. E6 is
currently a single-point dependency wearing the costume of a redundant branch.

**B10 and B11 are not independent of TE-2's B5/B6 in the way the tree implies.** A
correlated cause — the seal drag being far higher than modelled — simultaneously raises
the force SF2 must bound *and* defeats the return element sized for the lower figure.
That is `seal_drag.py`'s 700 N/m upper case. The order-6 cut set is therefore optimistic
under exactly the condition the project has flagged as its master unknown (#9).

**Sizing consequence, for the record** (`actuator_sizing.py`, re-run 2026-08-04):

| Quantity | Value |
|----------|-------|
| seal drag (2 lips × 3.97 m @ 150 N/m) | 1190 N |
| resisting force (drag + guide friction) | 1206 N |
| SF4 return element required | **1567 N** |
| closing resistance with the return element | 2773 N |
| **design force (×2 factor)** | **5546 N** — was 2411 N before SF4 |

---

## 5. Reproducing the evidence

```sh
./scripts/run_selftest.sh              # twin self-tests + all three TLC runs (the push gate)
./scripts/run_modelcheck.sh --mutants  # proves the model's checks can fail (9 injected defects)

flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/pin_relief.py       # SR-013
flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/actuator_sizing.py  # §4.3 table
flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/seal_drag.py        # SR-011
```

Model-check runs need a JRE; without one the gate skips with a warning rather than
blocking. Full claim list and abstractions: [`../spec/README.md`](../spec/README.md).

---

## 6. Gap register

Everything §3 does **not** discharge. Ordered by how much of the safety case rests on it.

| # | Gap | Blocks | Consequence if wrong | Issue |
|---|-----|--------|----------------------|-------|
| **G1** | **Seal drag unmeasured** (16–700 N/m, ~44×) | SR-011, SR-013 | correlated: defeats the return element **and** raises the force SF2 must bound (§4.3) — weakens TE-2 and TE-3 together | [#9](https://github.com/StrayEddy/HiveCell/issues/9) |
| **G2** | **120 N cap not validated against injury data** | SR-007 | systematic, fleet-wide: SF2 bounds force to a value that still injures (B7) | [#8](https://github.com/StrayEddy/HiveCell/issues/8) |
| **G3** | **Return element unbuilt and unsized against real drag** | SR-013 | the whole unpowered branch of TE-3 is a single point (B10) | [#11](https://github.com/StrayEddy/HiveCell/issues/11) |
| **G4** | **Seal compliance unproven** — deflect vs shear | SR-010 | H2 has *geometry* but no *material* defence | [#9](https://github.com/StrayEddy/HiveCell/issues/9) |
| **G5** | **SF1 channels unselected; common-cause untested** | SR-003 | the order-4 AND gate of §4.1 is the assurance argument; CCF is what collapses it | [#7](https://github.com/StrayEddy/HiveCell/issues/7) |
| **G6** | **No PL rating** — no MTTFd / DC / CCF, no rated controller | all | §4 cannot be quantified; no ISO 13849 claim can be made | [#7](https://github.com/StrayEddy/HiveCell/issues/7) |
| **G7** | **Timing layer abstracted** — dropouts, races, stall, power-loss position | SR-001…006 | V-MC collapses continuous time; a timing fault is out of its scope | [#3](https://github.com/StrayEddy/HiveCell/issues/3) |
| **G8** | **Back-drivability of the rigid chain unverified** | SR-013 | B11 | [#11](https://github.com/StrayEddy/HiveCell/issues/11) |
| **G9** | **Release-path self-test not designed** | SR-018 | F6 goes undetected until it is needed | — |
| **G10** | **Siting unenforceable by the device** | SR-021 | H4's sole non-SF1 layer depends on the installer | [#10](https://github.com/StrayEddy/HiveCell/issues/10) |
| **G11** | **Model is hand-written** and can drift from the GDScript | all V-MC | a stale model verifies a machine that no longer exists | — |

**The honest summary.** The *logic* is in good shape — exhaustively verified, with the
checks themselves mutation-tested. The *physics* is almost entirely unverified, and two
gaps (G1, G2) are not independent bad-luck events but correlated, systematic errors that
would weaken several branches of §4 at once. G1 is a ~$200 bench test that has been on
the roadmap since ADR-0011 and remains the highest-value unbought piece of information
in the project.

---

## 7. Maintenance

This document is only worth having if it stays true.

- A new hazard or safety function → add the SR here **and** the §3 row, or the coverage
  check in §3 breaks.
- A changed safety behaviour → update the ADR, `SAFETY.md`, and the §3 evidence row.
- A new verification (test, property, script) → cite it in §3; unreferenced evidence is
  invisible to a reviewer.
- Closing a gap → move the §6 row into §3 with its result, and re-check §4's cut sets:
  closing a gap can change a cut-set order, which is the number that matters.
