"""Render one BEAT of the HiveCell scenario cinematic to a PNG sequence.

Mirrors the Godot digital twin (godot/physics_demo.gd): the piston sweeps INANIMATE
items out the mouth, but a living occupant is never pushed — motion locks, or stops
and reverses. The steel shell + the wall fade to transparent so the interior reads
(objects being swept, or the person who is NOT swept). An SF5 beacon signals state.

Run headless on the built scene, one beat at a time (selected by the HC_BEAT env):
  HC_BEAT=clear  HC_DRAFT=1 flatpak run --filesystem=<repo> org.blender.Blender \
      --background <repo>/blender/hivecell.blend \
      --python <repo>/blender/scenario_cinematic.py

Beats: "clear" (sweep items out), "locked" (person inside -> no motion),
"intrude" (person reaches in mid-sweep -> stop & reverse). Frames land in
renders/beats/<beat>/f_####.png; blender/render_cinematic.sh drives all three,
burns in titles/status with ffmpeg, and concatenates renders/cinematic.mp4.

HC_DRAFT=1 -> Workbench (near-instant, to review motion). HC_DRAFT=0 -> EEVEE quality.
"""
import bpy
import os
import math
import random
from mathutils import Vector

BEAT = os.environ.get("HC_BEAT", "clear")
DRAFT = os.environ.get("HC_DRAFT", "1") == "1"
FPS = 24
SAMPLES = int(os.environ.get("HC_SAMPLES", "4"))   # EEVEE TAA (a moving shot hides low counts)
ROOT = "/home/eddy/Projects/HiveCell"
OUT = os.path.join(ROOT, "renders", "beats", BEAT, "f_")
random.seed(7)

sc = bpy.context.scene

# --- geometry read from the built scene (stays CAD-synced) -------------------
def bbox(name):
    o = bpy.data.objects[name]
    ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(v.x for v in ws), max(v.x for v in ws),
            min(v.y for v in ws), max(v.y for v in ws),
            min(v.z for v in ws), max(v.z for v in ws))

sh = bbox("CapsuleShell")
MOUTH_X = sh[0]                       # public opening (x = 0)
STROKE = 2.2                          # piston travel (cavity_length_m); face 2.2 -> 0
FLOOR_Z = -0.50                       # bore inner floor
HALF_W = 0.45                         # usable half-width in Y
GROUND_Z = bbox("Ground")[5]         # top of the exterior ground (~ -1.05)
CAV_X0, CAV_X1 = 0.35, 1.95           # where loose items may sit inside the bore

piston = bpy.data.objects["Piston"]
seals = bpy.data.objects["WiperSeals"]
focus = bpy.data.objects["Focus"]
cam = bpy.data.objects["Camera"]
spawned = []                          # objects created for this beat (rigid bodies)


def darken_backdrop():
    """The build's camera backdrop is a pale studio grey — against ghosted-glass
    transparency it washes out. Swap it dark (like the twin) so the revealed
    interior + swept items read with contrast; the HDRI still lights the steel."""
    w = sc.world
    if not w or not w.node_tree:
        return
    for n in w.node_tree.nodes:
        if n.type == "MIX" and len(n.inputs) > 7:      # camera-ray backdrop = input[7]
            n.inputs[7].default_value = (0.05, 0.06, 0.08, 1.0)

darken_backdrop()


# --- material helpers --------------------------------------------------------
def principled(mat):
    return mat.node_tree.nodes.get("Principled BSDF")

def make_alpha_animatable(mat):
    """Let a material fade: EEVEE-Next needs BLENDED render method + blend_method."""
    if hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "show_transparent_back"):
        mat.show_transparent_back = False

def key_alpha(mat, frame, a):
    inp = principled(mat).inputs["Alpha"]
    inp.default_value = a
    inp.keyframe_insert("default_value", frame=frame)

def new_pbr(name, color, rough=0.7, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = principled(m)
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


# --- SF5 beacon: an emissive sphere above the mouth --------------------------
def build_beacon():
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(MOUTH_X - 0.28, 0.0, 0.78))
    b = bpy.context.active_object
    b.name = "Beacon"
    for p in b.data.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new("BeaconMat")
    m.use_nodes = True
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes["Material Output"]
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    b.data.materials.append(m)
    return b, em

def key_beacon(em, frame, color, strength):
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Color"].keyframe_insert("default_value", frame=frame)
    em.inputs["Strength"].default_value = strength
    em.inputs["Strength"].keyframe_insert("default_value", frame=frame)

GREEN = (0.15, 0.75, 0.25)
RED = (0.95, 0.12, 0.08)
ORANGE = (1.0, 0.55, 0.05)
AMBER = (1.0, 0.62, 0.26)              # ADR-0014 warm night-glow (occupied / sleep-safe)


# --- ADR-0014 interior luminaire: flush crown strip (light + status) ---------
def build_luminaire():
    """Emissive strip at the bore crown running along X (from the CAD/manifest dims),
    plus a co-located strip area light so it actually washes the interior with its
    colour. Carries the warm night-glow + the state colour, visible through the mouth."""
    margin, width, crown = 0.15, 0.14, 0.55        # luminaire_end_margin / width / crown (m)
    x0, x1 = MOUTH_X + margin, MOUTH_X + STROKE - margin
    cx, length = (x0 + x1) * 0.5, (x1 - x0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = "Luminaire"
    o.scale = (length, width, 0.02)
    bpy.ops.object.transform_apply(scale=True)     # zeroes location -> set it after
    o.location = (cx, 0.0, crown - 0.05)
    m = bpy.data.materials.new("LuminaireMat")
    m.use_nodes = True
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    o.data.materials.append(m)
    bpy.ops.object.light_add(type="AREA", location=(cx, 0.0, crown - 0.05))
    light = bpy.context.active_object
    light.name = "LuminaireLight"
    light.data.shape = "RECTANGLE"
    light.data.size = 0.18
    light.data.size_y = length                     # a long strip light down the bore
    return em, light


def key_lum(lum, frame, color, em_strength, energy):
    # scaled up so the cell's OWN light characterises the interior (external key/sun
    # are dimmed for scenario mode, so this reads as the dominant interior source).
    em, light = lum
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Color"].keyframe_insert("default_value", frame=frame)
    em.inputs["Strength"].default_value = em_strength * 0.5   # keep the bar's COLOUR (no white clip)
    em.inputs["Strength"].keyframe_insert("default_value", frame=frame)
    light.data.color = color
    light.data.keyframe_insert("color", frame=frame)
    light.data.energy = energy * 6.0                          # the wash carries the intensity
    light.data.keyframe_insert("energy", frame=frame)


# --- props -------------------------------------------------------------------
def add_item(pos, size, color):
    # NB: transform_apply(scale=True) also zeroes location in Blender 5.2, so set
    # the location AFTER applying scale.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = "Item"
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.location = pos
    o.data.materials.append(new_pbr("ItemMat", color, rough=0.8))
    o.rotation_euler = (0, 0, random.uniform(-1.0, 1.0))
    spawned.append(o)
    return o

def add_person(cx):
    """A simple readable human lying along X: torso capsule + head + a raised knee."""
    parts = []
    skin = new_pbr("Skin", (0.86, 0.44, 0.38), rough=0.6)
    cloth = new_pbr("Cloth", (0.24, 0.34, 0.52), rough=0.9)
    # torso (capsule laid along X)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=0.95,
                                        location=(cx, 0.0, FLOOR_Z + 0.24))
    torso = bpy.context.active_object
    torso.rotation_euler = (0, math.radians(90), 0)
    torso.data.materials.append(cloth)
    parts.append(torso)
    # head toward the mouth (-X) so it reads through the opening from the front
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15,
                                         location=(cx - 0.62, 0.0, FLOOR_Z + 0.20))
    head = bpy.context.active_object
    head.data.materials.append(skin)
    parts.append(head)
    # a bent knee (deeper end), so the silhouette reads as a person, not a log
    bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.5,
                                        location=(cx + 0.42, 0.0, FLOOR_Z + 0.34))
    knee = bpy.context.active_object
    knee.rotation_euler = (0, math.radians(-35), 0)
    knee.data.materials.append(cloth)
    parts.append(knee)
    for o in parts:
        for p in o.data.polygons:
            p.use_smooth = True
    person = bpy.data.objects.new("Person", None)
    sc.collection.objects.link(person)
    for o in parts:
        o.parent = person
    spawned.append(person)
    for o in parts:
        spawned.append(o)
    return person


# --- invisible rigid-body colliders: a bore trough + the ground --------------
def add_collider(name, size, loc):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)     # zeroes location -> set it after
    o.location = loc
    o.hide_render = True
    return o

def setup_rigidbody(frame_end, active_objs, animated_piston=True):
    if not sc.rigidbody_world:
        bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    coll = bpy.data.collections.get("RB") or bpy.data.collections.new("RB")
    rbw.collection = coll

    def add(o, kind):
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.rigidbody.object_add(type=kind)

    # bore trough (invisible): a THICK floor (no tunnelling) + two side rails keep
    # items in the bore until the piston sweeps them off the mouth end.
    # floor spans mouth(~0) -> back, so items pushed past the mouth fall clear
    floor = add_collider("BoreFloor", (STROKE + 0.05, 2 * HALF_W, 0.3),
                         (STROKE * 0.5 + 0.05, 0.0, FLOOR_Z - 0.15))
    railL = add_collider("BoreRailL", (STROKE + 0.4, 0.06, 0.4),
                        ((STROKE) * 0.5, -HALF_W - 0.03, FLOOR_Z + 0.18))
    railR = add_collider("BoreRailR", (STROKE + 0.4, 0.06, 0.4),
                        ((STROKE) * 0.5, HALF_W + 0.03, FLOOR_Z + 0.18))
    for o in (floor, railL, railR):
        add(o, "PASSIVE")
        o.rigid_body.friction = 0.8
    # ground the ejected items land on
    add(bpy.data.objects["Ground"], "PASSIVE")
    bpy.data.objects["Ground"].rigid_body.friction = 0.9
    # piston as an animated (kinematic) passive collider so it shoves the items
    if animated_piston:
        add(piston, "PASSIVE")
        piston.rigid_body.kinematic = True
        piston.rigid_body.collision_shape = "CONVEX_HULL"
    # loose items are dynamic
    for o in active_objs:
        add(o, "ACTIVE")
        o.rigid_body.mass = 1.0
        o.rigid_body.friction = 0.7
        o.rigid_body.collision_shape = "BOX"

    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = frame_end
    bpy.ops.ptcache.free_bake_all()
    bpy.ops.ptcache.bake_all(bake=True)


# --- camera move -------------------------------------------------------------
def key_cam(frame, cloc, floc):
    cam.location = cloc
    cam.keyframe_insert("location", frame=frame)
    focus.location = floc
    focus.keyframe_insert("location", frame=frame)


def key_piston(frame, x):
    piston.location.x = x
    piston.keyframe_insert("location", index=0, frame=frame)
    seals.location.x = x
    seals.keyframe_insert("location", index=0, frame=frame)


# =============================================================================
# BEATS
# =============================================================================
mat_steel = bpy.data.materials["Steel"]
# The WALL stays opaque (a big semi-transparent panel just fogs the frame and
# washes the items). Only the SHELL fades to a ghosted glass; we view the interior
# through the mouth OPENING in the opaque wall, looking down into the bore.
SHELL_GHOST = 0.24


def recolor():
    """The build is all-stainless greys, so the shell, piston and wall blur together.
    Give the key parts distinct hues so they read apart in the scenario cinematic."""
    def setcol(name, rgb, metal=None, rough=None):
        m = bpy.data.materials.get(name)
        if not m:
            return
        b = principled(m)
        b.inputs["Base Color"].default_value = (*rgb, 1.0)
        if metal is not None:
            b.inputs["Metallic"].default_value = metal
        if rough is not None:
            b.inputs["Roughness"].default_value = rough
    setcol("Steel", (0.55, 0.62, 0.72), metal=1.0)        # bore/shell: cool steel
    setcol("PistonSteel", (0.86, 0.63, 0.26), metal=1.0)  # piston: warm gold, distinct
    setcol("Wall", (0.72, 0.68, 0.60), metal=0.0, rough=0.9)   # wall: warm matte concrete
    setcol("Magazine", (0.30, 0.33, 0.38), metal=1.0)     # magazine/chain: dark steel
    setcol("Chain", (0.40, 0.43, 0.48), metal=1.0)


def dim_external():
    """Scenario mode: turn the studio key/sun down so the cell's own interior luminaire
    (ADR-0014) reads as the dominant interior light, not a washed-out studio product."""
    k = bpy.data.objects.get("Key")
    if k:
        k.data.energy *= 0.30
    s = bpy.data.objects.get("Sun")
    if s:
        s.data.energy *= 0.45
    w = sc.world                                    # dim the studio HDRI fill too
    if w and w.node_tree:
        bg = w.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[1].default_value *= 0.4


recolor()
dim_external()
beacon, em = build_beacon()
lum = build_luminaire()


def reveal_shell(f0, f1):
    make_alpha_animatable(mat_steel)   # only when a beat actually ghosts the shell
    key_alpha(mat_steel, 1, 1.0)
    key_alpha(mat_steel, f0, 1.0)
    key_alpha(mat_steel, f1, SHELL_GHOST)


def beat_clear():
    """Empty of life: fade the shell/wall to reveal 3 items, sweep them out the mouth."""
    end = 100                             # ~4 s at 24 fps
    # fixed, well-spaced items resting on the bore floor (no overlap -> none get
    # flung out during the physics settle before the sweep)
    specs = [(0.95, -0.14, 0.26, (0.92, 0.30, 0.22)),   # saturated, so they read
             (1.40, 0.15, 0.24, (0.20, 0.55, 0.95)),
             (1.82, -0.06, 0.28, (0.98, 0.78, 0.15))]
    items = [add_item((x, y, FLOOR_Z + s * 0.5 + 0.02), (s, s, s), c)
             for (x, y, s, c) in specs]
    # look into the mouth, slightly elevated so the bore FLOOR (where the items sit)
    # reads through the opening; the piston then advances toward us and fills it.
    key_cam(1, (-4.2, -0.8, 0.75), (1.1, 0.0, -0.35))
    key_cam(end, (-3.0, -0.5, 0.35), (1.3, 0.0, -0.42))
    # No shell reveal — looking straight through the mouth the interior is already
    # fully visible, so the steel shell stays solid.
    # piston: brief hold -> sweep to flush -> hold -> redeploy
    key_piston(1, 0.0); key_piston(15, 0.0)
    key_piston(65, -STROKE); key_piston(75, -STROKE); key_piston(end, 0.0)
    # beacon: green -> red (moving) -> orange (flush) -> green
    key_beacon(em, 1, GREEN, 2.0); key_beacon(em, 15, GREEN, 2.0)
    key_beacon(em, 22, RED, 4.0); key_beacon(em, 65, RED, 4.0)
    key_beacon(em, 72, ORANGE, 3.0); key_beacon(em, 85, ORANGE, 3.0)
    key_beacon(em, 95, GREEN, 2.0)
    # interior luminaire (ADR-0014): green (available) -> red (in-movement) -> green.
    key_lum(lum, 1, GREEN, 3.0, 12.0); key_lum(lum, 15, GREEN, 3.0, 12.0)
    key_lum(lum, 22, RED, 3.5, 16.0); key_lum(lum, 72, RED, 3.5, 16.0)
    key_lum(lum, 85, GREEN, 3.0, 12.0)
    setup_rigidbody(end, items)
    return end


def beat_locked():
    """A person lies inside. Life detected -> the piston never moves. Beacon alarms."""
    end = 84                              # ~3.5 s
    add_person(1.0)                       # head toward the mouth, visible through it
    key_cam(1, (-4.2, -0.8, 0.75), (1.05, 0.0, -0.35))
    key_cam(end, (-3.4, -0.6, 0.5), (1.1, 0.0, -0.4))
    key_piston(1, 0.0); key_piston(end, 0.0)         # locked: no motion
    # beacon: green -> flashing-red alarm (hard strobe) while life is present
    key_beacon(em, 1, GREEN, 2.0); key_beacon(em, 22, GREEN, 2.0)
    f = 28
    while f < end:                                    # hard on/off strobe
        key_beacon(em, f, RED, 5.5); key_beacon(em, f + 6, RED, 0.15)
        f += 12
    # interior luminaire (ADR-0014): warm amber the whole stay (occupied / sleep-safe),
    # NOT the external beacon's red alarm — two audiences.
    key_lum(lum, 1, AMBER, 2.5, 10.0); key_lum(lum, end, AMBER, 2.5, 10.0)
    return end


def beat_intrude():
    """Sweep starts on a pod proved empty; someone reaches in -> stop & reverse."""
    end = 104                             # ~4.3 s
    items = [add_item((x, y, FLOOR_Z + 0.105), (0.2, 0.2, 0.2), (0.7, 0.55, 0.35))
             for (x, y) in ((1.2, -0.12), (1.65, 0.1))]
    person = add_person(0.7)              # reaches in AT the mouth
    intr = 52                             # intrusion frame
    for o in [person] + list(person.children):
        o.hide_render = True; o.keyframe_insert("hide_render", frame=intr - 6)
        o.hide_render = False; o.keyframe_insert("hide_render", frame=intr)
    key_cam(1, (-4.2, -0.8, 0.75), (1.0, 0.0, -0.35))
    key_cam(end, (-3.4, -0.6, 0.5), (0.7, 0.0, -0.4))
    # piston: advance toward the mouth, then reverse hard back out on intrusion
    key_piston(1, 0.0); key_piston(12, 0.0)
    key_piston(intr, -1.15)                           # mid-sweep when the arm intrudes
    key_piston(90, 0.0); key_piston(end, 0.0)         # stop & reverse to safe
    key_beacon(em, 1, GREEN, 2.0); key_beacon(em, 12, GREEN, 2.0)
    key_beacon(em, 18, RED, 4.0); key_beacon(em, intr - 2, RED, 4.0)
    f = intr                                          # alarm strobe on intrusion
    while f < end:
        key_beacon(em, f, RED, 5.5); key_beacon(em, f + 6, RED, 0.15)
        f += 12
    # interior luminaire: red while sweeping (empty) -> warm amber the instant life is
    # detected (machine yields to the occupant).
    key_lum(lum, 1, GREEN, 3.0, 12.0); key_lum(lum, 12, GREEN, 3.0, 12.0)
    key_lum(lum, 18, RED, 3.5, 16.0); key_lum(lum, intr - 2, RED, 3.5, 16.0)
    key_lum(lum, intr + 2, AMBER, 2.5, 10.0); key_lum(lum, end, AMBER, 2.5, 10.0)
    setup_rigidbody(intr, items)                      # items only pushed during forward stroke
    return end


BEATS = {"clear": beat_clear, "locked": beat_locked, "intrude": beat_intrude}
end = BEATS[BEAT]()

# --- render settings ---------------------------------------------------------
sc.frame_start = 1
sc.frame_end = end
sc.render.fps = FPS
# HC_LOWRES=1 -> 960x540 EEVEE for fast look-dev iteration; else 720p quality.
LOWRES = os.environ.get("HC_LOWRES", "0") == "1"
RES = (960, 540) if (DRAFT or LOWRES) else (1280, 720)
sc.render.resolution_x, sc.render.resolution_y = RES

if DRAFT:
    sc.render.engine = "BLENDER_WORKBENCH"
    for m in bpy.data.materials:
        if m.use_nodes:
            b = principled(m)
            if b:
                m.diffuse_color = b.inputs["Base Color"].default_value
    d = sc.display.shading
    d.light = "STUDIO"; d.color_type = "MATERIAL"; d.show_shadows = True; d.show_cavity = True
    sc.display.render_aa = "FXAA"
    # Workbench ignores emission/alpha; the draft is only to check motion + physics.
else:
    try:
        sc.eevee.taa_render_samples = SAMPLES
        sc.eevee.use_raytracing = True
    except Exception:
        pass

sc.render.image_settings.file_format = "PNG"
sc.render.filepath = OUT
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# HC_STILL="60,120,165" -> render just those frames as stills (fast EEVEE preview).
still = os.environ.get("HC_STILL", "")
if still:
    for fr in [int(x) for x in still.split(",")]:
        sc.frame_set(fr)
        sc.render.filepath = OUT + ("%04d" % fr)
        print("scenario_cinematic: still beat=%s frame=%d" % (BEAT, fr))
        bpy.ops.render.render(write_still=True)
    print("scenario_cinematic: stills done", BEAT)
else:
    print("scenario_cinematic: beat=%s frames=1..%d draft=%s -> %s" % (BEAT, end, DRAFT, OUT))
    bpy.ops.render.render(animation=True)
    print("scenario_cinematic: done", BEAT)
