extends SceneTree
## Headless self-test for SF1 occupancy fusion (ADR-0012).
## Run:  Godot_v4.7.1 --headless --path godot --script res://tests/test_occupancy_fusion.gd
## Exits 0 on pass, 1 on any failure (so it can gate CI / a pre-push check).
##
## The invariant that matters (ADR-0012 / docs/SAFETY.md): the suite reports "empty"
## ONLY when EVERY diverse channel positively reads clear. Any presence/life on any
## channel, and any faulted/stale/out-of-range channel, must read OCCUPIED. Absence
## of proof-of-emptiness is never "empty". We also assert the all-clear case DOES
## read empty, so a trivially-stuck-occupied voter can't pass.

const Fusion := preload("res://occupancy_fusion.gd")
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


## A suite with every channel healthy, fresh, and reading clear (the ONLY unlock).
func _all_clear_suite() -> OccupancyFusion:
	var f := OccupancyFusion.new()
	for c in f.channels:
		c.present = false
		c.healthy = true
		c.plausible = true
		c.age = 0.0
	return f


func _initialize() -> void:
	print("== HiveCell SF1 occupancy-fusion self-test ==")

	# Baseline -- all channels clear & healthy => empty (liveness: it CAN unlock).
	var base = _all_clear_suite()
	_check(base.all_clear(), "baseline: all-clear suite did not read empty (would never unlock)")

	# OR toward life -- each single channel reading presence forces occupied.
	for name in ["radar_vitals", "thermal_ir", "ndir_co2", "load_bcg"]:
		var f = _all_clear_suite()
		f.get_channel(name).present = true
		_check(f.occupied(), "OR-toward-life: '%s' presence did not force occupied" % name)

	# Fault = occupied -- each fault mode on each channel forces occupied even though
	# nobody is present and every other channel reads clear.
	for name in ["radar_vitals", "thermal_ir", "ndir_co2", "load_bcg"]:
		for mode in ["unhealthy", "implausible", "stale"]:
			var f = _all_clear_suite()
			var c = f.get_channel(name)
			match mode:
				"unhealthy": c.healthy = false
				"implausible": c.plausible = false
				"stale": c.age = c.max_stale + 1.0
			_check(f.occupied(), "fault=occupied: '%s' %s did not force occupied" % [name, mode])

	# Diversity / common-cause -- the hypothermic, covered occupant: thermal MISSES
	# them (reads clear), but radar + CO2 + load still catch life. A single channel's
	# clear must never unlock => still occupied.
	var cold = _all_clear_suite()
	cold.get_channel("thermal_ir").present = false     # cold body: thermal blind
	cold.get_channel("radar_vitals").present = true    # micro-motion still seen
	cold.get_channel("ndir_co2").present = true         # breath CO2 still rises
	cold.get_channel("load_bcg").present = true         # mass + pulse still there
	_check(cold.occupied(), "diversity: hypothermic occupant (thermal blind) was not caught")

	# Mass-without-life ambiguity -- only the load cell sees a static mass; radar/CO2
	# see no life signs. ADR-0012: ambiguity errs to possibly-occupied => hold.
	var mass = _all_clear_suite()
	mass.get_channel("load_bcg").present = true
	_check(mass.occupied(), "ambiguity: static mass with no life signs was treated as empty")

	# Blinded -- ALL channels faulted (e.g. power/comms loss): must fail safe.
	var blind = _all_clear_suite()
	for c in blind.channels:
		c.healthy = false
	_check(blind.occupied(), "blinded: all-faulted suite did not fail safe to occupied")

	# Staleness via tick() -- clear suite goes occupied if not refreshed, and only
	# returns to clear once EVERY channel is refreshed.
	var stale = _all_clear_suite()
	_check(stale.all_clear(), "staleness: fresh suite should start clear")
	stale.tick(2.0)                                    # age past every max_stale
	_check(stale.occupied(), "staleness: un-refreshed suite did not go occupied")
	for name in ["radar_vitals", "thermal_ir", "ndir_co2"]:
		stale.refresh(name)                            # refresh all but one
	_check(stale.occupied(), "staleness: one stale channel should still hold occupied")
	stale.refresh("load_bcg")
	_check(stale.all_clear(), "staleness: fully-refreshed clear suite did not return to empty")

	# Exhaustive fail-safe property -- over ALL vote combinations, occupied() must be
	# true unless every channel is CLEAR. This is the core SF1 invariant.
	_exhaustive_invariant()

	# Runtime self-test hook (what the twin would call at startup).
	_check(Fusion.self_test(), "OccupancyFusion.self_test() reported the voter invariant broken")

	# Integration -- a real fusion drives the interlock through life_present().
	_integration_with_interlock()

	if failures == 0:
		print("PASS: SF1 fusion is fail-safe (empty only when every diverse channel agrees clear).")
		quit(0)
	else:
		print("FAILED: %d assertion(s)." % failures)
		quit(1)


## Drive each of the 4 channels to CLEAR / OCCUPIED / FAULT across all 3^4 = 81
## combinations; assert occupied() == not(all four CLEAR).
func _exhaustive_invariant() -> void:
	var f := _all_clear_suite()
	var n: int = f.channels.size()
	var combos := int(pow(3, n))
	var checked := 0
	for code in combos:
		var all_cleared := true
		var x := code
		for c in f.channels:
			var v := x % 3
			x /= 3
			c.healthy = true
			c.plausible = true
			c.age = 0.0
			c.present = false
			if v == 1:                # OCCUPIED
				c.present = true
				all_cleared = false
			elif v == 2:              # FAULT
				c.healthy = false
				all_cleared = false
		if f.occupied() != (not all_cleared):
			_fail("exhaustive: combo %d violated fail-safe (all_clear=%s occupied=%s)"
				% [code, str(all_cleared), str(f.occupied())])
		checked += 1
	_check(checked == 81, "exhaustive: expected 81 combinations, checked %d" % checked)


## The fusion must gate the interlock exactly like the ground-truth path did:
## all-clear lets an empty pod clear its bag; any occupied channel freezes it.
func _integration_with_interlock() -> void:
	# Liveness: real fusion, all-clear, refreshed each frame => the bag gets cleared.
	var live = Interlock.new()
	live.demo_seconds = 1.0
	live.hold_seconds = 0.2
	live.life_check_seconds = 0.3
	live.fusion = _all_clear_suite()
	live.bag_present = true
	for i in 600:
		for name in ["radar_vitals", "thermal_ir", "ndir_co2", "load_bcg"]:
			live.fusion.refresh(name)   # sensors sampled fresh every frame
		live.step(DT)
	_check(not live.bag_present, "integration: empty pod (fusion all-clear) never cleared its bag")

	# Safety: one channel reads occupied the whole time => piston must never move.
	var occ = Interlock.new()
	occ.demo_seconds = 1.0
	occ.hold_seconds = 0.2
	occ.life_check_seconds = 0.3
	occ.fusion = _all_clear_suite()
	occ.fusion.get_channel("radar_vitals").present = true   # a live occupant
	occ.bag_present = true
	for i in 600:
		for name in ["radar_vitals", "thermal_ir", "ndir_co2", "load_bcg"]:
			occ.fusion.refresh(name)
		occ.step(DT)
	_check(occ.progress == 0.0, "integration: piston moved with a fusion occupant present")
	_check(occ.state == Interlock.State.BLOCKED_OCCUPIED,
		"integration: did not park in BLOCKED_OCCUPIED under fusion occupancy (state=%d)" % occ.state)
	_check(occ.bag_present, "integration: cleared the bag while fusion reported occupied")
