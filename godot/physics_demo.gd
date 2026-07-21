extends Node3D
## HiveCell physics scenario show.
## The SAME safety logic as the twin (safety_interlock.gd) drives a real physics
## sweep: an AnimatableBody3D piston pushes RigidBody3D contents out the mouth --
## but ONLY when life-detection proves the pod empty. Plays through a set of
## scenarios on loop so you can watch the interlock behave when you run the scene.
##
## Coordinate frame (meters, Y up): the mouth (public opening) is at x = 0; the
## cavity runs +X into the wall to x = CAVITY_LEN. Deployed piston sits deep;
## clearing advances it toward x = 0, sweeping anything loose out the mouth where
## it drops onto the exterior floor. A living thing present => piston never moves.

const CAVITY_LEN := 2.0
const BORE_W := 0.9        ## cavity width  (Z)
const BORE_H := 0.9        ## cavity height (Y)
const PLATE_TH := 0.1      ## piston plate thickness (X)

var il := SafetyInterlock.new()

var piston: AnimatableBody3D
var spawned: Array[Node] = []      ## contents + person, cleared between scenarios
var person: Node3D = null
var title_label: Label
var status_label: Label

## title, number of loose items, someone inside, and whether someone intrudes
## mid-sweep. Order matches the request + one bonus safety case at the end.
var scenarios := [
	{"title": "1 · EMPTY POD — no one, nothing inside", "things": 0, "person": false, "intrude": false},
	{"title": "2 · ONE ITEM LEFT — no one inside",       "things": 1, "person": false, "intrude": false},
	{"title": "3 · LOTS OF STUFF — no one inside",        "things": 7, "person": false, "intrude": false},
	{"title": "4 · SOMEONE INSIDE — motion LOCKED",       "things": 0, "person": true,  "intrude": false},
	{"title": "5 · INTRUSION MID-SWEEP — stop & reverse", "things": 2, "person": false, "intrude": true},
]
var scn := -1
var scn_time := 0.0
var saw_motion := false
var intruded := false


func _ready() -> void:
	il.demo_seconds = 3.5
	il.hold_seconds = 1.0
	il.life_check_seconds = 0.6
	_build_world()
	_start_scenario(0)


# --- world -------------------------------------------------------------------
func _mat(c: Color, rough := 0.7, metal := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	m.metallic = metal
	return m


func _box_mesh_inst(size: Vector3, mat: StandardMaterial3D) -> MeshInstance3D:
	var bm := BoxMesh.new()
	bm.size = size
	var mi := MeshInstance3D.new()
	mi.mesh = bm
	mi.material_override = mat
	return mi


func _static_box(size: Vector3, pos: Vector3, mat: StandardMaterial3D) -> void:
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	body.add_child(_box_mesh_inst(size, mat))
	body.position = pos
	add_child(body)


func _build_world() -> void:
	# Cavity floor + side walls (open at the mouth, x = 0, and at the top).
	_static_box(Vector3(CAVITY_LEN, 0.1, BORE_W), Vector3(CAVITY_LEN * 0.5, -0.05, 0.0),
		_mat(Color(0.32, 0.34, 0.38)))
	_static_box(Vector3(CAVITY_LEN, BORE_H, 0.05), Vector3(CAVITY_LEN * 0.5, BORE_H * 0.5, BORE_W * 0.5),
		_mat(Color(0.28, 0.30, 0.34)))
	_static_box(Vector3(CAVITY_LEN, BORE_H, 0.05), Vector3(CAVITY_LEN * 0.5, BORE_H * 0.5, -BORE_W * 0.5),
		_mat(Color(0.28, 0.30, 0.34)))
	# Exterior floor just below the mouth so ejected items drop out and tumble.
	_static_box(Vector3(3.0, 0.2, 3.0), Vector3(-1.4, -0.7, 0.0), _mat(Color(0.18, 0.19, 0.22)))

	# Piston plate: kinematic, pushes RigidBodies. sync_to_physics is on by default.
	piston = AnimatableBody3D.new()
	var pcs := CollisionShape3D.new()
	var pshape := BoxShape3D.new()
	pshape.size = Vector3(PLATE_TH, BORE_H - 0.02, BORE_W - 0.02)
	pcs.shape = pshape
	piston.add_child(pcs)
	piston.add_child(_box_mesh_inst(pshape.size, _mat(Color(0.85, 0.87, 0.92), 0.3, 0.9)))
	add_child(piston)
	_place_piston()

	# Lights + environment.
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52, -38, 0)
	sun.light_energy = 1.25
	add_child(sun)
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.06, 0.08)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.42, 0.47, 0.52)
	env.ambient_light_energy = 0.55
	world.environment = env
	add_child(world)

	var cam := Camera3D.new()
	# Near top-down: look almost straight into the open-top pod so the contents
	# and the sweep read like a plan view. Small +Z offset keeps a slight tilt
	# (and a valid up vector) and still catches the mouth ejection at x<0.
	cam.position = Vector3(0.7, 5.2, 0.6)
	add_child(cam)
	# Looking near-straight-down, so use -Z as "up" on screen (Vector3.UP would be
	# parallel to the view direction and is invalid). +X (pod depth) reads L->R.
	cam.look_at(Vector3(0.7, 0.0, -0.05), Vector3(0, 0, -1))
	cam.current = true

	var canvas := CanvasLayer.new()
	add_child(canvas)
	title_label = Label.new()
	title_label.position = Vector2(18, 14)
	title_label.add_theme_font_size_override("font_size", 26)
	canvas.add_child(title_label)
	status_label = Label.new()
	status_label.position = Vector2(18, 52)
	status_label.add_theme_font_size_override("font_size", 19)
	canvas.add_child(status_label)


# --- contents ----------------------------------------------------------------
func _spawn_item(pos: Vector3, size: Vector3, c: Color, mass := 1.0) -> void:
	var body := RigidBody3D.new()
	body.mass = mass
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	body.add_child(_box_mesh_inst(size, _mat(c, 0.85)))
	body.position = pos
	add_child(body)
	spawned.append(body)


func _spawn_person(pos: Vector3) -> void:
	# Purely visual -- the interlock, not physics, is what protects them.
	var node := Node3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.18
	cap.height = 0.95
	var mi := MeshInstance3D.new()
	mi.mesh = cap
	mi.material_override = _mat(Color(0.90, 0.45, 0.40), 0.6)
	mi.rotation_degrees = Vector3(0, 0, 90)   # lying along X
	node.add_child(mi)
	node.position = pos
	add_child(node)
	spawned.append(node)
	person = node


func _clear_scene_contents() -> void:
	for n in spawned:
		if is_instance_valid(n):
			n.queue_free()
	spawned.clear()
	person = null


# --- scenario flow -----------------------------------------------------------
func _start_scenario(i: int) -> void:
	scn = i
	scn_time = 0.0
	saw_motion = false
	intruded = false
	_clear_scene_contents()

	# Fresh interlock so each scenario starts deployed and empty of state.
	il = SafetyInterlock.new()
	il.demo_seconds = 3.5
	il.hold_seconds = 1.0
	il.life_check_seconds = 0.6

	var s = scenarios[i]
	il.occupant_alive = s["person"]
	print("[scenario] ", s["title"])

	var n: int = s["things"]
	for k in n:
		var x := 0.45 + (CAVITY_LEN - 0.9) * (float(k) + 0.5) / maxf(float(n), 1.0)
		var z := (-0.25 if k % 2 == 0 else 0.25) * (1.0 if n > 1 else 0.0)
		var sz := 0.16 + 0.06 * float(k % 3)
		var col := Color.from_hsv(fmod(0.08 + 0.13 * float(k), 1.0), 0.55, 0.9)
		_spawn_item(Vector3(x, sz * 0.5 + 0.02, z), Vector3(sz, sz, sz), col)

	if s["person"]:
		_spawn_person(Vector3(1.0, 0.32, 0.0))

	_place_piston()


func _place_piston() -> void:
	# progress 0 = deployed (deep); 1 = flush at the mouth. Front face sweeps -X.
	var x: float = CAVITY_LEN * (1.0 - il.progress)
	piston.position = Vector3(x + PLATE_TH * 0.5, BORE_H * 0.5, 0.0)


func _scenario_done() -> bool:
	var s = scenarios[scn]
	if s["person"]:
		# It will park in BLOCKED_OCCUPIED and never move: show it, then advance.
		return il.state == SafetyInterlock.State.BLOCKED_OCCUPIED and scn_time > 3.5
	if s["intrude"]:
		# Done once it has reversed back out after the intrusion.
		return intruded and il.progress <= 0.02 and scn_time > 1.0
	# Normal clear: it moved and returned to AVAILABLE, held a beat.
	return saw_motion and il.state == SafetyInterlock.State.AVAILABLE and scn_time > 1.0


func _physics_process(delta: float) -> void:
	scn_time += delta

	# Bonus scenario: someone reaches in once the sweep is well underway.
	if scenarios[scn]["intrude"] and not intruded \
			and il.state == SafetyInterlock.State.CLEARING and il.progress > 0.45:
		il.occupant_alive = true
		intruded = true
		_spawn_person(Vector3(0.25, 0.32, 0.0))

	il.step(delta)
	if il.state == SafetyInterlock.State.CLEARING or il.state == SafetyInterlock.State.REDEPLOY:
		saw_motion = true
	_place_piston()
	_update_hud()

	if _scenario_done() and scn_time > 2.0:
		_start_scenario((scn + 1) % scenarios.size())


func _update_hud() -> void:
	var names := {
		SafetyInterlock.State.AVAILABLE: "AVAILABLE (deployed)",
		SafetyInterlock.State.LIFE_CHECK: "LIFE CHECK — proving empty",
		SafetyInterlock.State.CLEARING: "CLEARING — sweeping items out",
		SafetyInterlock.State.CLEARED_HOLD: "CLEARED (flush)",
		SafetyInterlock.State.REDEPLOY: "REDEPLOYING",
		SafetyInterlock.State.BLOCKED_OCCUPIED: "BLOCKED — life detected, alert human",
	}
	var life := il.life_present()
	title_label.text = str(scenarios[scn]["title"])
	title_label.add_theme_color_override("font_color", Color(1, 0.5, 0.45) if life else Color(0.6, 1, 0.7))
	status_label.text = "Interlock: %s\nLife: %s    Sweep: %d%%" % [
		names[il.state], ("DETECTED" if life else "clear"), int(round(il.progress * 100.0))
	]
