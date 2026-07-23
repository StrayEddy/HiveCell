# Seal-drag bench test (SF3) — procedure

**Goal:** replace the single biggest estimated number in the whole design — seal
drag — with a *measured* one. Everything downstream (actuator size, the SF4 return
spring, energy per stroke, and whether ADR-0010's drive complexity is even warranted)
scales with it. Right now it is estimated across a ~40× range (**~16–700 N/m**); this
test collapses that range for a real seal sample.

> ⚠️ This is a **bench test with no occupant and no full machine**. It measures a
> friction force on a small seal coupon. It is not a test of the machine's safety
> functions. Read the safety notice in [`../LICENSE`](../LICENSE).

Related: ADR-0011 in [`DECISIONS.md`](DECISIONS.md) (why seal drag is the master
lever) and the first-principles estimate in [`../scripts/seal_drag.py`](../scripts/seal_drag.py).

---

## 1. What we are measuring, and the units that matter

The scripts model total seal force as:

```
f_seal = SEAL_DRAG_PER_M × perimeter × lips
```

where `SEAL_DRAG_PER_M` is the drag **per metre of a single lip's line contact**
(N/m), `perimeter ≈ 4.0 m` (rounded-rectangle piston cross-section), and `lips = 2`.

So the number this test must produce is **N/m, per lip**. You measure the steady
sliding force on a coupon of known contact length `L` carrying `n` lips, then:

```
SEAL_DRAG_PER_M  =  F_slide  /  (L × n)          [N/m per lip]
```

That single value drops straight into the twin (Section 6).

### The design conditions to reproduce

The real seal bridges a **3 mm running clearance per side** and scrapes a **dry,
potentially gritty** steel wall at a slow sweep speed. To be representative, the
coupon must sit at the same **interference** (lip compressed to bridge ~3 mm and
seal), run against the **same steel surface finish** you intend to use, and be tested
**dry** (the pessimistic, realistic street case) — with lubricated/PTFE runs as the
comparison that shows what a low-friction spec buys.

---

## 2. Bill of materials (~$150–250)

| Item | Purpose | Approx. cost |
|------|---------|-------------:|
| Seal profile samples — 2–3 candidates (e.g. dry NBR/EPDM wiper lip, a PTFE-faced or silicone lip, and a brush strip) | The variable under test; get ~300–500 mm of each | $30–80 |
| Steel plate, same finish/grade as the intended bore (~150 × 600 mm) | The counter-surface the lip scrapes | $15–40 |
| Digital force gauge **or** hanging luggage/fish scale (0–20 kg / 0–200 N, ideally with peak-hold) | Reads the sliding force | $15–60 |
| Linear motion: a drawer slide, linear rail, or just a flat guided track | Keeps the pull straight and the interference constant | $10–40 |
| Clamps, a rigid carrier block to hold the coupon at a set interference, feeler gauges/shims to set the gap | Fixture | $20–40 |
| Optional: fine sand/street grit, and a small weight set to vary contact pressure | Grit case + pressure sweep | $0–20 |

A kitchen/postal scale under the plate is a valid alternative readout (measures the
horizontal drag if you build a simple pulley, or the normal load for calibration).

---

## 3. Rig — two options

**Option A — horizontal pull (simplest).** Mount the steel plate flat and fixed.
Hold the seal coupon in a carrier that presses it against the plate at the set
interference (use shims to fix the gap the lip bridges). Attach the force gauge/scale
to the carrier and pull it along the plate by hand at a slow, steady speed. Read the
**steady-state** force (not the initial break-away spike) — peak-hold helps you catch
a stable plateau.

```
   pull  <—[force gauge]—[ carrier: seal coupon pressed down ]
   ================ steel plate (fixed) ================
```

**Option B — dead-weight / inclined (self-paced).** Put the coupon on the plate
under a known normal load, tilt or use a pulley + hanging weights, and find the force
that produces steady sliding. Slower to run but needs no gauge — a scale + weights
suffice.

Either way you want: **constant interference**, **steady slow speed** (the machine
sweeps at ~3.7 mm/s — hand speed is fine; friction here is roughly speed-independent),
and the **steady sliding force**, not stiction break-away.

---

## 4. Variables to sweep

Run each candidate seal across these — they are the axes that explain the 40× range:

1. **Interference** — the compression needed to bridge ~3 mm and seal. Test the
   design value and ±1 mm around it. (This is the biggest controllable driver.)
2. **Dry vs lubricated / PTFE-faced.** Dry is the design-realistic case; the low-friction
   run quantifies what the spec change buys (ADR-0011 targets a low-friction seal).
3. **Clean vs gritty.** Sprinkle fine grit on the plate for the worst realistic case.
4. **New vs bedded-in.** Optionally run a few hundred cycles first; lips can smooth
   (drag drops) or the surface can score (drag rises).

Keep everything else fixed within a run so each row isolates one variable.

---

## 5. Procedure & data recording

1. Fix the plate; note its grade and surface finish (Ra if known).
2. Mount a coupon; set interference with shims; record the coupon's **lip count `n`**
   and **contact length `L`** (the length of plate the lip actually touches).
3. Pull steadily; record the **steady sliding force** `F_slide`. Repeat 3× per
   condition and average.
4. Compute `SEAL_DRAG_PER_M = F_slide / (L × n)`.
5. Log every run:

| run | seal | interference (mm) | dry/lub | clean/grit | F_slide (N) | L (m) | n | **N/m per lip** |
|----:|------|------------------:|---------|------------|------------:|------:|--:|----------------:|
| 1 | | | | | | | | |

Report, per seal candidate, a **nominal** and a **worst-case** N/m. The worst-case
(dry + grit + max interference) is what the force budget must survive.

---

## 6. Feed the result into the twin / analysis

The measured N/m plugs straight into the existing scripts via the `SEAL_DRAG_PER_M`
env var (per lip). Re-run the force chain with your measured nominal *and* worst-case:

```sh
# actuator + force budget
SEAL_DRAG_PER_M=<measured> flatpak run --command=freecadcmd \
    org.freecad.FreeCAD scripts/actuator_sizing.py

# passive fail-open relief (SF4) — does the pin relieve to a safe force?
SEAL_DRAG_PER_M=<measured> flatpak run --command=freecadcmd \
    org.freecad.FreeCAD scripts/pin_relief.py
```

Run both at the nominal and the worst-case number so the design is sized for the bad
day, not the good one.

---

## 7. What the number decides (acceptance thresholds)

From the analysis in ADR-0009/0010/0011 and `pin_relief.py`:

| Measured drag | Consequence |
|---------------|-------------|
| **≤ ~13 N/m** | Passive fail-open relief alone would be safe — the SF4 return spring could shrink dramatically and ADR-0010's single-acting drive may be unnecessary. (Unlikely; a >11× reduction.) |
| **~40 N/m** (low-friction spec) | Resisting force ~333 N; passive residual pin ~333 N (~3× safe margin). Light actuator, modest spring. The target ADR-0011 is aiming for. |
| **~150 N/m** (dry elastomer nominal) | Resisting force ~1206 N; big forces; strongly motivates the ADR-0010 spring-open drive and a low-friction seal spec. |
| **> ~300 N/m** (dry + grit, stiff lip) | Forces 2–4× the model; the current mechanism assumptions need rework — reduce interference, cut to one lip, or change seal technology. |

**The decision this unblocks:** whether ADR-0010 (single-acting tension-close +
spring-open) is warranted, or a lighter drive + small spring suffices — plus freezing
the actuator and return-spring sizing. Record the measured value and the resulting
re-runs, then update ADR-0011 (and ADR-0010's status) with real data.

---

## 8. Test safety

Trivial compared to the machine, but: watch pinch points between the carrier and any
guide; secure the plate so it can't fly if you pull hard; wear eye protection if using
grit; no part of this test should ever have a person inside or near a moving piston —
there is no piston here, only a coupon.
