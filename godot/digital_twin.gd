extends Node3D
## HiveCell digital twin.
## Loads the FreeCAD-exported parts (meters, Y-up) and animates the syringe
## motion: the piston is the ONLY moving part, sliding -X by `stroke`.
## Dimensions/timing come from models/hivecell.json (kept in sync by
## scripts/export_godot.py), so nothing here is a hardcoded magic number.
##
## SAFETY MODEL (see docs/SAFETY.md):
## The piston exists to clear INANIMATE items (e.g. a bag left behind) from an
## EMPTY pod. It must never move against a living thing. So the clearing sweep is
## gated behind a life-detection interlock: the mechanism has to positively prove
## "no life inside" before it may move, and a force/safety-edge backstop reverses
## it if life is detected mid-motion. Removal is restricted to things that
## cannot be hurt; a person or animal present => hold still + alert a human.

const MODELS := "res://models/"

@export var demo_seconds := 8.0   ## compress the ~10 min sweep to this many seconds
@export var hold_seconds := 2.0   ## pause at each end of travel
@export var paused := false        ## Space toggles this at runtime

## --- Interlock simulation knobs (drive the simulated sensors so you can test) ---
@export var occupant_alive := false  ## SIM: a living person/animal is inside right now
@export var bag_present := true      ## SIM: an inanimate item was left behind
@export var sensor_fault := false    ## SIM: inject a sensor fault (must fail safe -> no motion)
@export var life_check_seconds := 1.5  ## dwell: all channels must read "no life" this long

var stroke := 2.2                  ## meters, overwritten from manifest
var retract_real := 600.0          ## real-world seconds, from manifest
var install_depth := 2.86          ## meters, full depth behind wall
var piston_rear_deployed := 2.5    ## meters
var magazine_front := 2.56         ## meters, fixed chain magazine mouth
var chain_w := 0.06                ## meters (Y)
var chain_h := 0.06                ## meters (Z)

var piston: MeshInstance3D
var seals: MeshInstance3D           ## SF3 wiper lip rings (ride with the piston)
var column: MeshInstance3D          ## rigid-chain exposed column (procedural)
var column_mesh: BoxMesh
var bag: MeshInstance3D             ## the inanimate item to be cleared (procedural)
var label: Label

## The clearing cycle + life-detection live in a pure, headless-testable class
## (safety_interlock.gd). This twin just drives its inputs and renders its state,
## so the twin and the self-test exercise the SAME safety logic.
var il := SafetyInterlock.new()
var progress := 0.0                ## mirrored from the interlock for rendering


func _ready() -> void:
	_load_manifest()
	il.demo_seconds = demo_seconds
	il.hold_seconds = hold_seconds
	il.life_check_seconds = life_check_seconds
	il.bag_present = bag_present   # interlock owns bag state once running (it clears it)
	_build_scene()


func _load_manifest() -> void:
	var f := FileAccess.open(MODELS + "hivecell.json", FileAccess.READ)
	if f == null:
		push_warning("hivecell.json not found; using defaults")
		return
	var data = JSON.parse_string(f.get_as_text())
	if data is Dictionary:
		stroke = float(data.get("stroke_m", stroke))
		retract_real = float(data.get("retract_seconds_real", retract_real))
		install_depth = float(data.get("install_depth_m", install_depth))
		piston_rear_deployed = float(data.get("piston_rear_deployed_m", piston_rear_deployed))
		magazine_front = float(data.get("magazine_front_m", magazine_front))
		chain_w = float(data.get("chain_width_m", chain_w))
		chain_h = float(data.get("chain_height_m", chain_h))


func _metal(color: Color, alpha := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(color.r, color.g, color.b, alpha)
	m.metallic = 0.9
	m.roughness = 0.35
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


func _add_part(part_name: String, mat: StandardMaterial3D) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = load(MODELS + part_name + ".obj")
	mi.material_override = mat
	add_child(mi)
	return mi


func _build_scene() -> void:
	# Barrel semi-transparent so you can watch the piston inside; piston solid.
	_add_part("CapsuleShell", _metal(Color(0.70, 0.75, 0.80), 0.22))
	piston = _add_part("Piston", _metal(Color(0.85, 0.87, 0.90), 1.0))
	# SF3 wiper seals: matte elastomer lip rings filling the 3mm gap; ride with piston.
	var seal_mat := StandardMaterial3D.new()
	seal_mat.albedo_color = Color(0.11, 0.12, 0.14)
	seal_mat.roughness = 0.95
	seals = _add_part("WiperSeals", seal_mat)
	_add_part("ChainMagazine", _metal(Color(0.30, 0.32, 0.36), 1.0))  # fixed coil + drive
	# Rigid-chain column: links lock straight to push and coil into the magazine to
	# retract. Its exposed length changes as chain feeds from the coil (total length
	# conserved in the magazine) -- so a variable-length column here is PHYSICAL.
	column_mesh = BoxMesh.new()
	column_mesh.size = Vector3(0.001, chain_w, chain_h)
	column = MeshInstance3D.new()
	column.mesh = column_mesh
	column.material_override = _metal(Color(0.55, 0.57, 0.60), 1.0)
	add_child(column)

	# The left-behind bag: a small soft item that rides out ahead of the piston
	# face during a clearing sweep. Purely a demo prop for the inanimate case.
	var bag_mesh := BoxMesh.new()
	bag_mesh.size = Vector3(0.35, 0.30, 0.30)
	bag = MeshInstance3D.new()
	bag.mesh = bag_mesh
	var bag_mat := StandardMaterial3D.new()
	bag_mat.albedo_color = Color(0.55, 0.40, 0.20)
	bag_mat.roughness = 0.9
	bag.material_override = bag_mat
	add_child(bag)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -35, 0)
	sun.light_energy = 1.2
	add_child(sun)

	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.06, 0.07, 0.09)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.40, 0.45, 0.50)
	env.ambient_light_energy = 0.6
	world.environment = env
	add_child(world)

	var mid := install_depth * 0.5          # middle of the full assembly
	var center := Vector3(mid, 0.0, 0.0)
	var cam := Camera3D.new()
	cam.position = Vector3(mid, 1.7, 4.6)
	add_child(cam)
	cam.look_at(center, Vector3.UP)
	cam.current = true

	var canvas := CanvasLayer.new()
	add_child(canvas)
	label = Label.new()
	label.position = Vector2(16, 12)
	label.add_theme_font_size_override("font_size", 20)
	canvas.add_child(label)


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_SPACE:
		paused = not paused


func _process(delta: float) -> void:
	if not paused:
		# Feed the live simulation knobs into the interlock, then step it.
		il.occupant_alive = occupant_alive
		il.sensor_fault = sensor_fault
		il.step(delta)
		progress = il.progress
		bag_present = il.bag_present

	piston.position.x = -progress * stroke
	seals.position.x = piston.position.x   # seals ride with the piston
	_update_chain()
	_update_bag()
	_update_label()


func _update_chain() -> void:
	# Rigid chain spans from the (moving) piston rear to the (fixed) magazine mouth;
	# the remainder is coiled inside the magazine (total chain length conserved).
	var piston_rear := piston_rear_deployed - progress * stroke
	var col_len: float = maxf(magazine_front - piston_rear, 0.001)
	column_mesh.size = Vector3(col_len, chain_w, chain_h)
	column.position = Vector3((piston_rear + magazine_front) * 0.5, 0.0, 0.0)


func _update_bag() -> void:
	# The bag rides just ahead of the piston face while it is being swept out, and
	# vanishes once cleared. Only shown for the inanimate-clearing demo.
	bag.visible = bag_present
	if bag_present:
		bag.position = Vector3(piston.position.x + 0.4, 0.0, 0.0)


func _update_label() -> void:
	var names := {
		SafetyInterlock.State.AVAILABLE: "AVAILABLE (in use / deployed)",
		SafetyInterlock.State.LIFE_CHECK: "LIFE CHECK (must prove empty)",
		SafetyInterlock.State.CLEARING: "CLEARING inanimate item",
		SafetyInterlock.State.CLEARED_HOLD: "CLEARED (flush)",
		SafetyInterlock.State.REDEPLOY: "REDEPLOYING",
		SafetyInterlock.State.BLOCKED_OCCUPIED: "BLOCKED: life detected -> alert human",
	}
	var verdict := ("OCCUPIED" if il.life_present() else "clear")
	var sig = ["OFF", "WARN", "MOVING"][il.signal_level()]
	var real_elapsed := int(round(progress * retract_real))
	label.text = "HiveCell digital twin   [Space] pause\nState: %s\nInterlock: %s   (fault=%s, bag=%s)\nSweep: %d%%   (~%ds of %ds real)\nSF5 signal: %s   Piston X: %+.2f m" % [
		names[il.state], verdict, str(sensor_fault), str(bag_present),
		int(round(progress * 100.0)), real_elapsed, int(retract_real), sig, piston.position.x
	]
