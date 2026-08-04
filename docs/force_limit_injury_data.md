# SF2 real force limit — injury/biomechanical data (issue #8, gap G2)

**Goal:** replace the engineering-judgment placeholder behind `SAFE_CONTACT_N` with a
cap traceable to real injury/biomechanical data, as flagged in
[`SAFETY.md`](SAFETY.md)'s Open items and gap **G2** in
[`TRACEABILITY.md`](TRACEABILITY.md).

> This is the **desk half** of issue #8 only. The other half — the drive's *actual*
> force-limitability under a real hard jam (can the real actuator/controller actually
> hold a cap, and how fast, once seal drag and the load's own inertia are real?) —
> is hardware work and stays open. SF1 (never move while occupied) remains the primary
> safeguard either way: SF2 is the backstop for the case SF1 fails to catch, not a
> substitute for it.

---

## 1. What was wrong with the placeholder

`godot/physics_demo.gd` set `SAFE_CONTACT_N = 120.0` with the comment "below the
~150 N powered-door limit, with margin for vulnerable occupants." Two problems:

1. **The "150 N powered-door limit" is not a real citation.** No standard was named,
   and — checked below — the actual power-door standard (ANSI/BHMA A156.19) caps
   normal operating force at **67 N**, not 150 N. The number appears to have been an
   unsourced round figure, exactly the kind of "systematic error, identical in every
   unit" gap **G2** in the FTA flags.
2. **It compared against the wrong hazard class.** A powered *door* stopping against
   an obstruction is a different geometry and contact area than HiveCell's H3/H8: "a
   slow piston pins a limb/torso against opening frame or bracing" or pinches at the
   mouth lip (`SAFETY.md` hazard register). The right comparison is body-region
   biomechanical injury/pain data, not an adjacent product category's door-closing
   spec.

## 2. Sources surveyed

| Source | What it measures | Relevant value | Applicability |
|---|---|---|---|
| **ISO/TS 15066:2016**, Annex A, Table A.2 | Body-region-specific quasi-static contact force at *pain onset* (University of Mainz study, 100 adult subjects, 29 body areas, 75th percentile of onset-of-pain pressures) | **Abdomen 110 N**, hands/fingers 140 N, chest 140 N, neck 150 N, pelvis 180 N, upper arms 150 N, lower arms 160 N (all quasi-static) | Best-matched dataset available: purpose-built for exactly this hazard (a powered mechanism that may clamp a body part against a fixed surface), by body region, with a documented derivation. Industrial/cobot context, adult subjects only. |
| **FMVSS 118 / 49 CFR 571.118** (US federal) | Power-window/partition anti-pinch: max squeeze force on a semi-rigid test rod across the full opening range | **100 N**, tested down to a 4 mm rod ("equivalent to a small child's finger") | Real, enforced regulatory precedent for the *identical* hazard class — a powered mechanism closing on a body part — and the only one of these sources that specifically validates against a child-sized limb. |
| **ANSI/BHMA A156.19** (power-assist/low-energy swing doors) | Max force to stop door motion during normal operation; max force to manually move the door on power failure | **67 N** (15 lbf) normal operation stop force; **133 N** (30 lbf) to set in motion on power loss | The standard the old comment was trying to cite. Confirms 150 N was wrong — the real door figure is lower, not higher, than HiveCell's old cap. |
| **EN 12453** (powered gates) | Max static crushing force by gap size; required force decay after contact | 400 N for 50–500 mm gaps, 1400 N for gaps >500 mm; must decay below **150 N within 750 ms** of contact | Gates tolerate much higher forces than doors/windows because most standard gap sizes are treated as lower-risk than a door edge. The "150 N" figure that likely got conflated into the old comment is this standard's *post-contact decay target*, not a static cap. |
| Cadaver crush studies (power-window entrapment, finger) | Force at onset of visible injury (contusion, fracture) | ~300 N: contusion/superficial injury onset. ~467–1485 N: fracture range (avg. ~1485 N, one outlier at 467 N in 200 jam events) | Confirms pain-onset thresholds (ISO/TS 15066, FMVSS 118) sit well below actual tissue injury — i.e. using pain onset as the design threshold, as this doc recommends, is conservative relative to injury, not merely adequate. |

## 3. Which body region actually governs

`SAFETY.md`'s hazard register describes two SF2-relevant scenarios:

- **H3** — "slow piston pins a limb/torso against opening frame or bracing"
- **H8** — "piston reaching flush pinches at the opening edge" (the mouth lip)

Both name torso/limb-scale contact, not just a fingertip catch — the piston face is
large relative to a hand, so a person positioned along the bore (`PERSON_HALF_X` in
the twin) can plausibly present abdomen, chest, or limb to the closing face, not only
a finger at the 3 mm lip gap. ISO/TS 15066's own guidance (§A.1, "worst case") is to
apply the *most stringent* body-region limit among those plausibly contacted — which
for this scenario is **abdomen at 110 N quasi-static**, not the hands/fingers value.

Skull/forehead and face are marked as a **critical zone** in ISO/TS 15066 (§5.5.5.3):
contact there is not permissible *at any force*, full stop. That is consistent with
this repo's existing principle that SF2 is a backstop and SF1 (never move while
occupied) must remain primary — no force cap makes head/face contact acceptable, so
this doc does not try to derive one.

## 4. Comparison against the cap

| Standard/threshold | Value | Is 120 N (old cap) below it? |
|---|---:|---|
| ISO/TS 15066 abdomen, quasi-static | 110 N | **No** — 120 N exceeds it by ~9% |
| FMVSS 118 (child-finger-equivalent rod) | 100 N | **No** — 120 N exceeds it by 20% |
| ISO/TS 15066 hands/fingers, quasi-static | 140 N | Yes |
| ANSI/BHMA A156.19 door, normal operation | 67 N | **No** — but this is the wrong comparator (§1) |
| EN 12453 gate, 50–500 mm gap | 400 N | Yes |
| Cadaver contusion onset | ~300 N | Yes |

The old 120 N cap was not conservative against the two most relevant, real,
body-region-specific sources: ISO/TS 15066's own abdomen pain-onset limit and the US
federal child-finger pinch standard. Both cluster at 100–110 N.

## 5. Recommendation

**Lower `SAFE_CONTACT_N` to 100 N.** Rationale for landing on the FMVSS 118 value
specifically rather than the ISO abdomen value (110 N):

- It clears *both* relevant thresholds (100 N ≤ 100 N ≤ 110 N), rather than sitting
  between them.
- It is the one source in this survey validated against a body part smaller than an
  adult's — relevant given `SAFETY.md`'s stated user model ("VULNERABLE — may be
  intoxicated, unconscious, disabled, asleep").
- It is a real, round, defensible regulatory number rather than a synthesized value,
  which matters for a fleet-wide constant a reviewer will ask "where did this number
  come from" about.

This still discriminates cleanly against the twin's existing test scenarios
(`physics_demo.gd`, SR-007): the trash-pile load peaks ~63 N (well under, does not
trip) and the non-yielding-body load reaches ~138 N (well over, trips).

## 6. Caveats — this does not close gap G2, it narrows it

- ISO/TS 15066's Table A.2 values are **pain-onset**, not injury, thresholds, from a
  single study (its own footnote flags this — "anticipation that additional studies
  will be conducted... that could result in modification of these values"). That is
  the right target for a safety cap (stop before pain, not before injury), but it is
  not exhaustive tissue data across ages/conditions.
- The test geometry behind Table A.2 is a flat 1.4×1.4 cm rigid probe, not
  HiveCell's actual piston face or lip profile — the *pressure* limits in the same
  table would need the real contact area to apply; only the *force* limits are
  geometry-independent and used here.
- All these sources study adult subjects (or adult-cadaver / adult-scale test rigs
  except FMVSS 118's 4 mm rod). None directly measures a HiveCell-scale user
  population.
- **Still open, and still hardware-gated:** whether the real drive (motor + controller
  + seal drag, issue #9) can actually *hold* a 100 N cap under a hard jam — sim force
  is a modeled quantity, not a measurement of real force-limitability. That is the
  other half of issue #8.

## Sources

- [ISO/TS 15066:2016(E)](https://www.diag.uniroma1.it/deluca/pHRI_elective/ISO_TS_15066_2016_en.pdf) — Annex A, Table A.2 (Biomechanical limits) and Table A.1 (body model)
- [49 CFR § 571.118 — FMVSS 118, power-operated window, partition, and roof panel systems](https://www.law.cornell.edu/cfr/text/49/571.118)
- [ANSI/BHMA A156.19 — Power Assist and Low-Energy Power-Operated Doors](https://law.resource.org/pub/us/cfr/ibr/003/bhma.a156.19.2002.pdf)
- [BS EN 12453 explained — gate force/gap limits](https://gaterepairer.co.uk/knowledge-hub/bs-en-12453/)
- [Finger injuries caused by power-operated windows of motor vehicles: an experimental cadaver study](https://www.sciencedirect.com/science/article/abs/pii/S0020138311005845)
