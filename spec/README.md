# HiveCell — formal model of the safety interlock

Machine-checked proof of the interlock's safety claims over **all** reachable states,
rather than the hand-written scenarios in `godot/tests/test_interlock.gd`.
Roadmap [#1](https://github.com/StrayEddy/HiveCell/issues/1).

```
./scripts/run_modelcheck.sh              # the three green runs   (~70 s)
./scripts/run_modelcheck.sh --deep       # Steps=6, DwellTicks=3  (~2 min 40 s)
./scripts/run_modelcheck.sh --mutants    # prove the checks bite  (~2 min)
```

Needs a JRE (`sudo pacman -S jre-openjdk`) — `tla2tools.jar` is downloaded to
`~/.cache/hivecell/` on first run. Nothing is vendored into the repo.

| Run | Environment | Proves |
|-----|-------------|--------|
| `Safety.cfg` | adversarial — any sensor reading, any trip, any power/E-stop event, people entering and leaving, at every tick | the 7 invariants + 5 action properties below |
| `Liveness.cfg` | benign — nothing ever wrong | the machine actually *works*: the item gets cleared, the pod returns to service |
| `Blackout.cfg` | FMEA **F3** — SF1 wholly blind with a real occupant inside, power fails at any moment and never returns | the SF4 pin relieves |

Current result: **all three pass** (29,892 / 22 / 264 distinct states) and all 9
injected defects are caught.

---

## What is verified

Stated as invariants (hold in every reachable state) and action properties (hold
across every transition — these are the formal analogue of the per-frame assertion
in `test_interlock.gd::_run()`, which state invariants cannot express).

| Name | Claim | Traces to |
|------|-------|-----------|
| `Inv_NoAdvanceWhileOccupied` | a sweep is never underway while any life signal or sensor fault is present | SF1, H1/H6 |
| `Inv_SweepNeedsAllChannelsClear` | a sweep runs only when **every** diverse channel positively reads CLEAR | ADR-0012 "AND toward clear" |
| `Inv_FaultMeansNoSweep` | a faulted/stale channel stops the machine exactly as a life reading would | ADR-0012 "fault = occupied" |
| `Inv_NoSweepWhileContact` | the safety edge alone also forbids a sweep, independently of SF1 | SF2 |
| `Inv_EStopHalts` | E-stop or power loss ⇒ the machine is in its fail-open state, not driving | ADR-0009/0023 |
| `Inv_BlockedIsStill` | refusing to move means actually standing still, at the open end | SF1 |
| **`Inv_NoCrush`** | **the piston never drives past a real occupant — even with all four SF1 channels blind** | **FMEA F1→F2** |
| `Inv_NoTripHeldAtFlush` | the pod never sits closed-and-flush with either trip asserted | SF2, H8, ADR-0022 |
| `P_NoAdvanceUnderLife` | no inward motion on any tick whose life reading says occupied | SF1 |
| `P_NoAdvanceUnderContact` | no inward motion on any tick with the edge tripped | SF2 |
| `P_NoAdvanceUnpowered` | an unpowered drive cannot close the pod | SF4 |
| `P_NoTeleport` | the piston moves one step per tick; it never resets position instead of reversing through it | — |
| `P_NoAutoRestart` | restoring power or releasing the E-stop never resumes the sweep | ADR-0009/0023 |
| `P_BagEventuallyCleared` | benign case: the item left behind really does get cleared | liveness |
| `P_ReturnsToService` | the cycle returns to service rather than parking closed | liveness |
| `P_PinRelieves` | with power gone, the piston never rests pinned mid-stroke | SF4, FMEA F3 |

Every claim above is verified against the shipped FSM.

`Inv_NoCrush` is the one that earns the "defence in depth" phrase in `SAFETY.md`.
The other SF1 claims are all *sensor-relative* — they say the machine obeys its
sensors, which is not the same as saying nobody gets hurt. `Inv_NoCrush` is stated
over a **ground-truth occupant** the sensors may miss entirely, so it holds even in
the FMEA F1 case where all four channels read false-empty. Scenario S5 in
`test_interlock.gd` checks this at one hand-picked position; here it holds for every
occupant position in every reachable state.

---

## Model ↔ code correspondence

The spec is a hand-written model, not generated from the GDScript, so this table is
the thing to re-check when either side changes.

| TLA+ | GDScript |
|------|----------|
| `FsmStates` | `enum State` — same seven, `UNPOWERED` included |
| `Available`, `LifeCheck`, `Clearing`, `ClearedHold`, `Redeploy`, `BlockedOccupied` | the six `match state:` branches of `step()` |
| `FailOpen` | `_fail_open()` — SF4 relief + flush latch |
| `Recover` | `_recover()` — back out, never resume |
| `DriveOf(es, pw)` | `drive_powered()` |
| `powered`, `estop` | `powered`, `estop` |
| `Verdict(v)` | `life_present()` `:48–53` → `OccupancyFusion.occupied()` `occupancy_fusion.gd:102–106` |
| `LifeOf(v)` | *specification only* — see "Why `LifeOf` and `Verdict` are separate" |
| `Edge(ct)` | `contact_over_limit` (SF2) |
| `vote ∈ [Channels → Votes]` | the four `Channel`s and their `vote()` `occupancy_fusion.gd:47–50` |
| `FaultOf` | `Channel.faulted()` — unhealthy ∨ implausible ∨ stale `:44–45` |
| `dwell` / `DwellTicks` | `clear_dwell` / `life_check_seconds` |
| `hold` / `HoldTicks` | `t` / `hold_seconds` |
| `progress ∈ 0..Steps` | `progress ∈ [0.0, 1.0]` |
| `bag` | `bag_present` |
| `Tick` atomicity | `step(delta)` reads the sensor fields as they stand when it runs |

### Why `LifeOf` and `Verdict` are separate

They are equal in the unmutated spec, and deliberately not collapsed:

- `LifeOf` is the **specification** of occupancy — only the invariants use it.
- `Verdict` is the **mechanism** the state machine consults — only the FSM uses it.

Without the split, a defect injected into the voter would weaken the very invariant
meant to catch it, and the mutation suite would report a false pass. `Edge(ct)` plays
the same role for SF2. Don't merge them.

### Abstractions (where the model is *not* the code)

Each of these is a place the proof is narrower than reality. They are the honest
limits of what the green runs establish.

1. **Discrete travel.** `progress` is `0..Steps` (4 by default), not a real in
   `[0,1]`. Preserved: monotone advance only in `CLEARING`, monotone retreat in
   `REDEPLOY`, and one step per tick. Abstracted away: the SF5 velocity shaping in
   `soft_profile.gd`. The model proves *whether* the piston may move and in which
   direction; it says nothing about *how fast*. `--deep` re-runs at `Steps = 6`.
2. **Discrete time.** Timers are tick counts, and `hold` **saturates** at
   `HoldTicks` (the code only ever compares `t >= hold_seconds`, so values past the
   threshold are indistinguishable). Sound for these claims, and it keeps the state
   space finite.
3. **`reverse_from` is dropped.** In the code it only sets the reverse stroke's
   soft-profile span — an SF5 velocity detail. It cannot affect *whether* progress
   decreases, which is all the model claims.
   Likewise the unpowered return *rate* (`return_seconds`) is a placeholder on both
   sides: the real rate is spring force minus seal drag, and seal drag is the
   project's master unknown (ADR-0011, issue #9). Only the **direction** of the
   relief and the fact that it **completes** are claimed.
4. **One occupant, stationary.** They may enter or reach in at any time, but only
   ahead of the piston face (FMEA F5 geometry), and they don't move once inside.
5. **The safety edge is perfect.** `SafetyEdgeOK` *forces* `contact` true whenever
   the face is against the occupant. A failed-blind SF2 is therefore **out of
   scope** — the model proves SF2 backstops SF1, not that SF2 itself cannot fail.
   Diverse-redundant SF2 is not modelled and remains a hardware/PL question.
6. **Sensor channels are free.** Any channel may false-positive or false-negative at
   any tick, independently. This is deliberately *weaker* than reality (real
   channels correlate) and so is the safe direction — except for common-cause
   failure, which ADR-0012 addresses by physics diversity, not by logic, and which
   this model cannot speak to.
7. **`Steps = 4` is not a proof for all `Steps`.** TLC checks a finite instance.
   `--deep` raises it; neither is induction over the parameter.

---

## SF4: how the model drove the implementation

Worth recording, because it is the reverse of the usual order.

Two of issue #1's four named invariants originally had **nothing to check against**:
`safety_interlock.gd` had no E-stop input and no notion of power at all, even though
`SAFETY.md` retained an external/operator E-stop and ADR-0009 makes the fail-open
drive the entire answer to FMEA F3. Rather than drop those claims, the spec modelled
them — an `UNPOWERED` state plus `FailOpen` / `Recover` — and they sat verified
against *intent* while the code had no counterpart.

Writing that model forced a question nobody had answered: **what does pressing the
E-stop actually do?** ADR-0009 named the E-stop but never specified its behaviour. The
model had to commit to something, and the only choice consistent with SF4 was Category
0 — cut drive power, inherit the fail-open path — because a freeze-in-place E-stop
recreates FMEA F3 exactly, the failure that forced SF4 in the first place. That is now
**ADR-0023**, and the twin implements it.

So the sequence ran spec → decision → code, and the properties that were the model's
guesses are now the implementation's tests. Both sides are checked by the same names:

| Claim | Model | Twin |
|-------|-------|------|
| E-stop / power loss cuts the drive | `Inv_EStopHalts` | S9 |
| no inward motion unpowered | `P_NoAdvanceUnpowered` | `_run()` per-frame check |
| the pin relieves; no held mid-stroke | `P_PinRelieves` | S7 |
| the flush latch holds without power | `FailOpen` at `Flush` | S8 |
| release never resumes the sweep | `P_NoAutoRestart` | S9 |

---

## Findings

### F-1 — `CLEARED_HOLD` ignored both safety trips — **fixed, ADR-0022**

The first thing this model found, and the concrete argument for doing any of it: a
real defect in shipped logic that had survived both review and the scenario self-test.

`safety_interlock.gd`'s `CLEARED_HOLD` branch tested only `t >= hold_seconds` — it
never re-read SF1 or SF2. With the piston flush at the mouth, a safety-edge trip was
therefore not acted on until the dwell expired, **2.0 s** at the twin's default.

TLC reached it two ways: a spurious edge trip at flush (the shortest trace), and the
one that matters — someone reaches into the mouth (**H5**) at the exact position the
piston is completing to, and is held against the flush face for the rest of the dwell.
That is **H8**, the mouth-lip pinch, precisely where SF2 is supposed to act.

Bounded, not a crush: `Inv_NoCrush` held throughout — the piston never drove *past*
them, and contact stays at the SF2 cap (100 N, sourced from injury/biomechanical data
— see `docs/force_limit_injury_data.md`, ADR-0024).
The defect was in the *latency* of the response, not its existence. But SF2's
specified response is "immediate stop and reverse", and up to a full dwell is not
immediate.

**Why the scenario tests missed it.** Every hand-written scenario trips SF1 or SF2
*mid-sweep*, because that is the moment an author thinks of as dangerous. None of them
trips it while the pod is already closed — the state that intuitively reads as "safe,
nothing is moving". Exhaustive exploration has no such intuition.

Fixed by giving `CLEARED_HOLD` the same two trips `CLEARING` has. Now guarded three
ways: `Inv_NoTripHeldAtFlush` in `Safety.cfg`, scenario S6 in `test_interlock.gd`, and
the `hold-ignores-trips` mutant, which re-injects the exact pre-fix code so the guard
cannot rot silently.

No open findings.

---

## Why the mutation suite exists

A spec that passes proves nothing unless it *can* fail — a model with a typo in a
guard, or an invariant that is true by construction, passes just as greenly as a
correct one. `--mutants` injects eight real defects, most of them designs the ADRs
explicitly rejected, and **fails if TLC does not catch each one**.

| Mutant | Defect | Caught by |
|--------|--------|-----------|
| `sf1-ignored` | the FSM never consults life detection | `Inv_NoAdvanceWhileOccupied` |
| `fault-reads-clear` | a faulted channel stops failing safe | `Inv_NoAdvanceWhileOccupied` |
| `majority-vote` | 2-of-4 instead of "AND toward clear" | `Inv_NoAdvanceWhileOccupied` |
| `sf2-ignored` | the safety edge is never consulted | `Inv_NoSweepWhileContact`, and `Inv_NoCrush` independently |
| `self-locking-drive` | the drive holds position without power (FMEA F3) | `P_PinRelieves` |
| `auto-restart` | releasing the E-stop resumes the sweep | `P_NoAutoRestart` |
| `snap-home` | the piston teleports home instead of reversing | `P_NoTeleport` |
| `hold-ignores-trips` | `CLEARED_HOLD` stops re-reading the trips — *the pre-ADR-0022 defect verbatim* | `Inv_NoTripHeldAtFlush` |
| `frozen-sweep` | the machine never moves — safe but useless | `P_BagEventuallyCleared` |

Writing this suite is what caught the one weak check in the first draft:
`Inv_FaultMeansOccupied` was stated as `FaultOf(vote) ⇒ LifePresent`, which is true
by construction and checks nothing about the machine. It is now
`Inv_FaultMeansNoSweep`, stated over the FSM's state, and `fault-reads-clear` bites.

Mutations are `sed` expressions over the module text, so they are brittle by
construction — a mutation that no longer applies is reported as an `ERROR`, not
silently skipped.

---

## What this does *not* establish

- **No PL rating.** This is logic, not certified hardware. ISO 13849 PL e for SF1
  needs rated parts and a rated controller (ADR-0012) — untouched by any of this.
- **The model is hand-written.** It can drift from the GDScript. The correspondence
  table above is the mitigation; re-check it when either side changes.
- **Timing is abstracted.** Dropouts, races, stall detection and power-loss position
  live in the continuous layer this model deliberately collapses — that is roadmap
  [#3](https://github.com/StrayEddy/HiveCell/issues/3), and it stays open.
- **SF2 cannot fail here** (abstraction 5), so "SF2 backstops SF1" is proven while
  "SF2 is itself trustworthy" is not.
