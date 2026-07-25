"""HiveCell narrative cinematic -- "One Night" (greybox animatic, Phase 1).

A wordless day-in-the-life piece that REPLACES the old 3-beat safety reel as the
website hero video. TWO CAMERAS ONLY -- the wall is the protagonist, not any one
person:

  S1  THE LIVING WALL (~20s, wide)
      One wide, slowly drifting frame that favours no cell. Life happens in
      parallel: pedestrians pass on the street, sleepers glow amber, someone
      sits on a sill, a resident gets up and leaves and their cell sweeps
      closed for cleaning, while a finished cell reopens ready.

  S2  THE PASS (~22s, close tracking)
      A close lateral dolly glides along the face of the wall -- past open
      bores, closed faces, the person sitting in theirs -- and eases to a stop
      at one cell just as its occupant wakes, leaves, and the piston sweeps
      the cell clean behind them.

One warm end card is burned in at assembly time (render_narrative.sh).

PHASE 1 = GREYBOX: blocking + timing + camera only, rendered in Workbench draft
(near-instant) so we can lock the edit before spending Cycles time on lighting
(Phase 2), the real characters + materials (Phase 3), and the final render
(Phase 4). Everything here is deliberately crude: capsule people, flat lighting.

Run one pass headless on the built hero cell:
  HC_DRAFT=1 flatpak run --filesystem=<repo> org.blender.Blender \
      --background <repo>/blender/hivecell.blend \
      --python <repo>/blender/narrative_cinematic.py

Env:
  HC_DRAFT=1   Workbench (fast greybox)   HC_DRAFT=0  Cycles (later phases)
  HC_STEP=N    render every Nth frame (quick preview of the whole timeline)
  HC_STILL="120,600"  render just those frames as stills (fastest look check)
  HC_SAVE=<path>      build the scene + animation, save it as a .blend and do
                      NOT render -- the baked file is for hand-editing in
                      Blender (from then on that file is the source of truth;
                      re-running this script regenerates from scratch and will
                      not contain manual edits)
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
N_SIDE = 4                          # cells each side of the hero -> 9 total
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


# --- SF5 state palette --------------------------------------------------------
GREEN = (0.16, 0.72, 0.28)          # available
AMBER = (1.0, 0.62, 0.26)           # occupied / sleep-safe night-glow (ADR-0014)
RED = (0.92, 0.14, 0.10)            # moving
ORANGE = (1.0, 0.55, 0.06)          # closed / flush


# Per-cell state for the neighbours. Every hole gets a REAL cell -- a duplicated
# shell + piston -- so the wall reads as live:
#   open     piston retracted, empty bore visible
#   occupied piston retracted, a static sleeper inside
#   closed   piston swept flush -> its face IS the wall
# Cells with story beats stay "open" here and get their occupant/piston animation
# in the timeline below: k=-2 sitter, k=+3 the S1 leaver (closes after), k=+2
# reopens mid-S1, and the hero k=0 holds the S2 guest.
NEIGHBOUR_STATE = {-4: "closed", -3: "occupied", -2: "open", -1: "occupied",
                   1: "open", 2: "closed", 3: "open", 4: "open"}

# The FULL hero cell, so every neighbour is a proper clone of hivecell.blend
# ("Key" in the blend is a studio light, not a cell part). Piston + seals travel
# together on the stroke; magazine/column/luminaire stay put.
CELL_PARTS = ("CapsuleShell", "Piston", "WiperSeals",
              "ChainMagazine", "ChainColumn", "Luminaire")
CELL_MOVERS = ("Piston", "WiperSeals")

neigh_movers = {}                   # k -> [piston clone, seals clone] (keyable)


def duplicate_cell(k, piston_x):
    """Clone the whole hero cell to neighbour column k (offset in Y); set the
    neighbour stroke along X for its state (0 retracted/open, -STROKE swept/closed).
    The hero piston rests at x=0, so neighbour stroke X is keyed in absolute terms.
    Meshes are LINKED duplicates (edit the hero, all cells follow) except the
    Luminaire, whose data is copied so Phase 2 can give each cell its own state
    colour."""
    y = k * PITCH
    for src_name in CELL_PARTS:
        src = bpy.data.objects[src_name]
        o = src.copy()
        if src_name == "Luminaire":
            o.data = src.data.copy()
        sc.collection.objects.link(o)
        o.name = "%s_c%d" % (src_name, k)
        o.location = src.location.copy()
        o.location.y += y
        if src_name in CELL_MOVERS:
            o.location.x += piston_x
            neigh_movers.setdefault(k, []).append(o)


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
# CAST: greybox people (capsule body + head, optional bag) on keyframable roots.
# Postures tip the WHOLE rig as one rigid unit by rotating the ROOT about Y --
# never a single part (rotating just the body while the head kept its standing
# offset was the "head flies above the wall" bug). Root sits at the feet; local
# +Z is "up the body", so a -90 deg Y-rotation lays the figure along -X.
# =============================================================================
def make_person(name, cloth_color=(0.26, 0.34, 0.50), with_bag=False):
    skin = bpy.data.materials.get("ActorSkin") or new_pbr("ActorSkin", (0.80, 0.52, 0.42), 0.6)
    cloth = new_pbr("Cloth_" + name, cloth_color, 0.9)
    root = bpy.data.objects.new(name, None)
    sc.collection.objects.link(root)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=1.0, location=(0, 0, 0.62))
    body = bpy.context.active_object
    body.name = name + "Body"
    body.data.materials.append(cloth)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, 1.27))
    head = bpy.context.active_object
    head.name = name + "Head"
    head.data.materials.append(skin)
    parts = [body, head]
    if with_bag:
        bagm = bpy.data.materials.get("ActorBag") or new_pbr("ActorBag", (0.45, 0.32, 0.20), 0.85)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
        bag = bpy.context.active_object
        bag.name = name + "Bag"
        bag.scale = (0.22, 0.16, 0.26)
        bpy.ops.object.transform_apply(scale=True)
        bag.location = (0.28, 0.0, 0.28)
        bag.data.materials.append(bagm)
        parts.append(bag)
    for o in parts:
        for p in o.data.polygons:
            p.use_smooth = True
        o.parent = root
    return root


def key_obj(o, frame, loc=None, rot=None):
    if loc is not None:
        o.location = loc
        o.keyframe_insert("location", frame=frame)
    if rot is not None:
        o.rotation_euler = rot
        o.keyframe_insert("rotation_euler", frame=frame)


def key_cam(frame, cloc, floc):
    cam.location = cloc
    cam.keyframe_insert("location", frame=frame)
    focus.location = floc
    focus.keyframe_insert("location", frame=frame)


def key_lens(frame, mm):
    # keyframe focal length so the two shots can carry different fields of view;
    # keyed on the adjacent frames of the cut so the change never blends.
    cam.data.lens = mm
    cam.data.keyframe_insert("lens", frame=frame)


def key_piston(frame, x):
    piston.location.x = x
    piston.keyframe_insert("location", index=0, frame=frame)
    seals.location.x = x
    seals.keyframe_insert("location", index=0, frame=frame)


def key_neigh_piston(k, frame, x):
    for o in neigh_movers[k]:
        o.location.x = x
        o.keyframe_insert("location", index=0, frame=frame)


# =============================================================================
# TIMELINE  (24 fps). TWO SHOTS, one hard cut: the shots' end/start camera keys
# sit on ADJACENT frames (S1 ends at 480, S2 starts at 481), so no in-between
# frame is ever rendered -- the cut is inherent.
# =============================================================================
GROUND_STAND = GROUND_Z - 0.12      # root at the feet -> body bottom plants on the ground
SILL_Z = sh[4]                      # mouth sill height
STREET_X = -1.6                     # people walk here, in front of the wall

build_wall_of_cells()

# the cast
guest = make_person("Guest", (0.26, 0.34, 0.50), with_bag=True)   # hero cell k=0; leaves in S2
resident = make_person("Resident", (0.52, 0.30, 0.28))            # cell k=+3; leaves in S1
sitter = make_person("Sitter", (0.30, 0.44, 0.30))                # sits on the sill of k=-2
walker1 = make_person("Walker1", (0.35, 0.35, 0.38))
walker2 = make_person("Walker2", (0.55, 0.50, 0.35))
walker3 = make_person("Walker3", (0.30, 0.30, 0.45))


def stand(rig, frame, x, y):
    key_obj(rig, frame, loc=(x, y, GROUND_STAND), rot=(0, 0, 0))

def sit(rig, frame, y, x=0.15):
    # lounging in the mouth, well reclined and tucked past the sill -- otherwise
    # the figure reads as "standing in the hole" from the wide camera
    key_obj(rig, frame, loc=(x, y, SILL_Z + 0.05), rot=(0, math.radians(-60), 0))

def lie(rig, frame, y, cx=1.0):
    # flat on the bore floor; root offset so the torso centres on cx, head toward -X
    key_obj(rig, frame, loc=(cx + 0.60, y, FLOOR_Z + 0.20), rot=(0, math.radians(-90), 0))


shots = []   # (name, start, end) for the log

# ---- S1  THE LIVING WALL (wide, favours no cell) ----  0:00 .. 0:20
S1_A, S1_B = 1, 480
key_lens(S1_A, 28)
key_cam(S1_A, (-11.3, -1.0, 1.45), (0.3, -0.5, 0.40))
key_cam(S1_B, (-11.0, 0.8, 1.40), (0.3, 0.5, 0.40))

# parallel life -- nothing is "the" subject:
# the guest is already asleep in the hero cell (their story pays off in S2)
lie(guest, S1_A, 0.0)
# someone sits on the sill of k=-2 for the whole film
sit(sitter, S1_A, -2 * PITCH)
# pedestrians cross the street at different depths / directions / speeds; ALL
# of them are fully clear of the wall span (and of the S2 dolly track, which
# starts around y=-8) before the cut at 480
stand(walker1, S1_A, STREET_X - 0.7, -9.0)
stand(walker1, S1_A + 429, STREET_X - 0.7, 11.0)
stand(walker2, S1_A + 59, STREET_X - 1.4, 9.5)
stand(walker2, S1_B, STREET_X - 1.4, -12.0)
stand(walker3, S1_A + 139, STREET_X - 1.0, 9.0)
stand(walker3, S1_B, STREET_X - 1.0, -11.0)
# a resident wakes, leaves cell k=+3 ... and it sweeps closed for cleaning
Y3 = 3 * PITCH
lie(resident, S1_A, Y3)
lie(resident, S1_A + 129, Y3)
sit(resident, S1_A + 184, Y3)
stand(resident, S1_A + 234, -0.5, Y3)
stand(resident, S1_A + 299, STREET_X, Y3 + 0.8)
stand(resident, S1_A + 459, STREET_X - 0.4, Y3 + 6.0)   # off along the street
key_neigh_piston(3, S1_A + 319, 0.0)
key_neigh_piston(3, S1_A + 429, -STROKE)
# ... while next door a finished cell reopens, ready (the wall breathes)
key_neigh_piston(2, S1_A + 339, -STROKE)
key_neigh_piston(2, S1_A + 449, 0.0)
shots.append(("S1_living_wall", S1_A, S1_B))

# ---- S2  THE PASS (close lateral dolly -> stops on the leave + clean) ----  0:20 .. 0:42
S2_A, S2_B = 481, 1000
key_lens(S1_B, 28)                  # hold the wide lens right up to the cut
key_lens(S2_A, 35)
Y0 = -(N_SIDE * PITCH + 2.0)
# glide along the wall, focus leading a couple of metres ahead; ease to a stop
# just off the hero cell for the finale
# camera height ~ opening centre so the tilt stays near level and the rounded
# tops are never cropped by the frame edge
key_cam(S2_A, (-3.0, Y0, 0.45), (0.3, Y0 + 2.2, OPEN_CZ + 0.05))
key_cam(S2_A + 339, (-3.1, -0.8, 0.45), (0.3, 0.3, OPEN_CZ + 0.05))
key_cam(S2_B, (-3.4, -1.0, 0.50), (0.3, 0.0, OPEN_CZ))
# the guest wakes as the camera arrives, leaves past the frame ...
lie(guest, S2_A + 219, 0.0)
sit(guest, S2_A + 279, 0.0)
stand(guest, S2_A + 329, -0.5, 0.0)
stand(guest, S2_A + 369, STREET_X, 0.6)
stand(guest, S2_A + 479, STREET_X - 0.6, 5.0)      # exits the way the camera came from... away
# ... a beat while the cell verifies it is empty, then the sweep, hold on flush
key_piston(S2_A + 394, 0.0)
key_piston(S2_A + 479, -STROKE)
shots.append(("S2_pass_and_clean", S2_A, S2_B))

END = S2_B
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

save = os.environ.get("HC_SAVE", "")
still = os.environ.get("HC_STILL", "")
if save:
    bpy.ops.wm.save_as_mainfile(filepath=save)
    print("narrative: scene baked to %s (no render)" % save)
elif still:
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
