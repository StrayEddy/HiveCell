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
		var life_before: bool = il.life_present()
		var p_before: float = il.progress
		il.step(DT)
		if life_before:
			_check(il.progress <= p_before + 1e-6,
				"%s: sweep ADVANCED while life present (%.4f -> %.4f)" % [tag, p_before, il.progress])
			_check(not il.advancing(),
				"%s: entered CLEARING while life present" % tag)


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

	if failures == 0:
		print("PASS: all interlock scenarios held (sweep never advanced against life).")
		quit(0)
	else:
		print("FAILED: %d assertion(s)." % failures)
		quit(1)
