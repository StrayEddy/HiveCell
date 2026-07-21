extends Node3D
## HiveCell digital twin.
## Loads the FreeCAD-exported parts (meters, Y-up) and animates the syringe
## retraction: the piston is the ONLY moving part, sliding -X by `stroke`.
## Dimensions/timing come from models/hivecell.json (kept in sync by
## scripts/export_godot.py), so nothing here is a hardcoded magic number.

const MODELS := "res://models/"

@export var demo_seconds := 8.0   ## compress the ~10 min retraction to this many seconds
@export var hold_seconds := 2.0   ## pause at each end of travel
@export var paused := false        ## Space toggles this at runtime

var stroke := 2.2                  ## meters, overwritten from manifest
var retract_real := 600.0          ## real-world seconds, from manifest
var install_depth := 2.86          ## meters, full depth behind wall
var piston_rear_deployed := 2.5    ## meters
var magazine_front := 2.56         ## meters, fixed chain magazine mouth
var chain_w := 0.06                ## meters (Y)
var chain_h := 0.06                ## meters (Z)

var piston: MeshInstance3D
var column: MeshInstance3D          ## rigid-chain exposed column (procedural)
var column_mesh: BoxMesh
var label: Label

enum State { DEPLOYED, RETRACTING, CLOSED, EXTENDING }
var state: int = State.DEPLOYED
var t := 0.0                       ## time in current state
var progress := 0.0                ## 0 = deployed (available), 1 = closed (flush)


func _ready() -> void:
	_load_manifest()
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
		t += delta
		match state:
			State.DEPLOYED:
				progress = 0.0
				if t >= hold_seconds:
					_goto(State.RETRACTING)
			State.RETRACTING:
				progress = clampf(t / demo_seconds, 0.0, 1.0)
				if progress >= 1.0:
					_goto(State.CLOSED)
			State.CLOSED:
				progress = 1.0
				if t >= hold_seconds:
					_goto(State.EXTENDING)
			State.EXTENDING:
				progress = clampf(1.0 - t / demo_seconds, 0.0, 1.0)
				if progress <= 0.0:
					_goto(State.DEPLOYED)

	piston.position.x = -progress * stroke
	_update_chain()
	_update_label()


func _update_chain() -> void:
	# Rigid chain spans from the (moving) piston rear to the (fixed) magazine mouth;
	# the remainder is coiled inside the magazine (total chain length conserved).
	var piston_rear := piston_rear_deployed - progress * stroke
	var col_len: float = maxf(magazine_front - piston_rear, 0.001)
	column_mesh.size = Vector3(col_len, chain_w, chain_h)
	column.position = Vector3((piston_rear + magazine_front) * 0.5, 0.0, 0.0)


func _goto(s: int) -> void:
	state = s
	t = 0.0


func _update_label() -> void:
	var names := {
		State.DEPLOYED: "AVAILABLE (deployed)",
		State.RETRACTING: "RETRACTING",
		State.CLOSED: "CLOSED (flush)",
		State.EXTENDING: "DEPLOYING",
	}
	var real_elapsed := int(round(progress * retract_real))
	label.text = "HiveCell digital twin   [Space] pause\nState: %s\nRetraction: %d%%   (~%ds of %ds real)\nPiston X: %+.2f m" % [
		names[state], int(round(progress * 100.0)), real_elapsed, int(retract_real), piston.position.x
	]
