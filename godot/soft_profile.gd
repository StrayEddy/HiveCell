extends RefCounted
class_name SoftProfile
## SF5 soft motion profile (defense-in-depth, never a primary safeguard).
## Shapes the sweep velocity instead of moving at a constant rate:
##   soft-start (accel-limited) -> cruise -> soft-stop, PLUS a REDUCED FINAL-APPROACH
## speed in the last stretch near the flush/mouth end. The reduced approach lowers
## contact energy exactly where the mouth-lip pinch (H8) lives, if SF1/SF2 have
## already failed. Pure + headless-testable; no scene dependency.

var accel_frac := 0.15      # fraction of travel spent ramping up from rest
var decel_frac := 0.15      # fraction ramping back down to rest at the end
var approach_frac := 0.25   # final fraction held at the reduced approach speed
var approach_ratio := 0.35  # reduced-approach speed as a fraction of cruise
var v_min := 0.05           # floor so motion always completes (never a hard stall)

var _integral_cache := -1.0


## Normalized velocity (cruise = 1.0) at fractional position p in [0,1].
func velocity(p: float) -> float:
	p = clampf(p, 0.0, 1.0)
	var v := 1.0
	if accel_frac > 0.0 and p < accel_frac:
		v = minf(v, smoothstep(0.0, 1.0, p / accel_frac))           # soft start 0->1
	if decel_frac > 0.0 and p > 1.0 - decel_frac:
		v = minf(v, smoothstep(0.0, 1.0, (1.0 - p) / decel_frac))   # soft stop ->0
	if approach_frac > 0.0 and p > 1.0 - approach_frac:
		v = minf(v, approach_ratio)                                 # reduced approach
	return maxf(v, v_min)


# Integral of dp/velocity over [0,1]; scales advance() so the whole sweep still
# takes ~`duration` regardless of the shape.
func _integral() -> float:
	if _integral_cache >= 0.0:
		return _integral_cache
	var acc := 0.0
	var n := 400
	for i in n:
		var p := (float(i) + 0.5) / float(n)
		acc += (1.0 / velocity(p)) / float(n)
	_integral_cache = acc
	return _integral_cache


## Advance a 0..1 position by dt so the whole 0->1 sweep takes ~`duration` seconds,
## following the shaped velocity.
func advance(p: float, dt: float, duration: float) -> float:
	var k := _integral() / maxf(duration, 0.0001)   # cruise-speed scale
	return clampf(p + velocity(p) * k * dt, 0.0, 1.0)
