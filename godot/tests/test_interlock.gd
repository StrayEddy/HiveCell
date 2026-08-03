extends SceneTree
## Headless self-test for the HiveCell safety interlock.
## Run:  Godot_v4.7.1 --headless --path godot --script res://tests/test_interlock.gd
## Exits 0 on pass, 1 on any failure (so it can gate CI / a pre-push check).
##
## The invariant that matters (docs/SAFETY.md): the clearing sweep must NEVER
## advance into the pod while anything alive is detected. Everything else is
## secondary. We also assert the safe path still WORKS (bag gets cleared), so a
## trivially-frozen mechanism can't pass.

const Interlock := preload("res://safety_interlock.gd")
const DT := 1.0 / 60.0

var failures: int = 0


func _fail(msg: String) -> void:
	failures += 1
	push_error("FAIL: " + msg)
	print("  FAIL: ", msg)


func _check(cond: bool, msg: String) -> void:
	if not cond:
		_fail(msg)


## Step `n` frames. Every frame, enforce the master invariant: if life is present
## at the start of the frame, progress must not increase across that frame, and
## the machine must not be in the advancing (CLEARING) state.
func _run(il, n: int, tag: String) -> void:
	for i in n:
		# Any safety trip -- SF1 life, SF2 contact-over-limit, or a drive with no
		# power (SF4) -- must prevent the sweep from advancing into the pod.
		var block_before: bool = il.life_present() or il.contact_over_limit \
			or not il.drive_powered()
		var p_before: float = il.progress
		il.step(DT)
		if block_before:
			_check(il.progress <= p_before + 1e-6,
				"%s: sweep ADVANCED while a safety trip was active (%.4f -> %.4f)" % [tag, p_before, il.progress])
			_check(not il.advancing(),
				"%s: entered CLEARING while a safety trip was active" % tag)


## Step until `want` is the current state, or `cap` frames pass. No invariant
## enforcement -- use _run() for that; this is just for getting somewhere.
func _advance_to(il, want: int, cap: int) -> bool:
	for i in cap:
		if il.state == want:
			return true
		il.step(DT)
	return il.state == want


## Step until the sweep is genuinely underway, at least `upto` into the stroke.
func _advance_to_sweep(il, upto: float) -> bool:
	for i in 2000:
		if il.state == Interlock.State.CLEARING and il.progress >= upto:
			return true
		il.step(DT)
	return false


func _new_il(demo := 1.0, hold := 0.2, dwell := 0.3):
	var il = Interlock.new()
	il.demo_seconds = demo      # short timings so the test runs fast
	il.hold_seconds = hold
	il.life_check_seconds = dwell
	return il


func _initialize() -> void:
	print("== HiveCell interlock self-test ==")

	# Scenario 1 -- empty pod, bag left behind: it MUST get cleared (liveness).
	var il1 = _new_il()
	il1.occupant_alive = false
	il1.bag_present = true
	_run(il1, 600, "S1 empty+bag")
	_check(not il1.bag_present, "S1: bag was never cleared in an empty pod")
	_check(il1.progress >= 0.99 or il1.state == Interlock.State.CLEARED_HOLD
		or il1.state == Interlock.State.REDEPLOY or il1.state == Interlock.State.AVAILABLE,
		"S1: cycle did not complete a sweep")

	# Scenario 2 -- occupant present the whole time: piston must NEVER move.
	var il2 = _new_il()
	il2.occupant_alive = true
	il2.bag_present = true
	_run(il2, 600, "S2 occupied")
	_check(il2.progress == 0.0, "S2: progress moved off 0 with an occupant present")
	_check(il2.state == Interlock.State.BLOCKED_OCCUPIED,
		"S2: did not park in BLOCKED_OCCUPIED (state=%d)" % il2.state)
	_check(il2.bag_present, "S2: bag cleared while occupied (must not happen)")

	# Scenario 3 -- someone appears MID-SWEEP: must stop advancing and reverse out.
	var il3 = _new_il()
	il3.occupant_alive = false
	il3.bag_present = true
	# advance until the sweep is genuinely underway
	while il3.state != Interlock.State.CLEARING or il3.progress < 0.3:
		il3.step(DT)
		if il3.progress >= 0.99:
			break
	_check(il3.state == Interlock.State.CLEARING and il3.progress >= 0.3,
		"S3: could not reach a mid-sweep state to test")
	var peak: float = il3.progress
	il3.occupant_alive = true            # life appears now
	_run(il3, 300, "S3 mid-sweep intrusion")   # _run enforces "never advances while life present"
	_check(il3.progress < peak + 1e-6, "S3: advanced past peak after intrusion")
	_check(il3.progress <= 0.001, "S3: did not fully reverse out after intrusion")
	_check(il3.bag_present, "S3: cleared the bag despite a mid-sweep intrusion")

	# Scenario 4 -- sensor fault with nobody there: must fail safe (no motion).
	var il4 = _new_il()
	il4.occupant_alive = false
	il4.sensor_fault = true
	il4.bag_present = true
	_run(il4, 600, "S4 sensor fault")
	_check(il4.progress == 0.0, "S4: moved despite a sensor fault (must fail safe)")
	_check(il4.state == Interlock.State.BLOCKED_OCCUPIED,
		"S4: fault did not block motion (state=%d)" % il4.state)

	# Scenario 5 -- SF1 BLIND, SF2 catches: life-detection misses the occupant
	# (occupant_alive stays false), but a contact-over-limit trip mid-sweep must
	# still stop and reverse. Proves SF2 is independent of SF1.
	var il5 = _new_il()
	il5.occupant_alive = false
	il5.bag_present = true
	while il5.state != Interlock.State.CLEARING or il5.progress < 0.3:
		il5.step(DT)
		if il5.progress >= 0.99:
			break
	_check(il5.state == Interlock.State.CLEARING and il5.progress >= 0.3,
		"S5: could not reach a mid-sweep state to test")
	var peak5: float = il5.progress
	il5.contact_over_limit = true          # safety edge fires; SF1 still says clear
	_run(il5, 300, "S5 SF2 contact trip")  # _run enforces "never advances while tripped"
	_check(il5.progress < peak5 + 1e-6, "S5: advanced past peak after SF2 trip")
	_check(il5.progress <= 0.001, "S5: did not reverse out after SF2 trip")

	# Scenario 6 -- a safety trip while the pod is CLOSED (flush) must reverse it
	# EARLY, not at the end of the hold dwell. The mouth-lip pinch (H8) lives at
	# exactly this position. Regression guard for finding F-1 (ADR-0022): before
	# the fix, CLEARED_HOLD re-read neither trip and held for the whole dwell.
	for trip in ["SF2 contact", "SF1 life"]:
		var il6 = _new_il(1.0, 2.0, 0.3)   # long hold: a late reverse is unmistakable
		il6.bag_present = true
		_check(_advance_to(il6, Interlock.State.CLEARED_HOLD, 1200),
			"S6 %s: never reached CLEARED_HOLD to test" % trip)
		_check(il6.progress >= 0.99, "S6 %s: not flush in CLEARED_HOLD" % trip)

		if trip == "SF2 contact":
			il6.contact_over_limit = true
		else:
			il6.occupant_alive = true
		il6.step(DT)
		_check(il6.state == Interlock.State.REDEPLOY,
			"S6 %s: stayed flush -- trip ignored during the hold dwell (F-1)" % trip)

		_run(il6, 300, "S6 %s reverse" % trip)
		_check(il6.progress <= 0.001, "S6 %s: did not reverse out after the trip" % trip)

	# Scenario 7 -- SF4 / FMEA F3 (ADR-0009): power lost MID-SWEEP must not sustain a
	# holding force. The stored-energy return element relieves the piston back to
	# deployed, and nothing advances while the drive is dead.
	var il7 = _new_il()
	il7.return_seconds = 0.5
	il7.bag_present = true
	_check(_advance_to_sweep(il7, 0.4), "S7: could not reach a mid-sweep state to test")
	var peak7: float = il7.progress
	il7.powered = false                    # blackout
	_run(il7, 600, "S7 power loss mid-sweep")
	_check(il7.progress < peak7 + 1e-6, "S7: advanced after power loss")
	_check(il7.state == Interlock.State.UNPOWERED, "S7: did not enter UNPOWERED")
	_check(il7.progress <= 0.001,
		"S7: pin did NOT relieve -- piston still held mid-stroke without power (F3)")

	# Scenario 8 -- SF4 at the FLUSH end: there the PASSIVE latch holds the pod closed
	# with zero power (security + zero standby). Safe because geometry puts no occupant
	# behind the piston (FMEA F5). The two behaviours must not be confused.
	var il8 = _new_il(1.0, 2.0, 0.3)
	il8.return_seconds = 0.5
	il8.bag_present = true
	_check(_advance_to(il8, Interlock.State.CLEARED_HOLD, 1200),
		"S8: never reached CLEARED_HOLD to test")
	il8.powered = false
	_run(il8, 600, "S8 blackout at flush")
	_check(il8.state == Interlock.State.UNPOWERED, "S8: did not enter UNPOWERED")
	_check(il8.progress >= 0.99,
		"S8: flush latch did not hold the pod closed without power")

	# Scenario 9 -- the EXTERNAL E-stop (ADR-0023) is a Category 0 stop: it cuts drive
	# power, taking the same fail-open path. Releasing it must NOT resume the sweep --
	# the machine backs out and re-enters through LIFE_CHECK.
	var il9 = _new_il()
	il9.return_seconds = 0.5
	il9.bag_present = true
	_check(_advance_to_sweep(il9, 0.4), "S9: could not reach a mid-sweep state to test")
	il9.estop = true
	il9.step(DT)
	_check(il9.state == Interlock.State.UNPOWERED, "S9: E-stop did not cut the drive")
	var peak9: float = il9.progress
	il9.estop = false                      # operator releases the button
	il9.step(DT)
	_check(il9.state != Interlock.State.CLEARING,
		"S9: sweep RESUMED on E-stop release (must re-enter via LIFE_CHECK)")
	_check(il9.progress <= peak9 + 1e-6, "S9: advanced on E-stop release")
	_check(il9.state == Interlock.State.REDEPLOY or il9.state == Interlock.State.AVAILABLE,
		"S9: recovered into an unexpected state (must back out, not resume)")

	if failures == 0:
		print("PASS: all interlock scenarios held (sweep never advanced against a safety trip).")
		quit(0)
	else:
		print("FAILED: %d assertion(s)." % failures)
		quit(1)
