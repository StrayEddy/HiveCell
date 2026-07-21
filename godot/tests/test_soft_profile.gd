extends SceneTree
## Headless self-test for the SF5 soft motion profile (soft_profile.gd).
## Run:  Godot --headless --path godot --script res://tests/test_soft_profile.gd
## Exits 0 on pass, 1 on any failure.
##
## Checks the SHAPE holds: soft-start and soft-stop are slower than cruise, the
## final approach is speed-limited, motion is monotonic and completes, and the
## whole sweep still takes ~the requested duration.

const Profile := preload("res://soft_profile.gd")
const DT := 1.0 / 60.0

var failures := 0


func _check(cond: bool, msg: String) -> void:
	if not cond:
		failures += 1
		push_error("FAIL: " + msg)
		print("  FAIL: ", msg)


func _initialize() -> void:
	print("== HiveCell soft-profile self-test ==")
	var sp = Profile.new()

	# Shape: start & stop slower than cruise; approach speed-limited.
	var v_start: float = sp.velocity(0.02)
	var v_cruise: float = sp.velocity(0.5)
	var v_approach: float = sp.velocity(1.0 - sp.approach_frac * 0.5)
	var v_end: float = sp.velocity(0.999)
	_check(v_cruise > 0.95, "cruise velocity should be ~1.0 (got %.2f)" % v_cruise)
	_check(v_start < v_cruise, "soft-start should be slower than cruise (%.2f vs %.2f)" % [v_start, v_cruise])
	_check(v_approach <= sp.approach_ratio + 1e-6,
		"final approach should be <= approach_ratio (%.2f vs %.2f)" % [v_approach, sp.approach_ratio])
	_check(v_approach < v_cruise, "approach should be slower than cruise")
	_check(v_end < v_approach + 1e-6, "soft-stop should be slowest near the end (%.2f)" % v_end)

	# Monotonic + completes, and total time ~ duration.
	var duration := 4.0
	var p := 0.0
	var elapsed := 0.0
	var last := -1.0
	var steps := 0
	while p < 1.0 and steps < 100000:
		last = p
		p = sp.advance(p, DT, duration)
		_check(p >= last - 1e-9, "progress must be monotonic non-decreasing")
		elapsed += DT
		steps += 1
	_check(p >= 1.0, "sweep must complete (reached %.3f)" % p)
	_check(absf(elapsed - duration) < 0.5 * duration,
		"total time ~ duration (got %.2fs for %.2fs target)" % [elapsed, duration])

	if failures == 0:
		print("PASS: soft profile shape, monotonicity, completion, and timing hold.")
		quit(0)
	else:
		print("FAILED: %d assertion(s)." % failures)
		quit(1)
