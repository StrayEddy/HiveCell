--------------------------- MODULE HiveCellInterlock ---------------------------
(***************************************************************************)
(* Formal model of the HiveCell safety interlock  --  roadmap item #1.     *)
(*                                                                         *)
(* Machine-proves the headline safety claims over ALL reachable states,    *)
(* rather than the hand-written scenarios in godot/tests/test_interlock.gd.*)
(*                                                                         *)
(* Models, together:                                                       *)
(*   - the clearing-cycle state machine   (godot/safety_interlock.gd)      *)
(*   - the diverse-redundant SF1 voter    (godot/occupancy_fusion.gd)      *)
(*   - the SF2 contact trip / safety edge (safety_interlock.gd)            *)
(*   - the external E-stop + SF4 fail-open drive (docs/SAFETY.md, ADR-0009)*)
(*   - a GROUND-TRUTH occupant, so the FMEA F1 -> F2 defence-in-depth      *)
(*     chain (SF1 blind, SF2 catches) is proven rather than asserted.      *)
(*                                                                         *)
(* The E-stop and fail-open parts have NO implementation in the twin yet   *)
(* -- the model runs ahead of the code there. See spec/README.md for the   *)
(* full model <-> code correspondence table, the abstractions, and the     *)
(* open findings.                                                          *)
(***************************************************************************)
EXTENDS Integers, FiniteSets

CONSTANTS
    Steps,        \* piston travel discretised into 0..Steps (0 = deployed, Steps = flush)
    DwellTicks,   \* consecutive "no life" ticks needed to unlock  (life_check_seconds)
    HoldTicks,    \* ticks held in AVAILABLE / CLEARED_HOLD        (hold_seconds)
    EnvKind       \* "ADVERSARIAL" | "BENIGN" | "BLACKOUT" -- see the .cfg files

Votes    == {"CLEAR", "OCCUPIED", "FAULT"}

\* ADR-0012 diverse suite. Different physics per channel, so no single
\* common-cause failure can blind the whole suite.
Channels == {"radar_vitals", "thermal_ir", "ndir_co2", "load_bcg"}

\* The six states of safety_interlock.gd, plus UNPOWERED (spec-only, see README).
FsmStates == {"AVAILABLE", "LIFE_CHECK", "CLEARING", "CLEARED_HOLD",
              "REDEPLOY", "BLOCKED_OCCUPIED", "UNPOWERED"}

VARIABLES
    state,      \* current FSM state
    progress,   \* piston position, 0 = deployed (pod open) .. Steps = flush (closed)
    dwell,      \* clear_dwell: how long the life-check has read "no life"
    hold,       \* t: time in the current state (saturating, see README)
    vote,       \* [Channels -> Votes] -- what each diverse sensor channel reports
    contact,    \* SF2: measured contact force over the safe cap (safety edge tripped)
    estop,      \* external / operator E-stop asserted (ADR-0009: NOT occupant-facing)
    powered,    \* drive power present
    bag,        \* an inanimate item is still in the pod -- the liveness witness
    occupant,   \* GROUND TRUTH: a living person really is in the pod
    occPos      \* where they are, as a piston position -- contact happens here

vars == <<state, progress, dwell, hold, vote, contact, estop, powered, bag,
          occupant, occPos>>

Deployed == 0        \* pod fully open, piston back
Flush    == Steps    \* pod fully closed, piston at the mouth

Min(a, b) == IF a < b THEN a ELSE b
Max(a, b) == IF a > b THEN a ELSE b

-----------------------------------------------------------------------------
(*              SF1 -- what "occupied" MEANS, vs what the FSM READS         *)
(*                                                                         *)
(* These two are deliberately kept as separate operators even though they  *)
(* are equal in the unmutated model:                                       *)
(*                                                                         *)
(*   LifeOf  -- the SPECIFICATION of occupancy. Only the invariants use it.*)
(*   Verdict -- the MECHANISM the state machine consults. Only the FSM     *)
(*              actions use it.                                            *)
(*                                                                         *)
(* Splitting them is what makes the mutation suite meaningful: a defect    *)
(* injected into Verdict cannot silently weaken the invariant that is      *)
(* supposed to catch it. Do not collapse them. `Edge` plays the same role  *)
(* for SF2: the safety-edge reading as the FSM consults it.                *)
(***************************************************************************)

\* occupancy_fusion.gd `occupied()` -- ADR-0012 fail-safe voting:
\*   OR toward life   -- ANY channel reading presence/life  => occupied
\*   fault = occupied -- ANY faulted / stale channel        => occupied
\*   AND toward clear -- "empty" ONLY when EVERY channel reads CLEAR
\* i.e. absence of proof-of-emptiness is never treated as empty.
LifeOf(v)  == \E c \in Channels : v[c] # "CLEAR"

Verdict(v) == \E c \in Channels : v[c] # "CLEAR"     \* MUTATION TARGET (SF1)

\* SF2 safety edge as the FSM consults it.
Edge(ct)   == ct                                     \* MUTATION TARGET (SF2)

FaultOf(v) == \E c \in Channels : v[c] = "FAULT"

\* The drive can only move the piston when powered AND not e-stopped.
\* Per ADR-0009 the E-stop cuts drive power, so it inherits SF4 fail-open.
DriveOf(es, pw) == pw /\ ~es

LifePresent  == LifeOf(vote)
DrivePowered == DriveOf(estop, powered)

\* The safety edge is physically against the occupant right now.
Touching == occupant /\ progress >= occPos

TypeOK ==
    /\ state    \in FsmStates
    /\ progress \in Deployed..Flush
    /\ dwell    \in 0..DwellTicks
    /\ hold     \in 0..HoldTicks
    /\ vote     \in [Channels -> Votes]
    /\ contact  \in BOOLEAN
    /\ estop    \in BOOLEAN
    /\ powered  \in BOOLEAN
    /\ bag      \in BOOLEAN
    /\ occupant \in BOOLEAN
    /\ occPos   \in 1..Steps

Init ==
    /\ state    = "AVAILABLE"     \* boots deployed / open / available
    /\ progress = Deployed
    /\ dwell    = 0
    /\ hold     = 0
    /\ vote     = [c \in Channels |-> "CLEAR"]
    /\ contact  = FALSE
    /\ estop    = FALSE
    /\ powered  = TRUE
    /\ bag      = TRUE            \* something inanimate to clear
    /\ occupant = FALSE
    /\ occPos   = Steps

-----------------------------------------------------------------------------
(***************************************************************************)
(*                     SF4 -- fail-open drive (ADR-0009)                   *)
(*                                                                         *)
(* Power loss (or an E-stop, which cuts drive power) must NOT sustain a    *)
(* holding force -- FMEA F3, the driver for the whole SF4 decision.        *)
(* Behaviour is POSITION-DEPENDENT:                                        *)
(*   - anywhere in the occupant zone (progress < Flush): the stored-energy *)
(*     return element drives the piston back toward deployed, so a         *)
(*     mis-detected pin relieves passively;                                *)
(*   - at the flush end: the PASSIVE latch holds it closed with zero       *)
(*     power. Safe because geometry (FMEA F5) puts no occupant there.      *)
(***************************************************************************)
FailOpen(es, pw) ==
    /\ ~DriveOf(es, pw)
    /\ state'    = "UNPOWERED"
    /\ progress' = IF progress = Flush
                     THEN Flush                        \* passive flush latch holds
                     ELSE Max(progress - 1, Deployed)  \* return element relieves the pin
    /\ dwell'    = 0
    /\ hold'     = 0
    /\ UNCHANGED bag

(***************************************************************************)
(* Recovery from an unpowered / e-stopped state. A restored supply or a    *)
(* released E-stop must NEVER resume the sweep: the machine returns to     *)
(* deployed and re-enters the cycle through LIFE_CHECK from the top.       *)
(***************************************************************************)
Recover(es, pw) ==
    /\ DriveOf(es, pw)
    /\ state  = "UNPOWERED"
    /\ state' = IF progress = Deployed THEN "AVAILABLE" ELSE "REDEPLOY"
    /\ UNCHANGED <<progress, bag>>
    /\ dwell' = 0
    /\ hold'  = 0

-----------------------------------------------------------------------------
(*                        The normal clearing cycle                        *)

\* Pod in use. A session never ends by moving blindly -- life-check first.
Available ==
    /\ state = "AVAILABLE"
    /\ progress' = Deployed
    /\ IF hold + 1 >= HoldTicks
         THEN /\ state' = "LIFE_CHECK"
              /\ hold'  = 0
              /\ dwell' = 0
         ELSE /\ state' = "AVAILABLE"
              /\ hold'  = hold + 1
              /\ dwell' = dwell
    /\ UNCHANGED bag

\* Must read "no life" CONTINUOUSLY for the whole dwell to unlock, and must
\* never begin a sweep while the SF2 safety edge is already tripped.
LifeCheck(v, ct) ==
    /\ state = "LIFE_CHECK"
    /\ UNCHANGED <<progress, bag>>
    /\ \/ /\ Verdict(v)                       \* SF1: any life or any fault
          /\ state' = "BLOCKED_OCCUPIED"
          /\ dwell' = 0
          /\ hold'  = 0
       \/ /\ ~Verdict(v)
          /\ Edge(ct)                         \* SF2 already tripped: hold, don't start
          /\ state' = "LIFE_CHECK"
          /\ dwell' = 0
          /\ hold'  = Min(hold + 1, HoldTicks)
       \/ /\ ~Verdict(v)
          /\ ~Edge(ct)
          /\ IF dwell + 1 >= DwellTicks
               THEN /\ state' = "CLEARING"
                    /\ dwell' = 0
                    /\ hold'  = 0
               ELSE /\ state' = "LIFE_CHECK"
                    /\ dwell' = dwell + 1
                    /\ hold'  = Min(hold + 1, HoldTicks)

\* THE motion that must never happen while life is present. Two INDEPENDENT
\* trips stop and reverse mid-sweep, from the CURRENT position (never snap
\* forward first): SF1 life detected, SF2 contact force over the safe cap.
Clearing(v, ct) ==
    /\ state = "CLEARING"
    /\ \/ /\ Verdict(v) \/ Edge(ct)
          /\ state' = "REDEPLOY"
          /\ UNCHANGED <<progress, bag>>
          /\ dwell' = 0
          /\ hold'  = 0
       \/ /\ ~Verdict(v)
          /\ ~Edge(ct)
          /\ progress' = Min(progress + 1, Flush)
          /\ IF progress + 1 >= Flush
               THEN /\ state' = "CLEARED_HOLD"
                    /\ bag'   = FALSE          \* the sweep did its job
                    /\ dwell' = 0
                    /\ hold'  = 0
               ELSE /\ state' = "CLEARING"
                    /\ UNCHANGED bag
                    /\ dwell' = dwell
                    /\ hold'  = Min(hold + 1, HoldTicks)

\* Closed and flush; dwell, then reverse back out to deployed. EITHER trip cuts
\* the dwell short -- the mouth-lip pinch (H8) is at exactly this position, so
\* SF2 must act now rather than when the timer expires (ADR-0022).
ClearedHold(v, ct) ==
    /\ state = "CLEARED_HOLD"
    /\ progress' = Flush
    /\ UNCHANGED bag
    /\ dwell' = 0
    /\ IF Verdict(v) \/ Edge(ct) \/ hold + 1 >= HoldTicks
         THEN /\ state' = "REDEPLOY"
              /\ hold'  = 0
         ELSE /\ state' = "CLEARED_HOLD"
              /\ hold'  = hold + 1

\* Reverse to the safe deployed position from wherever the sweep was.
\* Permitted even with life present: moving AWAY is the safe direction.
Redeploy ==
    /\ state = "REDEPLOY"
    /\ progress' = Max(progress - 1, Deployed)
    /\ UNCHANGED bag
    /\ dwell' = 0
    /\ IF progress - 1 <= Deployed
         THEN /\ state' = "AVAILABLE"
              /\ hold'  = 0
         ELSE /\ state' = "REDEPLOY"
              /\ hold'  = Min(hold + 1, HoldTicks)

\* Hold still and alert a human. Re-verify only once it reads clear again.
BlockedOccupied(v) ==
    /\ state = "BLOCKED_OCCUPIED"
    /\ progress' = Deployed
    /\ UNCHANGED bag
    /\ \/ /\ ~Verdict(v)
          /\ state' = "LIFE_CHECK"
          /\ dwell' = 0
          /\ hold'  = 0
       \/ /\ Verdict(v)
          /\ state' = "BLOCKED_OCCUPIED"
          /\ dwell' = 0
          /\ hold'  = Min(hold + 1, HoldTicks)

\* One powered frame of safety_interlock.gd `step(delta)`.
Powered(v, ct, es, pw) ==
    /\ DriveOf(es, pw)
    /\ \/ Available
       \/ LifeCheck(v, ct)
       \/ Clearing(v, ct)
       \/ ClearedHold(v, ct)
       \/ Redeploy
       \/ BlockedOccupied(v)

-----------------------------------------------------------------------------
(*                            The environment                              *)

(***************************************************************************)
(* Who is in the pod. A person may walk in, or reach in mid-sweep (H5),    *)
(* but only ever AHEAD of the piston face -- geometry (FMEA F5) means no   *)
(* one can be behind it. They may leave at any time. While present they    *)
(* stay put.                                                               *)
(***************************************************************************)
OccupancyOK(occ, op) ==
    \/ /\ ~occ
       /\ op = Steps                          \* canonical value when nobody is in
    \/ /\ occ /\ occupant /\ op = occPos      \* the same person, still there
    \/ /\ occ /\ ~occupant /\ op > progress   \* enters / reaches in, ahead of the face

(***************************************************************************)
(* The SF2 safety edge. It MUST read contact when the face is against the  *)
(* occupant (that is what a pressure-sensitive edge is for). It is free    *)
(* otherwise -- yielding trash, or a spurious trip, both allowed.          *)
(* Note this constrains only the edge; the SF1 channels stay entirely      *)
(* free, so "all four blind with a person inside" (FMEA F1) is reachable.  *)
(***************************************************************************)
SafetyEdgeOK(occ, op, ct) == (occ /\ progress >= op) => ct

(***************************************************************************)
(* What the world is allowed to do to the machine, per .cfg:               *)
(*                                                                         *)
(*  ADVERSARIAL -- unconstrained. Every channel may read anything, the     *)
(*                 edge may trip, the E-stop may be hit and released,      *)
(*                 power may drop and return, people may come and go, at   *)
(*                 every tick. This is the environment the SAFETY claims   *)
(*                 are proven under.                                       *)
(*  BENIGN      -- nothing wrong ever: pod empty, all channels positively  *)
(*                 clear, no contact, powered, no E-stop. Used to prove    *)
(*                 LIVENESS -- that a frozen machine cannot pass.          *)
(*  BLACKOUT    -- FMEA F3 exactly: SF1 completely blind (all channels     *)
(*                 read CLEAR) with a real occupant inside, and power that *)
(*                 may fail at any moment and never returns. Used to prove *)
(*                 the SF4 pin actually relieves.                          *)
(***************************************************************************)
EnvAllows(v, ct, es, pw, occ) ==
    CASE EnvKind = "ADVERSARIAL" -> TRUE
      [] EnvKind = "BENIGN"      -> /\ \A c \in Channels : v[c] = "CLEAR"
                                    /\ ~ct /\ ~es /\ pw /\ ~occ
      [] EnvKind = "BLACKOUT"    -> /\ \A c \in Channels : v[c] = "CLEAR"
                                    /\ ~es
                                    /\ (pw => powered)   \* power loss is permanent
      [] OTHER                   -> FALSE

(***************************************************************************)
(* One tick. The environment moves and the machine steps ATOMICALLY, which *)
(* mirrors safety_interlock.gd: step() reads the sensor fields as they     *)
(* stand at the instant it runs. So the primed sensor values are exactly   *)
(* the ones this transition's decision was made on.                        *)
(***************************************************************************)
Tick ==
    \E v \in [Channels -> Votes], ct \in BOOLEAN, es \in BOOLEAN,
       pw \in BOOLEAN, occ \in BOOLEAN, op \in 1..Steps :
        /\ OccupancyOK(occ, op)
        /\ SafetyEdgeOK(occ, op, ct)
        /\ EnvAllows(v, ct, es, pw, occ)
        /\ vote' = v /\ contact' = ct /\ estop' = es /\ powered' = pw
        /\ occupant' = occ /\ occPos' = op
        /\ \/ FailOpen(es, pw)
           \/ Recover(es, pw)
           \/ Powered(v, ct, es, pw)

Next == Tick

Spec == Init /\ [][Next]_vars /\ WF_vars(Tick)

-----------------------------------------------------------------------------
(*                       SAFETY INVARIANTS (state)                         *)

\* THE headline claim (docs/SAFETY.md SF1, hazards H1/H6): the clearing sweep
\* is never underway while ANY life signal -- or any sensor fault -- is present.
Inv_NoAdvanceWhileOccupied ==
    (state = "CLEARING") => ~LifePresent

\* ADR-0012 "AND toward clear": a sweep runs only when EVERY diverse channel
\* positively reads CLEAR. One clear channel can never unlock on its own.
Inv_SweepNeedsAllChannelsClear ==
    (state = "CLEARING") => (\A c \in Channels : vote[c] = "CLEAR")

\* Fail-safe: a faulted / stale / out-of-range channel must stop the machine
\* sweeping, exactly as a positive life reading would. Stated about the
\* MACHINE, not about the definitions -- "FaultOf => LifeOf" would be true by
\* construction and would check nothing.
Inv_FaultMeansNoSweep ==
    FaultOf(vote) => (state # "CLEARING")

\* SF2 is independent of SF1: the safety edge alone also forbids a sweep.
Inv_NoSweepWhileContact ==
    (state = "CLEARING") => ~contact

\* E-stop or power loss => the machine is in its fail-open state, not driving.
Inv_EStopHalts ==
    (estop \/ ~powered) => (state = "UNPOWERED")

\* Refusing to move means actually standing still, at the open/deployed end.
Inv_BlockedIsStill ==
    (state = "BLOCKED_OCCUPIED") => (progress = Deployed)

(***************************************************************************)
(* DEFENCE IN DEPTH -- the FMEA F1 -> F2 chain, over ground truth.         *)
(*                                                                         *)
(* The piston never drives PAST a real occupant, even when all four SF1    *)
(* channels are blind (F1: "SF1 reads false-empty"). It reaches them, the  *)
(* SF2 edge trips, and it reverses -- so contact is bounded at the safe    *)
(* cap instead of becoming a crush. This is the claim that scenario S5 in  *)
(* test_interlock.gd checks at ONE hand-picked position; here it holds for *)
(* every occupant position and every reachable state.                      *)
(***************************************************************************)
Inv_NoCrush ==
    occupant => (progress <= occPos)

(***************************************************************************)
(* ADR-0022, and the regression guard for what was finding F-1.            *)
(*                                                                         *)
(* The machine is never sitting closed-and-flush while EITHER trip is       *)
(* asserted. Before the fix, CLEARED_HOLD re-read neither, so a safety-edge *)
(* trip at the mouth lip (H8) went unacted-on for the whole hold dwell --   *)
(* TLC found it; `test_interlock.gd` S6 now guards the same thing, and the  *)
(* `hold-ignores-trips` mutant proves this invariant still bites.           *)
(***************************************************************************)
Inv_NoTripHeldAtFlush ==
    (LifePresent \/ contact) => (state # "CLEARED_HOLD")

-----------------------------------------------------------------------------
(*                     SAFETY PROPERTIES (transitions)                     *)
(*                                                                         *)
(* State invariants cannot express "the piston did not MOVE inward", which *)
(* is the real claim. These are action properties over each tick, and they *)
(* are the direct formal analogue of the per-frame assertion in            *)
(* godot/tests/test_interlock.gd `_run()`.                                 *)

\* No inward motion on any tick whose life reading says occupied.
P_NoAdvanceUnderLife ==
    [][ LifeOf(vote') => progress' <= progress ]_vars

\* No inward motion on any tick whose safety edge is tripped (SF2, independent).
P_NoAdvanceUnderContact ==
    [][ contact' => progress' <= progress ]_vars

\* No inward motion without drive power -- an unpowered drive cannot close.
P_NoAdvanceUnpowered ==
    [][ ~DriveOf(estop', powered') => progress' <= progress ]_vars

\* The piston never teleports: one discrete step per tick, in either direction.
\* Catches a state that resets progress instead of reversing through it.
P_NoTeleport ==
    [][ progress' - progress \in {-1, 0, 1} ]_vars

\* Restoring power or releasing the E-stop must not resume the sweep. From
\* UNPOWERED the only exits are "stay", "back out", or "available" -- never
\* straight back into CLEARING.
P_NoAutoRestart ==
    [][ (state = "UNPOWERED")
          => (state' \in {"UNPOWERED", "REDEPLOY", "AVAILABLE"}) ]_vars

-----------------------------------------------------------------------------
(*                        LIVENESS  (BENIGN / BLACKOUT)                    *)

\* Under a benign environment the machine actually WORKS: the inanimate item
\* left behind really does get cleared. Without this a machine frozen solid
\* would satisfy every safety property above.
P_BagEventuallyCleared == <>(~bag)

\* ...and the cycle returns to service rather than parking closed forever.
P_ReturnsToService == []<>(state = "AVAILABLE")

\* SF4 / FMEA F3: with power gone, the piston never rests pinned mid-stroke.
\* It relieves to deployed, or sits latched at flush where no occupant can be.
P_PinRelieves ==
    [] (~powered => <>(progress = Deployed \/ progress = Flush))

=============================================================================
