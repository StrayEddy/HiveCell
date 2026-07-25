"""HiveCell narrative cinematic -- "One Night" (greybox animatic, Phase 1).

A single day-in-the-life story that REPLACES the old 3-beat safety reel as the
website hero video (see docs/ROADMAP.md / the cinematic storyboard). Arc:

  dusk  -> a person arrives at a wall of cells and lies down to sleep
  night -> the cell holds still, warm amber glow: it knows someone is inside
  dawn  -> he leaves (a bit of litter behind); the cell verifies it is empty,
           then the piston sweeps it clean, becomes flush wall, and reopens ready.

Wordless; one warm end card is burned in at assembly time (render_narrative.sh).

PHASE 1 = GREYBOX: blocking + timing + camera only, rendered in Workbench draft
(near-instant) so we can lock the edit before spending Cycles time on lighting
(Phase 2), the real character + materials (Phase 3), and the final render (Phase 4).
Everything here is deliberately crude: capsule people, flat-lit neighbour cells.

Run one pass headless on the built hero cell:
  HC_DRAFT=1 flatpak run --filesystem=<repo> org.blender.Blender \
      --background <repo>/blender/hivecell.blend \
      --python <repo>/blender/narrative_cinematic.py

Env:
  HC_DRAFT=1   Workbench (fast greybox)   HC_DRAFT=0  Cycles (later phases)
  HC_STEP=N    render every Nth frame (quick preview of the whole timeline)
  HC_STILL="120,600"  render just those frames as stills (fastest look check)
"""
import bpy
import os
import math
from mathutils import Vector

ROOT = "/home/eddy/Projects/HiveCell"
OUT = os.path.join(ROOT, "renders", "narrative", "f_")
DRAFT = os.environ.get("HC_DRAFT", "1") == "1"
FPS = 24
STEP = int(os.environ.get("HC_STEP", "1"))

sc = bpy.context.scene


# =============================================================================
# scene dimensions (read from the built hero cell so we stay CAD-synced)
# =============================================================================
def bbox(name):
    o = bpy.data.objects[name]
    ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(v.x for v in ws), max(v.x for v in ws),
            min(v.y for v in ws), max(v.y for v in ws),
            min(v.z for v in ws), max(v.z for v in ws))

sh = bbox("CapsuleShell")
MOUTH_X = sh[0]                      # public opening plane (~0)
STROKE = 2.2                         # piston travel (cavity_length_m); 0 open -> -STROKE flush
FLOOR_Z = -0.50                     # bore inner floor
OPEN_HH = (sh[5] - sh[4]) * 0.5     # hero opening half-height (Z)
OPEN_HW = (sh[3] - sh[2]) * 0.5     # hero opening half-width (Y)
OPEN_CZ = (sh[4] + sh[5]) * 0.5     # opening centre Z
GROUND_Z = bbox("Ground")[5]        # top of the exterior ground (~ -1.05)

CORNER_R = 0.131                    # cell outer corner radius (cavity 0.125 + wall, scene.json)
PITCH = 2 * OPEN_HW + 0.30          # cell-to-cell spacing (tight piers -> cells close together)
N_SIDE = 3                          # cells each side of the hero -> 7 total
WALL_TOP = sh[5] + 1.15             # facade top (Z)
FACADE_D = 0.25                     # facade depth in X (mouth .. +FACADE_D)

piston = bpy.data.objects["Piston"]
seals = bpy.data.objects["WiperSeals"]
focus = bpy.data.objects["Focus"]
cam = bpy.data.objects["Camera"]


# =============================================================================
# helpers (mirrors build_scene / scenario_cinematic idioms)
# =============================================================================
def principled(mat):
    return mat.node_tree.nodes.get("Principled BSDF")

def new_pbr(name, color, rough=0.7, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = principled(m)
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m

# NB: create the primitive at the ORIGIN, not at `center`. In Blender 5.2
# transform_apply(scale=True) also bakes+zeroes location, so adding at `center` and
# then setting location=center DOUBLES the position (the floating-cell bug).
def box(name, size, center, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    o.location = center
    if mat:
        o.data.materials.append(mat)
    return o

def cutbox(name, size, center):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    o.location = center
    return o

def rounded_rect_prism(name, hw, hh, r, cz, x0, x1, cy=0.0, seg=10):
    """A closed prism whose Y-Z cross-section is a rounded rectangle (half-width hw,
    half-height hh, corner radius r, centred on y=cy / z=cz), spanning x0..x1. Ported
    from build_scene -- used as a boolean cutter so the wall opening hugs the cell's
    filleted corners instead of a square hole."""
    r = min(r, hw, hh)
    corners = [(hw - r, hh - r, 0.0), (-(hw - r), hh - r, 90.0),
               (-(hw - r), -(hh - r), 180.0), (hw - r, -(hh - r), 270.0)]
    outline = []
    for cyk, czk, a0 in corners:
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            outline.append((cyk + r * math.cos(a), czk + r * math.sin(a)))
    n = len(outline)
    verts = [(x0, cy + y, cz + z) for (y, z) in outline] + \
            [(x1, cy + y, cz + z) for (y, z) in outline]
    faces = [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    faces.append(tuple(range(n)))
    faces.append(tuple(range(2 * n - 1, n - 1, -1)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    o = bpy.data.objects.new(name, mesh)
    sc.collection.objects.link(o)
    return o

def boolean_diff(target, cutter):
    m = target.modifiers.new(cutter.name + "_cut", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

def emissive_plane(name, size_xy, loc, rot, color, strength):
    """A downward/-X facing emissive quad used for the neighbour-cell state glow."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    # set object transforms directly (no transform_apply -- its location-baking in 5.2
    # was intermittently dropping the placement); emission needs no applied transform.
    o.scale = (size_xy[0], size_xy[1], 1.0)
    o.rotation_euler = rot
    o.location = loc
    m = bpy.data.materials.new(name + "Mat")
    m.use_nodes = True
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], nt.nodes["Material Output"].inputs["Surface"])
    o.data.materials.append(m)
    return o, em


# --- SF5 state palette --------------------------------------------------------
GREEN = (0.16, 0.72, 0.28)          # available
AMBER = (1.0, 0.62, 0.26)           # occupied / sleep-safe night-glow (ADR-0014)
RED = (0.92, 0.14, 0.10)            # moving
ORANGE = (1.0, 0.55, 0.06)          # closed / flush


# Per-cell state for the neighbours (hero k=0 is animated by the story). Every hole
# gets a REAL cell -- a duplicated shell + piston -- so the wall reads as live:
#   open     piston retracted, empty bore visible
#   occupied piston retracted, a sleeper inside
#   closed   piston swept flush -> its face IS the wall
NEIGHBOUR_STATE = {-3: "occupied", -2: "open", -1: "closed",
                   1: "closed", 2: "occupied", 3: "open"}


def duplicate_cell(k, piston_x):
    """Clone the hero shell + piston to neighbour column k (offset in Y); set the
    neighbour piston along X for its state (0 retracted/open, -STROKE swept/closed)."""
    y = k * PITCH
    for src_name in ("CapsuleShell", "Piston"):
        src = bpy.data.objects[src_name]
        o = src.copy()
        o.data = src.data.copy()
        sc.collection.objects.link(o)
        o.name = "%s_c%d" % (src_name, k)
        o.location = src.location.copy()
        o.location.y += y
        if src_name == "Piston":
            o.location.x += piston_x


def add_sleeper(k):
    """A static greybox occupant lying in neighbour cell k (torso + head, head -X)."""
    y = k * PITCH
    cloth = bpy.data.materials.get("ActorCloth") or new_pbr("ActorCloth", (0.26, 0.34, 0.50), 0.9)
    skin = bpy.data.materials.get("ActorSkin") or new_pbr("ActorSkin", (0.80, 0.52, 0.42), 0.6)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=1.0,
                                        location=(1.15, y, FLOOR_Z + 0.20))
    torso = bpy.context.active_object
    torso.name = "Sleeper_c%d" % k
    torso.rotation_euler = (0, math.radians(90), 0)
    torso.data.materials.append(cloth)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0.50, y, FLOOR_Z + 0.20))
    head = bpy.context.active_object
    head.name = "SleeperHead_c%d" % k
    head.data.materials.append(skin)
    for o in (torso, head):
        for p in o.data.polygons:
            p.use_smooth = True


# =============================================================================
# a WALL OF CELLS: a regular facade of rounded openings, each with a REAL cell
# behind it in a state (open / occupied / closed). Hero cell (k=0) keeps the
# imported shell+piston and is animated by the story.
# =============================================================================
def build_wall_of_cells():
    old = bpy.data.objects.get("Wall")
    if old:
        old.hide_render = True
        old.hide_viewport = True
    mat_wall = bpy.data.materials.get("Wall") or new_pbr("WallNarr", (0.42, 0.40, 0.38), rough=0.9)
    span_y = 2 * (N_SIDE * PITCH + OPEN_HW + 0.9)   # solid pier beyond the outermost cell
    cx = MOUTH_X + FACADE_D * 0.5
    facade = box("Facade", (FACADE_D, span_y, WALL_TOP - GROUND_Z),
                 (cx, 0.0, (GROUND_Z + WALL_TOP) * 0.5), mat_wall)

    reveal = 0.02
    for k in range(-N_SIDE, N_SIDE + 1):
        y = k * PITCH
        # ROUNDED opening that hugs the cell's filleted corners (not a square hole)
        cut = rounded_rect_prism("Open_%d" % k, OPEN_HW + reveal, OPEN_HH + reveal,
                                 CORNER_R + reveal, OPEN_CZ, MOUTH_X - 0.15,
                                 MOUTH_X + FACADE_D + 0.15, cy=y)
        boolean_diff(facade, cut)
        if k == 0:
            continue                                    # hero: imported cell, story-animated
        state = NEIGHBOUR_STATE[k]
        duplicate_cell(k, -STROKE if state == "closed" else 0.0)
        if state == "occupied":
            add_sleeper(k)


# =============================================================================
# ACTOR: a greybox person (capsule body + head + bag) on a keyframable root.
# Postures are set by keying the root location + the body's tilt: STAND upright,
# LIE flat along X inside the bore. Crude on purpose (Phase 3 replaces it).
# =============================================================================
def build_actor():
    skin = new_pbr("ActorSkin", (0.80, 0.52, 0.42), rough=0.6)
    cloth = new_pbr("ActorCloth", (0.26, 0.34, 0.50), rough=0.9)
    bagm = new_pbr("ActorBag", (0.45, 0.32, 0.20), rough=0.85)

    root = bpy.data.objects.new("Actor", None)
    sc.collection.objects.link(root)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=1.0, location=(0, 0, 0.62))
    body = bpy.context.active_object
    body.name = "ActorBody"
    body.data.materials.append(cloth)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, 1.27))
    head = bpy.context.active_object
    head.name = "ActorHead"
    head.data.materials.append(skin)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.28, 0.0, 0.28))
    bag = bpy.context.active_object
    bag.name = "ActorBag"
    bag.scale = (0.22, 0.16, 0.26)
    bpy.ops.object.transform_apply(scale=True)
    bag.location = (0.28, 0.0, 0.28)
    bag.data.materials.append(bagm)
    for o in (body, head, bag):
        for p in o.data.polygons:
            p.use_smooth = True
        o.parent = root
    return {"root": root, "body": body, "head": head, "bag": bag}


def key_obj(o, frame, loc=None, rot=None, hide=None):
    if loc is not None:
        o.location = loc
        o.keyframe_insert("location", frame=frame)
    if rot is not None:
        o.rotation_euler = rot
        o.keyframe_insert("rotation_euler", frame=frame)
    if hide is not None:
        o.hide_render = hide
        o.keyframe_insert("hide_render", frame=frame)
        o.hide_viewport = hide
        o.keyframe_insert("hide_viewport", frame=frame)


def key_cam(frame, cloc, floc):
    cam.location = cloc
    cam.keyframe_insert("location", frame=frame)
    focus.location = floc
    focus.keyframe_insert("location", frame=frame)


def key_lens(frame, mm):
    # keyframe focal length so one shot can tighten without moving the camera in; key
    # 32 on the adjacent frames of neighbouring shots so the change is a clean cut.
    cam.data.lens = mm
    cam.data.keyframe_insert("lens", frame=frame)


def key_piston(frame, x):
    piston.location.x = x
    piston.keyframe_insert("location", index=0, frame=frame)
    seals.location.x = x
    seals.keyframe_insert("location", index=0, frame=frame)


def cut_hold(frame):
    """Hard CUT between shots. Each shot's end key and the next shot's start key sit
    on ADJACENT frames (end at f+span, next start at f+span+1), so no intermediate
    frame is ever rendered between them -- the cut is inherent. Kept as a no-op hook
    in case a future shot needs an explicit hold."""
    return


# =============================================================================
# TIMELINE  (24 fps, hard cuts between shots). Frame ranges per shot.
# =============================================================================
GROUND_STAND = GROUND_Z - 0.12      # root at the feet -> body bottom plants on the ground
SILL_Z = sh[4]                      # mouth sill height
STREET_X = -1.6                     # people walk here, in front of the wall

neigh = build_wall_of_cells()
A = build_actor()
root, body, head, bag = A["root"], A["body"], A["head"], A["bag"]
cam.data.lens = 32                              # wider than the night-hero default, for the street


def hide_actor(frame, hidden):
    """Hide the actor by keying its MESHES (the root is an Empty, which never renders,
    so keying the root alone leaves the body/head/bag on screen -- the reappearing-
    sleeper bug). Key each child mesh's render + viewport visibility."""
    for o in (body, head, bag):
        o.hide_render = hidden
        o.keyframe_insert("hide_render", frame=frame)
        o.hide_viewport = hidden
        o.keyframe_insert("hide_viewport", frame=frame)

# Postures tip the WHOLE rig as one rigid unit by rotating the ROOT about Y -- never
# a single part (rotating just the body while the head kept its standing offset was
# the "head flies above the wall" bug). Root sits at the feet; local +Z is "up the
# body", so a -90 deg Y-rotation lays the figure along -X (head toward the mouth).
def stand(frame, x, y):
    key_obj(root, frame, loc=(x, y, GROUND_STAND), rot=(0, 0, 0))

def sit(frame, x=-0.1):
    # perched on the sill, half-reclined -- the in-between of stand and lie
    key_obj(root, frame, loc=(x, 0.0, SILL_Z + 0.05), rot=(0, math.radians(-42), 0))

def lie(frame, cx=1.0):
    # flat on the bore floor; root offset so the torso centres on cx, head toward -X
    key_obj(root, frame, loc=(cx + 0.60, 0.0, FLOOR_Z + 0.20), rot=(0, math.radians(-90), 0))


shots = []   # (name, start, end) for the log

# ---- S1  establish wide: the living wall (dusk) ----  0:00
f = 1
key_cam(f, (-11.5, -0.7, 1.5), (0.0, 0.0, 0.35))
key_cam(f + 130, (-11.0, 0.2, 1.4), (0.0, 0.5, 0.30))
hide_actor(f, True)                            # actor not on screen yet
stand(f, STREET_X - 3.0, -3.2)
shots.append(("S1_establish", f, f + 143))
f += 144

# ---- S2  the person notices a free cell ----  ~0:06
key_cam(f, (-4.2, -2.2, 0.7), (STREET_X, -1.4, 0.4))
key_cam(f + 95, (-3.6, -1.6, 0.6), (STREET_X, -0.4, 0.4))
hide_actor(f, False)
stand(f, STREET_X, -1.8)
stand(f + 95, STREET_X + 0.3, -0.3)            # drifts toward the hero cell (y=0)
shots.append(("S2_notices", f, f + 95))
cut_hold(f)
f += 96

# ---- S3  greeting + sits on the sill, swings in ----  ~0:10
key_cam(f, (-3.0, -1.5, 0.6), (MOUTH_X, 0.0, SILL_Z))
key_cam(f + 119, (-2.4, -1.0, 0.5), (MOUTH_X + 0.4, 0.0, SILL_Z - 0.1))
stand(f, STREET_X + 0.3, 0.0)
stand(f + 40, -0.5, 0.0)                       # steps up to the mouth
sit(f + 70, -0.1)                              # perches on the sill
lie(f + 119, 1.0)                              # swings in, settling toward lying
shots.append(("S3_enter", f, f + 119))
cut_hold(f)
f += 120

# ---- S4  settles inside, warm amber; the mouth STAYS open ----  ~0:15
key_cam(f, (-3.4, -1.4, 0.2), (1.0, 0.0, FLOOR_Z + 0.3))
key_cam(f + 95, (-3.0, -1.1, 0.1), (1.1, 0.0, FLOOR_Z + 0.25))
lie(f, 1.0)
lie(f + 95, 1.0)
shots.append(("S4_settle", f, f + 95))
cut_hold(f)
f += 96

# ---- S5  night passes (time-lapse hold on the wall) ----  ~0:19
key_cam(f, (-8.6, -1.8, 1.7), (0.0, 0.0, 0.3))
key_cam(f + 119, (-8.4, -1.2, 1.6), (0.0, 0.2, 0.3))
lie(f, 1.0); lie(f + 119, 1.0)
shots.append(("S5_night", f, f + 119))
cut_hold(f)
f += 120

# ---- S6  dawn: he wakes, gathers the bag, leaves (litter behind) ----  ~0:24
key_cam(f, (-3.2, -1.4, 0.3), (0.8, 0.0, FLOOR_Z + 0.3))
key_cam(f + 143, (-3.4, -1.8, 0.6), (STREET_X, 0.6, 0.4))
lie(f, 1.0)
lie(f + 30, 1.0)
# sit up on the sill, then stand and walk away down the street
sit(f + 60, -0.1)
stand(f + 90, -0.5, 0.0)
stand(f + 143, STREET_X, 1.8)
shots.append(("S6_dawn_leave", f, f + 143))
cut_hold(f)
f += 144

# ---- S7  THE REVEAL: the piston sweeps the cell clean (interior) ----  ~0:30
hide_actor(f, True)                            # he is gone; only the litter remains
# same elevated 3/4 framing as S8 (reads well): watch the whole sweep from it
key_cam(f, (-3.2, -2.0, 0.6), (MOUTH_X, 0.0, OPEN_CZ))
key_cam(f + 167, (-4.0, -2.4, 0.7), (MOUTH_X, 0.0, OPEN_CZ))
key_piston(f, 0.0); key_piston(f + 20, 0.0)
key_piston(f + 130, -STROKE)                   # sweep to flush
shots.append(("S7_reveal_sweep", f, f + 167))
cut_hold(f)
f += 168

# ---- S8  becomes the wall (flush) ----  ~0:37
key_cam(f, (-3.2, -2.0, 0.6), (MOUTH_X, 0.0, OPEN_CZ))
key_cam(f + 71, (-4.0, -2.4, 0.7), (MOUTH_X, 0.0, OPEN_CZ))
key_piston(f, -STROKE); key_piston(f + 71, -STROKE)
shots.append(("S8_flush", f, f + 71))
cut_hold(f)
f += 72

# ---- S9  reopen, ready; pull back to the living wall ----  ~0:40
key_cam(f, (-4.0, -2.4, 0.7), (MOUTH_X, 0.0, OPEN_CZ))
key_cam(f + 119, (-11.5, -0.7, 1.5), (0.0, 0.0, 0.35))   # pull back to the living wall
key_piston(f, -STROKE); key_piston(f + 45, 0.0)   # withdraw -> open
shots.append(("S9_reopen", f, f + 119))
cut_hold(f)
f += 120

END = f
# hero interior luminaire + beacon exist on the base cell; the greybox leaves their
# state animation to Phase 2 (lighting), when the day/night arc is built.


# =============================================================================
# render settings (greybox: Workbench draft, low res, fast)
# =============================================================================
sc.frame_start = 1
sc.frame_end = END
sc.render.fps = FPS
sc.render.resolution_x, sc.render.resolution_y = (960, 540)
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = OUT
os.makedirs(os.path.dirname(OUT), exist_ok=True)

if DRAFT:
    sc.render.engine = "BLENDER_WORKBENCH"
    for m in bpy.data.materials:
        if m.use_nodes and principled(m):
            m.diffuse_color = principled(m).inputs["Base Color"].default_value
    d = sc.display.shading
    d.light = "STUDIO"; d.color_type = "MATERIAL"; d.show_shadows = True; d.show_cavity = True
    sc.display.render_aa = "FXAA"
    sc.render.film_transparent = False
else:
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True

for name, s, e in shots:
    print("SHOT %-18s frames %4d..%-4d (%4.1fs)" % (name, s, e, (e - s) / FPS))
print("narrative greybox: 1..%d  (%.1fs @ %dfps)  step=%d  draft=%s"
      % (END, END / FPS, FPS, STEP, DRAFT))

still = os.environ.get("HC_STILL", "")
if still:
    for fr in [int(x) for x in still.split(",")]:
        sc.frame_set(fr)
        sc.render.filepath = OUT + ("%04d" % fr)
        bpy.ops.render.render(write_still=True)
    print("narrative: stills done")
elif STEP > 1:
    for fr in range(1, END + 1, STEP):
        sc.frame_set(fr)
        sc.render.filepath = OUT + ("%04d" % fr)
        bpy.ops.render.render(write_still=True)
    print("narrative: stepped preview done")
else:
    bpy.ops.render.render(animation=True)
    print("narrative: done")
