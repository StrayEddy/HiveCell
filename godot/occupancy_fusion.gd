extends RefCounted
class_name OccupancyFusion
## SF1 occupancy sensing -- diverse-redundant, fail-safe fusion (ADR-0012).
##
## Pure, headless-testable. Models the four DIVERSE sensor channels (different
## physics, so no single common-cause failure can blind the suite) and reduces
## them to one verdict under the ADR-0012 fail-safe voting rules:
##
##   OR toward life   -- ANY channel that reads presence/life  => occupied.
##   fault = occupied -- ANY channel faulted / stale / out-of-range => occupied.
##   AND toward clear -- "empty" ONLY when EVERY channel positively reads CLEAR.
##
## i.e. the absence of proof-of-emptiness is never treated as "empty". A missed
## occupant can be fatal (users may not self-rescue), so ambiguity always holds.
##
## This encodes the LOGIC; ADR-0012 fixes the PHYSICS (sensor part numbers) and
## the RATING (ISO 13849 PL e on a rated safety controller). Feed the verdict into
## SafetyInterlock.life_present() to gate motion.

enum Vote { CLEAR, OCCUPIED, FAULT }


## One diverse sensor channel. Raw inputs are driven by the twin/test as ground
## truth; vote() reduces them to CLEAR / OCCUPIED / FAULT under the fail-safe rules.
class Channel:
	extends RefCounted
	var name: String
	## Can this channel distinguish a LIVING thing (radar vitals / CO2 / load-BCG),
	## or only presence/heat (thermal)? Diagnostic only -- the voter treats any
	## presence as occupied regardless, since inert mass is still "not proven empty".
	var senses_life: bool

	# --- raw sim inputs (driven by twin/test) ---
	var present := false     ## channel signal is above its detection threshold
	var healthy := true      ## hardware / self-test OK
	var plausible := true    ## reading in-range (not saturated / not impossible)
	var age := 0.0           ## seconds since the last fresh sample
	var max_stale := 1.0     ## older than this => stale => fault

	func _init(n: String, life: bool) -> void:
		name = n
		senses_life = life

	func faulted() -> bool:
		return (not healthy) or (not plausible) or (age > max_stale)

	func vote() -> int:
		if faulted():
			return Vote.FAULT
		return Vote.OCCUPIED if present else Vote.CLEAR

	func vote_reason() -> String:
		if not healthy:
			return "%s: FAULT (unhealthy)" % name
		if not plausible:
			return "%s: FAULT (out-of-range)" % name
		if age > max_stale:
			return "%s: FAULT (stale %.2fs > %.2fs)" % [name, age, max_stale]
		if present:
			return "%s: OCCUPIED (presence/life)" % name
		return "%s: clear" % name


var channels: Array = []


func _init() -> void:
	# ADR-0012 diverse suite: A radar vitals, B thermal IR, C NDIR CO2, D load+BCG.
	channels = [
		Channel.new("radar_vitals", true),   # A: respiration/heartbeat micro-motion (still, covered)
		Channel.new("thermal_ir", false),    # B: body heat/shape (presence; weak on hypothermic)
		Channel.new("ndir_co2", true),       # C: exhaled CO2 = metabolism (penetration-independent)
		Channel.new("load_bcg", true),       # D: static mass + ballistocardiography (pulse micro-shifts)
	]


func get_channel(n: String) -> Channel:
	for c in channels:
		if c.name == n:
			return c
	return null


## Advance the staleness clocks. A channel that isn't refreshed goes stale =>
## fault => occupied (fail-safe). Call once per frame with the frame delta.
func tick(delta: float) -> void:
	for c in channels:
		c.age += delta


## Mark a channel as freshly sampled (resets its staleness clock).
func refresh(chan_name: String) -> void:
	var c := get_channel(chan_name)
	if c != null:
		c.age = 0.0


## THE fusion verdict (ADR-0012). Occupied unless EVERY channel positively reads
## CLEAR: any OCCUPIED vote (OR toward life) or any FAULT vote (fault = occupied)
## returns true. Diverse physics means dust/fog/cold can blind one channel without
## blinding the others, so a single CLEAR can never unlock on its own.
func occupied() -> bool:
	for c in channels:
		if c.vote() != Vote.CLEAR:
			return true
	return false


func all_clear() -> bool:
	return not occupied()


## Human-readable reasons every channel is (or isn't) forcing occupied -- for the
## twin's diagnostics and the self-test.
func reasons() -> Array:
	var out: Array = []
	for c in channels:
		out.append(c.vote_reason())
	return out


## Runtime self-test of the VOTER logic on a scratch suite (does not touch live
## channels). Proves the fail-safe invariant still holds: "empty" requires every
## channel CLEAR, and any single OCCUPIED or FAULT forces occupied. Returns true
## if the invariant holds for all vote combinations. The twin can call this at
## startup (like the interlock's self-test) to catch a broken build.
static func self_test() -> bool:
	var scratch := OccupancyFusion.new()
	var n := scratch.channels.size()
	# Drive every channel to each of the 3 votes; check occupied == not(all CLEAR).
	var combos := int(pow(3, n))
	for code in combos:
		var all_cleared := true
		var x := code
		for c in scratch.channels:
			var v := x % 3
			x /= 3
			# CLEAR=0, OCCUPIED=1, FAULT=2 -- set inputs to force that vote.
			c.healthy = true
			c.plausible = true
			c.age = 0.0
			c.present = false
			if v == 1:
				c.present = true
				all_cleared = false
			elif v == 2:
				c.healthy = false
				all_cleared = false
		var want_occupied := not all_cleared
		if scratch.occupied() != want_occupied:
			return false
	return true
