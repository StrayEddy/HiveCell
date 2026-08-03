extends RefCounted
class_name SafetyInterlock
## Pure, headless-testable safety state machine for the HiveCell clearing cycle.
## No scene/visual dependencies, so it can be unit-tested without a viewport.
##
## THE RULE (see docs/SAFETY.md): the piston may only advance a clearing sweep
## when life-detection positively proves the pod empty. Any life signal, or any
## sensor fault, means "assume occupied" -> no advancing motion. The sweep is for
## INANIMATE items only; a living thing present => hold still (+ alert a human on
## real hardware). The only motion permitted while life is present is REVERSING
## back to the safe deployed position.

enum State { AVAILABLE, LIFE_CHECK, CLEARING, CLEARED_HOLD, REDEPLOY, BLOCKED_OCCUPIED,
	UNPOWERED }
enum SignalLevel { READY, MOVING, CLOSED, ALARM }   # green / red / orange / flashing red

var profile := SoftProfile.new()    # SF5 soft velocity profile (shapes the sweep)

## SF1 occupancy fusion (ADR-0012). When set, life_present() consults the
## diverse-redundant, fail-safe voter instead of the simplified ground-truth
## fields below. Left null in the pure-logic interlock tests (which drive
## occupant_alive / sensor_fault directly). The twin attaches a real suite.
var fusion: OccupancyFusion = null

# --- tuning ---
var demo_seconds := 8.0
var hold_seconds := 2.0
var life_check_seconds := 1.5

## Duration of the UNPOWERED return stroke, driven by the stored-energy return
## element rather than the drive. PLACEHOLDER: the real rate is spring force
## minus seal drag, and seal drag is the project's master unknown (ADR-0011,
## issue #9). Only the DIRECTION and the fact that it completes are claimed here.
var return_seconds := 4.0

# --- simulated sensor inputs (ground truth the twin/test drives) ---
var occupant_alive := false   ## a living person/animal is inside right now
var sensor_fault := false     ## a faulted/unknown sensor (must fail safe)
var bag_present := true        ## an inanimate item left behind (owned here once running)
var contact_over_limit := false  ## SF2: measured contact force exceeded the safe
                                 ## limit (a non-yielding obstruction / crush). An
                                 ## independent trip from SF1 life-detection.
var powered := true       ## drive power present
var estop := false        ## EXTERNAL / operator E-stop asserted. Not occupant-facing:
                          ## ADR-0009 rejects any interior release as a vandalism
                          ## surface in unattended public units.

# --- state ---
var state: int = State.AVAILABLE
var progress := 0.0            ## 0 = deployed (available), 1 = swept (flush)
var t := 0.0                   ## time in current state
var clear_dwell := 0.0         ## how long the life-check has read "no life"
var reverse_from := 0.0        ## progress captured when a reverse begins


## Fail-safe voting: diverse channels (radar vitals, thermal, CO2, load-cell BCG)
## OR toward life. In the twin/test all read the simulated ground truth; on real
## hardware this is an OR across independent sensor outputs. A fault reads occupied.
func life_present() -> bool:
	if fusion != null:
		return fusion.occupied()
	if sensor_fault:
		return true
	return occupant_alive


## True while the sweep is advancing INTO the pod (progress increasing). This is
## the motion that must never happen while life is present.
func advancing() -> bool:
	return state == State.CLEARING


## SF4 (ADR-0009): the drive can only move the piston when powered AND not
## e-stopped. An E-stop is a Category 0 stop -- it REMOVES drive power rather than
## commanding a halt, so it takes the same fail-open path as a blackout and cannot
## itself become a way to sustain a pin (ADR-0023).
func drive_powered() -> bool:
	return powered and not estop


## SF5 signalling: green = ready to occupy, red = about to move / moving,
## orange = closed (flush), flashing red = occupied + refusing to move (alarm).
func signal_level() -> int:
	match state:
		State.AVAILABLE:
			return SignalLevel.READY     # green: deployed, ready to occupy
		State.CLEARED_HOLD:
			return SignalLevel.CLOSED     # orange: closed / flush
		State.BLOCKED_OCCUPIED, State.UNPOWERED:
			return SignalLevel.ALARM      # flashing red: refusing to run, alert human
		_:
			return SignalLevel.MOVING     # red: about to move or moving


func step(delta: float) -> void:
	t += delta
	if fusion != null:
		# Age the sensor channels; unrefreshed => stale => occupied. Deliberately
		# still ticked while unpowered: no power means no sampling, so the suite
		# goes stale and the pod must re-prove itself empty before it can move.
		fusion.tick(delta)
	if not drive_powered():
		_fail_open(delta)
		return
	if state == State.UNPOWERED:
		_recover()
		return
	match state:
		State.AVAILABLE:
			# Pod in use. Session end never moves blindly: life-check first.
			progress = 0.0
			if t >= hold_seconds:
				clear_dwell = 0.0
				_goto(State.LIFE_CHECK)
		State.LIFE_CHECK:
			# Must read "no life" continuously for the whole dwell to unlock -- and
			# never start a sweep while the safety edge (SF2) is already tripped.
			if life_present():
				_goto(State.BLOCKED_OCCUPIED)
			elif contact_over_limit:
				clear_dwell = 0.0   # safety edge active: hold, don't begin moving
			else:
				clear_dwell += delta
				if clear_dwell >= life_check_seconds:
					_goto(State.CLEARING)
		State.CLEARING:
			# Two independent trips STOP and REVERSE mid-sweep, reversing from the
			# CURRENT position (never snap forward first):
			#   SF1 - life detected;  SF2 - contact force over the safe limit.
			if life_present() or contact_over_limit:
				reverse_from = progress
				_goto(State.REDEPLOY)
			else:
				progress = profile.advance(progress, delta, demo_seconds)  # SF5 soft
				if progress >= 1.0:
					bag_present = false
					_goto(State.CLEARED_HOLD)
		State.CLEARED_HOLD:
			# Closed and flush. Either trip reverses EARLY instead of waiting out
			# the dwell: the mouth-lip pinch (H8) sits exactly at this position,
			# so SF2's "immediate stop and reverse" has to mean immediate here
			# too. Reversing is the safe direction, so an early exit is never
			# worse than the dwell -- at most it costs availability on a spurious
			# read. (ADR-0022; found by model checking, spec/README.md F-1.)
			progress = 1.0
			if life_present() or contact_over_limit or t >= hold_seconds:
				reverse_from = progress
				_goto(State.REDEPLOY)
		State.REDEPLOY:
			# Reverse to the safe deployed position from wherever the sweep was.
			# Allowed even with life present (moving AWAY is the safe direction).
			# Soft profile applied along the reverse stroke (SF5).
			var span := maxf(reverse_from, 0.0001)
			var r := (reverse_from - progress) / span   # 0..1 along the reverse
			r = profile.advance(r, delta, demo_seconds)
			progress = clampf(reverse_from * (1.0 - r), 0.0, 1.0)
			if progress <= 0.001:
				progress = 0.0
				_goto(State.AVAILABLE)
		State.BLOCKED_OCCUPIED:
			# Hold still, alert a human. Re-verify only once it reads clear again.
			progress = 0.0
			if not life_present():
				clear_dwell = 0.0
				_goto(State.LIFE_CHECK)


## SF4 fail-open drive (ADR-0009) -- the answer to FMEA F3, the failure that drove
## the whole decision: losing drive power must NEVER sustain a holding force, because
## once power is gone nothing can detect or act. Behaviour is POSITION-DEPENDENT:
##
##   * occupant zone (anywhere short of flush) -- the stored-energy return element
##     drives the piston back toward deployed, so a mis-detected pin relieves with no
##     accessible part and no occupant action. Passive back-drive ALONE is NOT enough:
##     `scripts/pin_relief.py` shows it stalls at the seal drag, flooring the residual
##     pin at ~1.2 kN (~10x a safe force), which is exactly why ADR-0009 requires the
##     ~1.5 kN return element modelled here.
##   * flush end -- the PASSIVE latch holds the pod closed with zero power (security,
##     vandal resistance, zero standby). Safe because the piston only ever sweeps
##     TOWARD the mouth, so no occupant can be behind it there (FMEA F5).
func _fail_open(delta: float) -> void:
	if state != State.UNPOWERED:
		_goto(State.UNPOWERED)
	if progress >= 1.0 - 0.000001:
		return    # passive flush latch: holds closed, needs no power
	progress = maxf(progress - delta / maxf(return_seconds, 0.0001), 0.0)


## Drive power restored, or the E-stop released. This must NEVER resume the sweep:
## the machine backs out to deployed and re-enters the cycle from the top, so a fresh
## life-check has to pass before anything advances again. (At the flush end a powered
## solenoid releases the passive latch first, ADR-0009.)
func _recover() -> void:
	if progress <= 0.001:
		progress = 0.0
		_goto(State.AVAILABLE)
	else:
		reverse_from = progress
		_goto(State.REDEPLOY)


func _goto(s: int) -> void:
	state = s
	t = 0.0
