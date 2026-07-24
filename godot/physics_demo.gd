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
const SAFE_CONTACT_N := 120.0   ## SF2 hard force cap: below the ~150 N powered-door
                                ## limit, with margin for vulnerable occupants. Tunable.
const PERSON_HALF_X := 0.72     ## half-length of the lying person along X (capsule)

var il := SafetyInterlock.new()

var stroke := 2.2          ## piston travel, from manifest
var floor_y := -0.5        ## inner-bore floor Y, from the shell mesh
var half_w := 0.4          ## usable half-width (Z) inside the bore
var mouth_x := 0.0         ## public opening, shell min-x
var cavity_x0 := 0.15      ## just inside the mouth
var cavity_x1 := 2.0       ## just in front of the deployed piston face

## Siting (ADR-0013 / SAFETY.md): the cell is set INTO a wall with its mouth sill
## ~500 mm above ground, so ejected inanimate items fall CLEAR onto a forgiving
## surface (they physically drop `sill_height` to the ground here). From manifest.
var sill_height := 0.5     ## meters, bore floor above ground (mouth sill height)
var ground_y := -1.0       ## world Y of the ground (= floor_y - sill_height)

## Rigid-chain drive, ported from the old twin: the exposed column spans the
## (moving) piston rear to the (fixed) magazine mouth; its length is physical
## (chain coils into the magazine). From manifest.
var magazine_front := 2.56 ## meters, fixed chain-magazine mouth
var piston_rear_deployed := 2.5  ## meters, piston rear at the deployed pose
var chain_w := 0.06        ## meters (Y)
var chain_h := 0.06        ## meters (Z)
var column: MeshInstance3D
var column_mesh: BoxMesh

## Interior luminaire (ADR-0014): a flush crown strip carrying the warm night-glow +
## state colour. From manifest; the twin builds it procedurally (like ChainColumn).
var lum_length := 1.9      ## strip length along X
var lum_width := 0.14      ## CAD fixture width along Z (manifest)
var lum_face_wid := 0.20   ## emitting-panel width that reads from the bore (matches Blender)
var lum_margin := 0.15     ## setback from the cavity ends (X)
var lum_crown := 0.55      ## bore crown / ceiling plane (Y up)

## Rounded-rectangle profile (mirrors the CAD capsule + Blender wall opening).
var corner_radius := 0.125 ## CAD fillet on the 4 long corners
var wall_thickness := 0.006

var piston: AnimatableBody3D
var spawned: Array[Node] = []
var person: Node3D = null
var title_label: Label
var status_label: Label
var luminaire: MeshInstance3D         ## ADR-0014 interior light + status strip (crown)
var luminaire_mat: StandardMaterial3D

var scenarios := [
	{"title": "1 · EMPTY POD — no one, nothing inside", "things": 0,  "person": false, "intrude": false},
	{"title": "2 · ONE ITEM LEFT — no one inside",       "things": 1,  "person": false, "intrude": false},
	{"title": "3 · LOTS OF STUFF — no one inside",        "things": 10, "person": false, "intrude": false},
	{"title": "4 · SOMEONE INSIDE — motion LOCKED",       "things": 0,  "person": true,  "intrude": false},
	{"title": "5 · INTRUSION MID-SWEEP — stop & reverse", "things": 2,  "person": false, "intrude": true},
	{"title": "6 · SENSOR BLIND — safety edge catches",   "things": 0,  "person": true,  "intrude": false, "sf1_blind": true},
]
var scn := -1
var scn_time := 0.0
var saw_motion := false
var intruded := false
var sf2_tripped := false
var drive_load := 0.0   ## current estimated contact force (N), shown on the HUD


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
		sill_height = float(d.get("sill_height_m", sill_height))
		magazine_front = float(d.get("magazine_front_m", magazine_front))
		piston_rear_deployed = float(d.get("piston_rear_deployed_m", piston_rear_deployed))
		chain_w = float(d.get("chain_width_m", chain_w))
		chain_h = float(d.get("chain_height_m", chain_h))
		lum_length = float(d.get("luminaire_length_m", lum_length))
		lum_width = float(d.get("luminaire_width_m", lum_width))
		lum_margin = float(d.get("luminaire_end_margin_m", lum_margin))
		lum_crown = float(d.get("luminaire_crown_m", lum_crown))
		corner_radius = float(d.get("corner_radius_m", corner_radius))
		wall_thickness = float(d.get("wall_thickness_m", wall_thickness))


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
	ground_y = floor_y - sill_height  # mouth sill ~500 mm above ground (ADR-0013)

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
	# SF3 wiper seals: elastomer lip rings that fill the 3mm gap, riding with the
	# piston. Visual only (piston collision already covers the plug).
	var seals := MeshInstance3D.new()
	seals.mesh = load(MODELS + "WiperSeals.obj")
	seals.material_override = _mat(Color(0.11, 0.11, 0.13), 0.95)
	piston.add_child(seals)
	var pcs := CollisionShape3D.new()
	pcs.shape = piston_mesh.create_convex_shape()
	piston.add_child(pcs)
	add_child(piston)
	_place_piston()

	# Rigid-chain exposed column: links lock straight to push the piston and coil
	# into the magazine to retract, so its exposed length is physical (not a rod).
	column_mesh = BoxMesh.new()
	column_mesh.size = Vector3(0.001, chain_w, chain_h)
	column = MeshInstance3D.new()
	column.mesh = column_mesh
	column.material_override = _mat(Color(0.55, 0.57, 0.60), 0.4, 0.9)
	add_child(column)
	_update_chain()

	# Ground: a large forgiving surface `sill_height` below the bore floor, so ejected
	# items fall CLEAR of the mouth (the H4 siting rationale). Its top is at ground_y.
	_static_box(Vector3(10.0, 0.2, 8.0), Vector3(stroke * 0.5, ground_y - 0.1, 0.0),
		_mat(Color(0.17, 0.19, 0.18), 1.0))
	# The cell is set INTO a wall at the mouth plane, mouth sill ~500 mm up.
	_build_wall(aabb)

	# ADR-0014 interior luminaire: a single emissive panel recessed FLUSH into the bore
	# ceiling (not hanging below it), running along X, carrying the warm night-glow + the
	# state colour. Mirrors the Blender build: widened to the emitting-face width, its face
	# level with the crown, set into a faked shallow pocket. Fixed (not on the piston).
	var lum_thick := 0.006
	var lum_cx := mouth_x + lum_margin + lum_length * 0.5
	# faked crown pocket: a shallow dark recess the panel sits in, so it reads as inset
	var pocket_size := Vector3(lum_length + 0.03, lum_thick * 3.0, lum_face_wid + 0.03)
	var pocket_mi := _box_mesh_inst(pocket_size, _mat(Color(0.05, 0.05, 0.06), 0.9))
	pocket_mi.position = Vector3(lum_cx, lum_crown + lum_thick, 0.0)
	add_child(pocket_mi)
	var lbm := BoxMesh.new()
	lbm.size = Vector3(lum_length, lum_thick, lum_face_wid)
	luminaire = MeshInstance3D.new()
	luminaire.mesh = lbm
	luminaire_mat = StandardMaterial3D.new()
	luminaire_mat.emission_enabled = true
	luminaire.material_override = luminaire_mat
	luminaire.position = Vector3(lum_cx, lum_crown - lum_thick * 0.5, 0.0)   # face flush at the crown
	add_child(luminaire)

	# Lights + environment.
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-62, -28, 0)
	sun.light_energy = 1.25
	sun.shadow_enabled = true   # shadows make the ~500 mm elevation read clearly
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

	# Front-ish 3/4 from the room side (-X), elevated: faces INTO the mouth so the
	# hole, the bore/piston (through the see-through wall + shell), and items falling
	# clear in the foreground all read; the ~500 mm sill-above-ground stays visible.
	var cam := Camera3D.new()
	cam.position = Vector3(-2.6, 1.0, 2.9)
	add_child(cam)
	cam.look_at(Vector3(0.6, floor_y - 0.15, 0.0), Vector3.UP)
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


func _build_wall(aabb: AABB) -> void:
	# The cell is set INTO a wall: a facade at the mouth plane with a ROUNDED-rectangle
	# opening that hugs the capsule's filleted corners (mirrors the Blender boolean), the
	# sill `sill_height` above the ground. Built as a CSG panel minus a rounded-rect cutter,
	# with collision so ejected items can't tunnel. Opening sized from the shell AABB.
	var reveal := 0.03
	var ob := aabb.position.y - reveal                    # opening bottom (barrel outer)
	var ot := aabb.position.y + aabb.size.y + reveal      # opening top
	var ohw := aabb.size.z * 0.5 + reveal                 # opening half-width (Z)
	var ohh := (ot - ob) * 0.5                            # opening half-height (Y)
	var whw := ohw + 2.4                                  # wall half-span (Z)
	var wtop := ot + 1.4                                  # wall top (Y)
	var fd := 0.25                                         # facade depth: X in [mouth_x, +fd]
	var cx := mouth_x + fd * 0.5
	# opening corner radius = cell OUTER fillet (corner_radius + wall) + the reveal gap
	var open_r: float = corner_radius + wall_thickness + reveal
	# Semi-transparent so it still reads as the wall the cell is set into, but never
	# hides the mouth, the mechanism, or items falling clear in front of it.
	var mat := _mat(Color(0.42, 0.44, 0.47), 0.9, 0.0, 0.28)

	var combiner := CSGCombiner3D.new()
	combiner.use_collision = true
	combiner.material_override = mat
	var panel := CSGBox3D.new()                           # solid facade: ground -> wall top
	panel.size = Vector3(fd, wtop - ground_y, 2.0 * whw)
	panel.position = Vector3(cx, (ground_y + wtop) * 0.5, 0.0)
	combiner.add_child(panel)
	var cutter := _rounded_rect_csg(ohw, ohh, open_r, fd + 0.2)
	cutter.operation = CSGShape3D.OPERATION_SUBTRACTION
	cutter.position = Vector3(cx, (ob + ot) * 0.5, 0.0)
	combiner.add_child(cutter)
	add_child(combiner)


func _rounded_rect_csg(hw: float, hh: float, r: float, depth: float) -> CSGCombiner3D:
	# A rounded-rectangle prism (axis along X): a cross of two boxes unioned with a cylinder
	# at each of the four corners. Used to cut the wall opening so it matches the capsule.
	r = minf(r, minf(hw, hh))
	var c := CSGCombiner3D.new()
	var bx := CSGBox3D.new()
	bx.size = Vector3(depth, 2.0 * (hh - r), 2.0 * hw)
	c.add_child(bx)
	var by := CSGBox3D.new()
	by.size = Vector3(depth, 2.0 * hh, 2.0 * (hw - r))
	c.add_child(by)
	for sy in [-1.0, 1.0]:
		for sz in [-1.0, 1.0]:
			var cyl := CSGCylinder3D.new()
			cyl.radius = r
			cyl.height = depth
			cyl.sides = 20
			cyl.rotation = Vector3(0.0, 0.0, PI * 0.5)    # height axis Y -> along X
			cyl.position = Vector3(0.0, sy * (hh - r), sz * (hw - r))
			c.add_child(cyl)
	return c


func _update_chain() -> void:
	# Column spans the (moving) piston rear to the (fixed) magazine mouth; the rest
	# is coiled in the magazine (total chain length conserved).
	var piston_rear := piston_rear_deployed - il.progress * stroke
	var col_len: float = maxf(magazine_front - piston_rear, 0.001)
	column_mesh.size = Vector3(col_len, chain_w, chain_h)
	column.position = Vector3((piston_rear + magazine_front) * 0.5, 0.0, 0.0)


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
	sf2_tripped = false
	_clear_scene_contents()

	# Fresh interlock so each scenario starts deployed and empty of state.
	il = SafetyInterlock.new()
	il.demo_seconds = 3.5
	il.hold_seconds = 1.0
	il.life_check_seconds = 0.6

	var s = scenarios[i]
	# SF1 now runs the REAL diverse-redundant fusion (ADR-0012, occupancy_fusion.gd):
	# the visual twin and the logic can't drift because life_present() reads this same
	# voter. Its four channels are driven from ground truth every frame in
	# _update_fusion(). A "blind" scenario models an SF1 false-negative (channels
	# healthy + fresh but not detecting), so SF2 (contact force) is the only catch left.
	il.fusion = OccupancyFusion.new()
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


func _piston_face_x() -> float:
	# Front face of the piston plug (its natural front is at x = stroke).
	return stroke - il.progress * stroke


## Estimate the contact force the drive is meeting (N). The key discriminator is
## YIELD, not magnitude: movable trash slides away so its resistance stays low and
## bounded; a NON-YIELDING body (a braced limb) makes force climb steeply with
## penetration, which is the crush SF2 must catch.
func _drive_load() -> float:
	var face_x := _piston_face_x()
	var load := 6.0   # baseline drive + seal drag
	for n in spawned:
		if n is RigidBody3D and is_instance_valid(n):
			var dx: float = n.position.x - face_x   # item ahead of the face is < 0
			if dx > -0.30 and dx < 0.04 and absf(n.position.z) < half_w + 0.15:
				load += 9.0 * n.mass                # movable trash: modest, bounded
	# A non-yielding occupant/limb: force rises fast as the face presses into it.
	if person != null and is_instance_valid(person):
		var pen: float = (person.position.x + PERSON_HALF_X) - face_x
		if pen > 0.0:
			load += 2200.0 * pen                    # steep -> exceeds the safe cap
	return load


func _scenario_done() -> bool:
	var s = scenarios[scn]
	if s.get("sf1_blind", false):
		# SF2 must have fired and reversed the sweep back out.
		return sf2_tripped and il.progress <= 0.05 and scn_time > 1.0
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
		intruded = true
		# The reach-in body is spawned; _update_fusion() sees it and the SF1 channels
		# light up (no separate occupant flag -- ground truth drives the same voter).
		_spawn_person(Vector3(mouth_x + 0.35, floor_y + 0.28, 0.0))

	# SF2: estimate the contact force the drive is meeting and set the independent
	# over-limit trip (separate from SF1 life-detection).
	drive_load = _drive_load()
	il.contact_over_limit = drive_load > SAFE_CONTACT_N
	if il.contact_over_limit:
		sf2_tripped = true

	_update_fusion()   # drive the SF1 channels from ground truth BEFORE the interlock steps

	il.step(delta)
	if il.state == SafetyInterlock.State.CLEARING or il.state == SafetyInterlock.State.REDEPLOY:
		saw_motion = true
	_place_piston()
	_update_chain()
	_update_luminaire()
	_update_hud()

	if _scenario_done() and scn_time > 2.0:
		_start_scenario((scn + 1) % scenarios.size())


func _update_fusion() -> void:
	# Keep the visual twin and SF1 logic in lockstep: the four diverse channels read
	# the SAME ground truth the scene shows (a living body in the bore), refreshed each
	# frame. A blind scenario is an SF1 false-negative -- channels healthy + fresh but
	# NOT detecting the present occupant -- leaving SF2 as the only catch.
	if il.fusion == null:
		return
	var blind: bool = scenarios[scn].get("sf1_blind", false)
	var life_here: bool = (person != null and is_instance_valid(person)) and not blind
	for c in il.fusion.channels:
		c.present = life_here   # all diverse channels see a warm, breathing, massed body
		c.age = 0.0             # sampled fresh this frame (no staleness fault)


## Compact per-channel SF1 readout for the HUD (radar / thermal / CO2 / load).
func _fusion_votes_str() -> String:
	if il.fusion == null:
		return "(none)"
	var abbr := {"radar_vitals": "radar", "thermal_ir": "thermal", "ndir_co2": "CO2", "load_bcg": "load"}
	var tag := ["clear", "OCC", "FLT"]
	var parts: Array[String] = []
	for c in il.fusion.channels:
		parts.append("%s=%s" % [abbr.get(c.name, c.name), tag[c.vote()]])
	return "  ".join(parts)


func _update_luminaire() -> void:
	# ADR-0014: the interior strip holds WARM AMBER while OCCUPIED (reassurance + the
	# sleep-safe night-glow). The status colours only show while the pod is EMPTY, so
	# green (available) / red (in-movement) never fall on a sleeper.
	var col: Color
	var energy := 1.2
	if il.life_present():
		col = Color(1.0, 0.62, 0.26)          # warm amber: occupied / safe (night-glow)
		energy = 0.9                          # low, so it doesn't prevent sleep
	elif il.state == SafetyInterlock.State.CLEARING \
			or il.state == SafetyInterlock.State.REDEPLOY \
			or il.state == SafetyInterlock.State.LIFE_CHECK:
		col = Color(0.95, 0.15, 0.1)          # red: in movement (empty pod) — warns intruders
		var t := Time.get_ticks_msec() / 1000.0
		energy = 0.8 + 1.6 * (0.5 + 0.5 * sin(t * 6.0 * TAU))
	elif il.state == SafetyInterlock.State.AVAILABLE:
		col = Color(0.2, 0.8, 0.32)           # green: available / ready to occupy
	else:
		col = Color(1.0, 0.55, 0.05)          # closed/hold — not really seen inside
		energy = 0.5
	luminaire_mat.albedo_color = col
	luminaire_mat.emission = col
	luminaire_mat.emission_energy_multiplier = energy


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
	var over := il.contact_over_limit
	title_label.text = str(scenarios[scn]["title"])
	title_label.add_theme_color_override("font_color",
		Color(1, 0.5, 0.45) if (life or over) else Color(0.6, 1, 0.7))
	var force_note := "  !! OVER LIMIT -> STOP & REVERSE" if over else ""
	var sig = ["READY", "MOVING", "CLOSED", "ALARM"][il.signal_level()]
	var moving := il.state == SafetyInterlock.State.CLEARING \
		or il.state == SafetyInterlock.State.REDEPLOY \
		or il.state == SafetyInterlock.State.LIFE_CHECK
	var lum_state := "warm amber (occupied)" if life else ("red (moving)" if moving else \
		("green (ready)" if il.state == SafetyInterlock.State.AVAILABLE else "— (closed)"))
	status_label.text = "Interlock: %s\nSF1 life: %s    Sweep: %d%%\nSF1 fusion (ADR-0012): %s\nSF2 force: %d N / %d N cap%s\nSF5 signal: %s\nADR-0014 interior light: %s" % [
		names[il.state], ("DETECTED" if life else "clear"), int(round(il.progress * 100.0)),
		_fusion_votes_str(),
		int(round(drive_load)), int(SAFE_CONTACT_N), force_note, sig, lum_state
	]
