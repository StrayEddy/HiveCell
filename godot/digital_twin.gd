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
var install_depth := 4.91          ## meters, full depth behind wall

var piston: MeshInstance3D
var rod: MeshInstance3D
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
	_add_part("ActuatorHousing", _metal(Color(0.30, 0.32, 0.36), 1.0))  # fixed drive housing
	# Rigid, fixed-length rod: attached to the piston, it TRANSLATES with it and
	# telescopes into the housing -- it never changes length.
	rod = _add_part("ActuatorRod", _metal(Color(0.60, 0.62, 0.66), 1.0))

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
	rod.position.x = -progress * stroke   # rigid rod: same translation as the piston
	_update_label()


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
