extends Node3D
## HiveCell physics scenario show (CAD-accurate).
## Renders and collides against the ACTUAL FreeCAD-exported meshes
## (models/CapsuleShell.obj, Piston.obj) — the same geometry the digital twin
## uses — driven by the same safety_interlock. The piston plug physically sweeps
## loose RigidBody items out the mouth, but ONLY when life-detection proves the
## pod empty; a living thing present => no motion.
##
## Frame (from the exported meshes, meters, Y-up): the bore runs along X, mouth
## (public opening) at the shell's min-x (= 0); the cavity extends +X to the
## deployed piston face; the piston retracts -X by `stroke` to sit flush at the
## mouth. Gravity settles items on the bore's inner floor; ejected items drop
## onto an exterior floor just outside the mouth. Bore dims are read from the
## shell mesh AABB, so this stays in sync if the CAD changes and is re-exported.

const MODELS := "res://models/"

var il := SafetyInterlock.new()

var stroke := 2.2          ## piston travel, from manifest
var floor_y := -0.5        ## inner-bore floor Y, from the shell mesh
var half_w := 0.4          ## usable half-width (Z) inside the bore
var mouth_x := 0.0         ## public opening, shell min-x
var cavity_x0 := 0.15      ## just inside the mouth
var cavity_x1 := 2.0       ## just in front of the deployed piston face

var piston: AnimatableBody3D
var spawned: Array[Node] = []
var person: Node3D = null
var title_label: Label
var status_label: Label

var scenarios := [
	{"title": "1 · EMPTY POD — no one, nothing inside", "things": 0,  "person": false, "intrude": false},
	{"title": "2 · ONE ITEM LEFT — no one inside",       "things": 1,  "person": false, "intrude": false},
	{"title": "3 · LOTS OF STUFF — no one inside",        "things": 10, "person": false, "intrude": false},
	{"title": "4 · SOMEONE INSIDE — motion LOCKED",       "things": 0,  "person": true,  "intrude": false},
	{"title": "5 · INTRUSION MID-SWEEP — stop & reverse", "things": 2,  "person": false, "intrude": true},
]
var scn := -1
var scn_time := 0.0
var saw_motion := false
var intruded := false


func _ready() -> void:
	randomize()   # different item layout every run
	_load_manifest()
	il.demo_seconds = 3.5
	il.hold_seconds = 1.0
	il.life_check_seconds = 0.6
	_build_world()
	_start_scenario(0)


func _load_manifest() -> void:
	var f := FileAccess.open(MODELS + "hivecell.json", FileAccess.READ)
	if f == null:
		return
	var d = JSON.parse_string(f.get_as_text())
	if d is Dictionary:
		stroke = float(d.get("stroke_m", stroke))


# --- helpers -----------------------------------------------------------------
func _mat(c: Color, rough := 0.7, metal := 0.0, alpha := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(c.r, c.g, c.b, alpha)
	m.roughness = rough
	m.metallic = metal
	if alpha < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
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


# --- world (real CAD meshes) -------------------------------------------------
func _build_world() -> void:
	var shell_mesh: Mesh = load(MODELS + "CapsuleShell.obj")
	var aabb := shell_mesh.get_aabb()
	var wall := 0.012          # ~6mm sleeve, both surfaces
	mouth_x = aabb.position.x
	floor_y = aabb.position.y + wall
	half_w = aabb.size.z * 0.5 - wall
	cavity_x0 = mouth_x + 0.2
	cavity_x1 = stroke - 0.25  # keep items in front of the deployed piston face

	# Shell: static body, concave (trimesh) collision from the real mesh, drawn
	# semi-transparent so the interior reads from the near top-down camera.
	var shell_body := StaticBody3D.new()
	var smi := MeshInstance3D.new()
	smi.mesh = shell_mesh
	smi.material_override = _mat(Color(0.70, 0.75, 0.80), 0.35, 0.6, 0.20)
	shell_body.add_child(smi)
	var scs := CollisionShape3D.new()
	scs.shape = shell_mesh.create_trimesh_shape()
	shell_body.add_child(scs)
	add_child(shell_body)

	# Chain magazine: decorative only (behind the shell).
	var mag := MeshInstance3D.new()
	mag.mesh = load(MODELS + "ChainMagazine.obj")
	mag.material_override = _mat(Color(0.30, 0.32, 0.36), 0.5, 0.8)
	add_child(mag)

	# Piston: animatable body, real mesh + convex hull collision (the plug is
	# convex). sync_to_physics is on by default, so it pushes RigidBodies.
	var piston_mesh: Mesh = load(MODELS + "Piston.obj")
	piston = AnimatableBody3D.new()
	var pmi := MeshInstance3D.new()
	pmi.mesh = piston_mesh
	pmi.material_override = _mat(Color(0.85, 0.87, 0.92), 0.3, 0.9)
	piston.add_child(pmi)
	var pcs := CollisionShape3D.new()
	pcs.shape = piston_mesh.create_convex_shape()
	piston.add_child(pcs)
	add_child(piston)
	_place_piston()

	# Exterior floor just outside/below the mouth to catch ejected items.
	_static_box(Vector3(3.2, 0.2, 2.6), Vector3(mouth_x - 1.4, floor_y - 0.5, 0.0),
		_mat(Color(0.16, 0.17, 0.20)))

	# Lights + environment.
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-62, -28, 0)
	sun.light_energy = 1.25
	add_child(sun)
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.06, 0.08)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.42, 0.47, 0.52)
	env.ambient_light_energy = 0.6
	world.environment = env
	add_child(world)

	# Near top-down camera looking into the bore (shell is see-through). +X (bore
	# depth) reads left->right; -Z is screen-up since we look near-straight-down.
	var cam := Camera3D.new()
	cam.position = Vector3(1.0, 5.4, 0.7)
	add_child(cam)
	cam.look_at(Vector3(1.0, floor_y, -0.05), Vector3(0, 0, -1))
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
func _spawn_item(pos: Vector3, size: Vector3, c: Color, mass := 1.0, rot := Vector3.ZERO) -> void:
	var body := RigidBody3D.new()
	body.mass = mass
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	body.add_child(_box_mesh_inst(size, _mat(c, 0.85)))
	body.position = pos
	body.rotation_degrees = rot
	add_child(body)
	spawned.append(body)


func _spawn_person(pos: Vector3) -> void:
	# Purely visual — the interlock, not physics, is what protects them.
	var node := Node3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.26
	cap.height = 1.5
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
		# Random scatter across the real bore: position, size, drop, spin, colour
		# all vary so no two runs clear the same way.
		var x := randf_range(cavity_x0, cavity_x1)
		var z := randf_range(-half_w * 0.8, half_w * 0.8)
		var sz := Vector3(randf_range(0.14, 0.30), randf_range(0.12, 0.26), randf_range(0.14, 0.30))
		var drop := randf_range(0.0, 0.5)
		var rot := Vector3(0.0, randf_range(-180.0, 180.0), 0.0)
		var col := Color.from_hsv(randf(), randf_range(0.45, 0.72), randf_range(0.8, 0.95))
		_spawn_item(Vector3(x, floor_y + sz.y * 0.5 + 0.03 + drop, z), sz, col, randf_range(0.7, 1.4), rot)

	if s["person"]:
		_spawn_person(Vector3(stroke * 0.5, floor_y + 0.28, 0.0))

	_place_piston()


func _place_piston() -> void:
	# Deployed (progress 0) = piston at its natural pose (face at x = stroke);
	# flush (progress 1) = retracted -stroke so the face sits at the mouth.
	piston.position = Vector3(-il.progress * stroke, 0.0, 0.0)


func _scenario_done() -> bool:
	var s = scenarios[scn]
	if s["person"]:
		return il.state == SafetyInterlock.State.BLOCKED_OCCUPIED and scn_time > 3.5
	if s["intrude"]:
		return intruded and il.progress <= 0.02 and scn_time > 1.0
	return saw_motion and il.state == SafetyInterlock.State.AVAILABLE and scn_time > 1.0


func _physics_process(delta: float) -> void:
	scn_time += delta

	# Bonus scenario: someone reaches in once the sweep is well underway.
	if scenarios[scn]["intrude"] and not intruded \
			and il.state == SafetyInterlock.State.CLEARING and il.progress > 0.45:
		il.occupant_alive = true
		intruded = true
		_spawn_person(Vector3(mouth_x + 0.35, floor_y + 0.28, 0.0))

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
