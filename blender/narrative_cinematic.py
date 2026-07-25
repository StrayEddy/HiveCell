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
(Phase 2), material/look polish (Phase 3), and the final render (Phase 4).
The cast is real: Quaternius Universal Base Characters driven by the Universal
Animation Library (both CC0, in assets/quaternius/) -- same 65-bone rig on both
packs, so library clips bind to the characters directly, no retargeting.

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
sc.render.fps = FPS                 # before any glTF import: clip seconds -> frames


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
        # "occupied" cells get their sleeper from the cast section below


# =============================================================================
# CAST: Quaternius Universal Base Characters driven by clips from the Universal
# Animation Library (both CC0, assets/quaternius/). The packs share one 65-bone
# rig, so library actions bind to the characters directly -- no retargeting.
# Each character armature hangs under a keyframable Empty root: the ROOT
# carries world travel + facing (yaw), NLA strips carry the limbs (all clips
# are in-place). Empirical rig facts (probed):
#   character faces LOCAL -Y and is ~1.77 m tall, origin at the feet
#   Death01 ends lying on the back, head ~1.22 m toward local +Y, on z=0
#   Sitting_Idle_Loop: hips at z=0.58 with feet planted at z=0 -- a root on the
#     street puts the hips right at sill height (the sill is bench-high)
# =============================================================================
QUAT = os.path.join(ROOT, "assets", "quaternius")
UAL_GLB = os.path.join(QUAT, "Universal Animation Library[Standard]",
                       "Unreal-Godot", "UAL1_Standard.glb")
CHAR_GLTF = {
    "m": os.path.join(QUAT, "Universal Base Characters[Standard]",
                      "Base Characters", "Godot - UE", "Superhero_Male_FullBody.gltf"),
    "f": os.path.join(QUAT, "Universal Base Characters[Standard]",
                      "Base Characters", "Godot - UE", "Superhero_Female_FullBody.gltf"),
}
# The pack ships BASE bodies (briefs only) with dark/light skin variants; the
# base-color node MULTIPLIES the skin texture by a (white) vertex-colour layer.
# We "dress" the cast through that layer: tint body zones (shirt / pants /
# shoes) per character, which keeps the texture shading -> fitted clothing.
TEXDIR = os.path.join(QUAT, "Universal Base Characters[Standard]",
                      "Base Characters", "Textures")
LIGHT_TEX = {"m": os.path.join(TEXDIR, "T_Superhero_Male_Ligh.png"),   # sic
             "f": os.path.join(TEXDIR, "T_Superhero_Female_Light_BaseColor.png")}
SHOES = (0.16, 0.15, 0.15)
# zone cuts on the rest pose (m). NECK must clear the shoulders/T-pose arms
# (z ~1.45..1.55) or they stay "bare" -- only the head/neck sit above 1.55.
Z_SHOE, Z_WAIST, Z_NECK = 0.14, 1.02, 1.55
if not os.path.exists(UAL_GLB):
    raise RuntimeError("Quaternius cast assets missing -- run blender/fetch_cast.sh")


def load_action_library():
    """Import the UAL mannequin for its actions, then drop its objects."""
    pre = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=UAL_GLB)
    for o in [o for o in bpy.data.objects if o not in pre]:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in bpy.data.actions:
        a.use_fake_user = True      # survive the save even where unused


def make_person(name, sex="m", shirt=(0.5, 0.5, 0.5), pants=(0.3, 0.3, 0.3), skin="dark"):
    """Import a rigged character, dress it, hang it under an Empty root at the feet."""
    pre = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=CHAR_GLTF[sex])
    new = [o for o in bpy.data.objects if o not in pre]
    arm = next(o for o in new if o.type == "ARMATURE")
    arm.animation_data_clear()      # an active action would override the NLA
    arm.name = name + "Rig"
    for o in new:
        if o is not arm:
            o.name = name + "_" + o.name
    body = next(o for o in new if o.type == "MESH" and any(
        s.material and "Superhero" in s.material.name for s in o.material_slots))
    if skin == "light":
        img = bpy.data.images.load(LIGHT_TEX[sex], check_existing=True)
        for n in body.material_slots[0].material.node_tree.nodes:
            if n.type == "TEX_IMAGE" and any(l.to_socket.name == "A"
                                             for o_ in n.outputs for l in o_.links):
                n.image = img
    # dress: tint the multiply vertex-colour layer by height zone
    me = body.data
    vc = me.color_attributes[0]
    for li, loop in enumerate(me.loops):
        z = me.vertices[loop.vertex_index].co.z
        if z < Z_SHOE:
            vc.data[li].color = (*SHOES, 1.0)
        elif z < Z_WAIST:
            vc.data[li].color = (*pants, 1.0)
        elif z < Z_NECK:
            vc.data[li].color = (*shirt, 1.0)   # arms/hands too = long sleeves
    root = bpy.data.objects.new(name, None)
    sc.collection.objects.link(root)
    arm.parent = root
    return {"root": root, "arm": arm}


def play(rig, schedule):
    """Lay clips onto the armature's NLA. schedule = [(action, start, end, mode
    [, blend])]: "loop" repeats the clip to fill start..end, "once" stretches a
    one-shot to fit, "still:F" holds the clip's pose at action-frame F.
    Consecutive strips alternate between two tracks and crossfade over `blend`
    frames (default 8) -- strips extrapolate NOTHING so a dead upper track
    never masks the one below; the last strip HOLDs to the end of the film."""
    arm = rig["arm"]
    ad = arm.animation_data or arm.animation_data_create()
    tracks = [ad.nla_tracks.new(), ad.nla_tracks.new()]
    for i, entry in enumerate(schedule):
        act_name, s, e, mode = entry[:4]
        blend = entry[4] if len(entry) > 4 else 8
        act = bpy.data.actions[act_name]
        s0 = s if i == 0 else s - blend             # overlap = the crossfade
        strip = tracks[i % 2].strips.new("%s_%d" % (act_name, s), int(s0), act)
        if hasattr(strip, "action_slot") and len(act.slots):
            strip.action_slot = act.slots[0]
        length = max(1e-3, act.frame_range[1] - act.frame_range[0])
        if mode == "loop":
            strip.repeat = max(1e-3, (e - s0) / length)
        elif mode == "once":
            strip.scale = max(1e-3, (e - s0) / length)
        elif mode.startswith("still:"):
            fa = float(mode.split(":")[1])
            strip.action_frame_start = fa - 2.5     # ~static tail of the clip
            strip.action_frame_end = fa
            strip.scale = (e - s0) / 2.5
        strip.blend_in = 0 if i == 0 else blend
        strip.blend_out = 0
        strip.extrapolation = "HOLD_FORWARD" if i == len(schedule) - 1 else "NOTHING"
        if i + 1 < len(schedule):
            strip.blend_out = entry_blend(schedule[i + 1])


def entry_blend(entry):
    return entry[4] if len(entry) > 4 else 8


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
SILL_Z = sh[4]                      # mouth sill height
SIT_Z = SILL_Z + 0.03 - 0.58        # root height that rests the sitting hips on the sill
STREET_X = -1.6                     # people walk here, in front of the wall

build_wall_of_cells()
load_action_library()

# the cast (sex/skin vary the body, shirt+pants colours vary the outfit)
guest = make_person("Guest", "m", (0.30, 0.40, 0.58), (0.24, 0.25, 0.30))
resident = make_person("Resident", "f", (0.60, 0.36, 0.28), (0.28, 0.28, 0.32), skin="light")
sitter = make_person("Sitter", "f", (0.36, 0.52, 0.38), (0.26, 0.26, 0.28))
walker1 = make_person("Walker1", "m", (0.45, 0.45, 0.48), (0.22, 0.24, 0.30), skin="light")
walker2 = make_person("Walker2", "f", (0.55, 0.50, 0.38), (0.30, 0.28, 0.26))
walker3 = make_person("Walker3", "m", (0.32, 0.34, 0.44), (0.26, 0.26, 0.26))
sleeper_a = make_person("Sleeper_c-3", "f", (0.46, 0.42, 0.40), (0.34, 0.32, 0.30), skin="light")
sleeper_b = make_person("Sleeper_c-1", "m", (0.40, 0.44, 0.46), (0.30, 0.32, 0.34))


# Roots carry travel + yaw only; the pose comes from the NLA. Yaw convention
# (character faces local -Y): 0 walks -Y, 180 walks +Y, -90 faces -X (out of
# the wall toward the street).
def stand(rig, frame, x, y, yaw):
    key_obj(rig["root"], frame, loc=(x, y, GROUND_Z), rot=(0, 0, math.radians(yaw)))

def sit(rig, frame, y):
    # facing the street, hips landing on the sill, feet reaching the ground
    key_obj(rig["root"], frame, loc=(-0.20, y, SIT_Z), rot=(0, 0, math.radians(-90)))

def lie(rig, frame, y, cx=0.35):
    # Death01's final pose: on the back, head toward local +Y -> yaw -90 lays
    # the head DEEP into the bore (+X), feet toward the mouth. Seen from the
    # street you get feet/legs, not a foreshortened face (head-out read as a
    # collapsed body from the low pass camera), the spread arms hide at the
    # dark end, and lie/sit/stand share yaw -90 so nobody pirouettes on exit.
    # Body spans ~cx-0.4 .. cx+1.8, head at cx+1.22.
    key_obj(rig["root"], frame, loc=(cx, y, FLOOR_Z), rot=(0, 0, math.radians(-90)))


shots = []   # (name, start, end) for the log

# ---- S1  THE LIVING WALL (wide, favours no cell) ----  0:00 .. 0:20
S1_A, S1_B = 1, 480
key_lens(S1_A, 28)
key_cam(S1_A, (-11.3, -1.0, 1.45), (0.3, -0.5, 0.40))
key_cam(S1_B, (-11.0, 0.8, 1.40), (0.3, 0.5, 0.40))

# parallel life -- nothing is "the" subject:
# the guest is already asleep in the hero cell (their story pays off in S2),
# and two neighbours sleep through the whole film
lie(guest, S1_A, 0.0)
lie(sleeper_a, S1_A, -3 * PITCH, cx=0.30)
lie(sleeper_b, S1_A, -1 * PITCH, cx=0.42)
# someone sits on the sill of k=-2 for the whole film
sit(sitter, S1_A, -2 * PITCH)
# pedestrians cross the street at different depths / directions / speeds; ALL
# of them are fully clear of the wall span (and of the S2 dolly track, which
# starts around y=-8) before the cut at 480
stand(walker1, S1_A, STREET_X - 0.7, -9.0, 180)
stand(walker1, S1_A + 429, STREET_X - 0.7, 11.0, 180)
stand(walker2, S1_A + 59, STREET_X - 1.4, 9.5, 0)
stand(walker2, S1_B, STREET_X - 1.4, -12.0, 0)
stand(walker3, S1_A + 139, STREET_X - 1.0, 9.0, 0)
stand(walker3, S1_B, STREET_X - 1.0, -11.0, 0)
# a resident wakes, leaves cell k=+3 ... and it sweeps closed for cleaning
Y3 = 3 * PITCH
lie(resident, S1_A, Y3)
lie(resident, S1_A + 129, Y3)
sit(resident, S1_A + 184, Y3)
stand(resident, S1_A + 234, -0.5, Y3, -90)
stand(resident, S1_A + 299, STREET_X, Y3 + 0.8, -90)
key_obj(resident["root"], S1_A + 324, rot=(0, 0, math.radians(-180)))  # turns up-street
stand(resident, S1_A + 459, STREET_X - 0.4, Y3 + 6.0, -180)  # off along the street
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
stand(guest, S2_A + 329, -0.5, 0.0, -90)
stand(guest, S2_A + 369, STREET_X, 0.6, -90)
key_obj(guest["root"], S2_A + 391, rot=(0, 0, math.radians(-180)))     # turns up-street
stand(guest, S2_A + 479, STREET_X - 0.6, 5.0, -180)  # exits the way the camera came... away
# ... a beat while the cell verifies it is empty, then the sweep, hold on flush
key_piston(S2_A + 394, 0.0)
key_piston(S2_A + 479, -STROKE)
shots.append(("S2_pass_and_clean", S2_A, S2_B))
END = S2_B


# ---- NLA clip schedules (poses; the roots above carry travel/facing) --------
# Sleep = the static tail of Death01 (the free UAL tier has no sleep loop; at
# these camera distances a held lying pose with the crossfades reads as sleep).
# NB: the lying->sitting crossfade must ride WITH the root's slide out of the
# bore (guest 700..760, resident 130..185) -- an earlier blend makes the body
# sit up inside the bore while the root still lies down (the "sprawl" bug).
play(guest, [
    ("Death01", 1, 750, "still:57"),
    ("Sitting_Idle_Loop", 750, 785, "loop", 45),   # crossfade 705..750 = the swing-out
    ("Sitting_Exit", 785, 812, "once"),
    ("Walk_Loop", 812, 962, "loop"),
    ("Idle_Loop", 962, END, "loop"),
])
play(resident, [
    ("Death01", 1, 180, "still:57"),
    ("Sitting_Idle_Loop", 180, 210, "loop", 45),   # crossfade 135..180 = the swing-out
    ("Sitting_Exit", 210, 237, "once"),
    ("Walk_Loop", 237, 462, "loop"),
    ("Idle_Loop", 462, END, "loop"),
])
play(sitter, [("Sitting_Idle_Loop", 1, END, "loop")])
play(walker1, [("Walk_Loop", 1, END, "loop")])
play(walker2, [("Walk_Formal_Loop", 1, END, "loop")])
play(walker3, [("Walk_Loop", 1, END, "loop")])
play(sleeper_a, [("Death01", 1, END, "still:57")])
play(sleeper_b, [("Death01", 1, END, "still:57")])
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
    # TEXTURE: characters show their PBR textures; untextured walls fall back
    # to the material colour copied above
    d.light = "STUDIO"; d.color_type = "TEXTURE"; d.show_shadows = True; d.show_cavity = True
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
