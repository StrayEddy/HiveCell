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
# HC_REAL=1 dresses the street with the licensed KitBash3D city assets
# (assets/envato/, Envato Elements) and renders lit in EEVEE with the night
# world -- the Phase 2/3 look. Unset = the fast Workbench greybox (Phase 1).
REAL = os.environ.get("HC_REAL", "0") == "1"
ENV = os.path.join(ROOT, "assets", "envato")
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

def emit(mat, color, strength):
    """Make a material glow in Cycles (windows, lamp heads). Workbench ignores
    emission and shades the diffuse_color copied in the render-settings block, so
    this only takes effect in the Phase 2 Cycles night pass."""
    b = principled(mat)
    b.inputs["Emission Color"].default_value = (*color, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return mat

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
# CITY CONTEXT: the wall is one facade on a night street, not an object in a
# void. We greybox the street it stands on (sidewalk -> curb -> road, running
# along Y past both cameras) and the city around it (a set-back skyline of lit
# blocks behind and beside the hive), then push the look to NIGHT. Geometry
# only here: real light is Phase 2 -- the night HDRI world + emissive windows /
# lamp heads drive Cycles. In the Workbench greybox the night read is carried by
# a dark sky, dark road/building masses, and the warm pools of the streetlamps,
# lit windows and (later) the cell glow.
#
# Everything shares ONE walking plane at GROUND_Z (feet are keyed there), so the
# sidewalk sits a hair proud of the road and the curb is a raised lip -- no slab
# is low enough to drop a foot through. City blocks are set back past x=3.2 so
# they clear the cell bores (the shells reach x=2.5).
# =============================================================================
import random as _rnd

CITY_Y = 17.0                       # street runs this far each way in Y
ROAD_X0, ROAD_X1 = -17.0, 9.5       # road spans under S1's camera and past the wall
CURB_X = -3.4                       # sidewalk (wall side) -> curb -> road (street side)


# =============================================================================
# REAL DRESSING: link the licensed KitBash3D assets (assets/envato/) as collection
# instances. KitBash ships each item at real-world metric scale, Z-up, base at
# z=0 -- the same units as the hero cell -- so placement is (x, y) on the street
# plus a Z-rotation for facing, dropping the base to GROUND_Z. Storefronts face
# their facade toward local -Y, so -90 deg swings it (and its built-in sidewalk)
# to face our street, which opens toward -X. Instances are cheap: the same linked
# collection can be dropped many times.
# =============================================================================
_kb_lib = {}                        # blend path -> local collection of linked objects
NIGHT_LIGHTS = []                   # city practicals (lamps, neon): off by day, on at night

def link_kb(item, blendfile, label, xy, rot_z=-90.0, scale=1.0, ztop=None):
    # KitBash blends keep their geometry directly in the scene root (the named
    # 'Collection' datablock is empty), so we LINK the objects and gather them
    # into a local collection we can instance -- link once per blend, instance
    # many. Cameras are dropped; meshes + the shopfront's own lights come along.
    path = os.path.join(ENV, item, blendfile)
    if path not in _kb_lib:
        with bpy.data.libraries.load(path, link=True) as (src, dst):
            dst.objects = list(src.objects)
        col = bpy.data.collections.new("KBsrc_" + os.path.splitext(blendfile.replace("/", "_"))[0])
        for o in dst.objects:
            # keep meshes only; drop each kit's own promo cameras AND lights (their
            # suns/area lights flood our night and swamp the mood lighting)
            if o is not None and o.type not in ("CAMERA", "LIGHT"):
                col.objects.link(o)                     # not linked into the scene: instance-only
        _kb_lib[path] = col
    e = bpy.data.objects.new("KB_" + label, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = _kb_lib[path]
    e.location = (xy[0], xy[1], GROUND_Z if ztop is None else ztop)
    e.rotation_euler = (0, 0, math.radians(rot_z))
    e.scale = (scale, scale, scale)
    sc.collection.objects.link(e)
    return e


GREENS = [(0.10, 0.26, 0.09), (0.14, 0.31, 0.11), (0.08, 0.22, 0.10)]

def blocky_tree(x, y, seed, h=None):
    """A stylised low-poly street tree (tapered trunk + a few faceted foliage
    blobs), matte and flat-shaded to match the blocky cast."""
    r = _rnd.Random(seed)
    if h is None:
        h = 2.8 + r.random() * 1.2
    bark = new_pbr("Bark%d" % seed, (0.17, 0.11, 0.07), rough=1.0)
    box("Tree%d_trunk" % seed, (0.16, 0.16, h * 0.6), (x, y, GROUND_Z + h * 0.3), bark)
    for i in range(3):
        rad = (0.78 + 0.24 * r.random()) * (h * 0.34)
        loc = (x + (r.random() - 0.5) * 0.4, y + (r.random() - 0.5) * 0.4,
               GROUND_Z + h * 0.62 + i * (h * 0.13))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rad, location=loc)
        o = bpy.context.active_object
        o.name = "Tree%d_leaf%d" % (seed, i)
        for p in o.data.polygons:
            p.use_smooth = False                          # facet it -> blocky foliage
        o.data.materials.append(new_pbr("Leaf%d_%d" % (seed, i), GREENS[i % 3], rough=1.0))


def blocky_bush(x, y, seed):
    """A low faceted shrub -- a small cluster of green blobs near the ground."""
    r = _rnd.Random(seed)
    for i in range(3):
        rad = 0.32 + 0.18 * r.random()
        loc = (x + (r.random() - 0.5) * 0.6, y + (r.random() - 0.5) * 0.6,
               GROUND_Z + 0.28 + r.random() * 0.16)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=rad, location=loc)
        o = bpy.context.active_object
        o.name = "Bush%d_%d" % (seed, i)
        for p in o.data.polygons:
            p.use_smooth = False
        o.data.materials.append(new_pbr("BushLeaf%d_%d" % (seed, i), GREENS[i % 3], rough=1.0))


def dress_city_real():
    # concrete pavement in front of the hive: KitBash sidewalk tiles (4x5x0.2),
    # laid along Y from wall to curb, tops a hair above the asphalt
    tiles = ["KB3D_CTS_Sidewalk_A.blend", "KB3D_CTS_Sidewalk_B.blend", "KB3D_CTS_Sidewalk_C.blend"]
    for i, yy in enumerate(range(-8, 12, 5)):
        link_kb("kitbash-city-streets-sidewalk-%s" % "abc"[i % 3], tiles[i % 3],
                "Walk%d" % yy, (-1.4, yy), rot_z=0, ztop=GROUND_Z - 0.18)

    # street-level neighbours flanking the hive, pushed out to the Y-ends so they
    # frame the shot rather than loom behind the hero (facades face -X)
    link_kb("kitbash-storefronts-st-noelle-bistro", "KB3D_SFR_HighEndStore_C.blend",
            "Bistro", (0.4, 15.5))
    link_kb("kitbash-storefronts-book-store", "KB3D_SFR_MidEndStore_F.blend",
            "BookStore", (0.4, -15.5))
    link_kb("kitbash-storefronts-minimart-groceries", "KB3D_SFR_MidEndStore_I.blend",
            "Minimart", (0.4, -28.0))
    link_kb("kitbash-city-streets-city-sidewalk-b", "KB3D_CTS_BldgMD_K.blend",
            "BldgMD", (0.4, 27.0))

    # the skyline: set back on +X, centred behind the hive so the wide S1 lens
    # catches the lit towers rising above the low wall
    link_kb("kitbash-manhattan-skyscraper-c", "KB3D_MIM_Skyscraper_C.blend",
            "Skyscraper", (40.0, -7.0))
    link_kb("kitbash-manhattan-upscale-hotel", "KB3D_MIM_UpscaleHotel_A.blend",
            "Hotel", (42.0, 15.0))

    # streetlamps along the curb (arm reaching over the road toward -X), each
    # with a real warm light at the head so the model actually pools light on the
    # street -- spread off-centre so no pole bisects the hero framing
    for yy in (-12.0, -4.0, 4.0, 12.0):
        link_kb("kitbash-city-streets-lamp-f", "KB3D_CTS_Lamp_F.blend",
                "Lamp%d" % int(yy), (CURB_X - 0.2, yy), rot_z=90)
        li = bpy.data.lights.new("LampL%d" % int(yy), "POINT")
        li.energy = 650.0
        li.color = (1.0, 0.72, 0.42)        # warm sodium
        li.shadow_soft_size = 0.5
        lo = bpy.data.objects.new("LampL%d" % int(yy), li)
        sc.collection.objects.link(lo)
        lo.location = (CURB_X - 1.0, yy, GROUND_Z + 4.6)
        NIGHT_LIGHTS.append(li)                          # off by day, on at night

    # a parked car at the curb + a little street furniture near the hero
    link_kb("kitbash-city-cars-sedan", os.path.join("asset", "KB3D_Sedan.blend"),
            "Sedan", (-2.6, -9.5), rot_z=0)
    link_kb("kitbash-city-streets-fire-hydrant-a", "KB3D_CTS_FireHydrant_A.blend",
            "Hydrant", (-3.0, 3.5), rot_z=0)
    link_kb("kitbash-city-streets-newspaper-stand-a", "KB3D_CTS_NewspaperStand_A.blend",
            "News", (-3.0, -1.5), rot_z=0)
    link_kb("kitbash-city-streets-traffic-lights-b", "KB3D_CTS_TrafficLights_B.blend",
            "Signal", (-3.6, 22.0), rot_z=0)     # far +Y, clear of the S2 opening

    # low-poly street trees -- green warms the cold palette and matches the blocky
    # cast. Curb trees (screen-left framer + down-street), one BIG tree rising
    # behind the wall on the right, and a small bush in the front-right foreground.
    for i, ty in enumerate((4.6, -9.5, 10.0, 16.0)):     # -Y = screen-right
        blocky_tree(-3.4, ty, 700 + i)
    blocky_tree(4.6, -4.6, 720, h=6.4)                   # behind the wall, screen-right
    blocky_bush(-4.4, -4.6, 730)                         # front-right foreground

    # saturated neon accents washing the storefronts at the Y-ends: colour pops in
    # the wings that never reach the warm hero cells, so the wall keeps focus
    for name, yy, col in [("NeonPink", 11.0, (1.0, 0.08, 0.42)),
                          ("NeonCyan", -11.0, (0.10, 0.55, 1.0)),
                          ("NeonAmber", 20.0, (1.0, 0.40, 0.08))]:
        li = bpy.data.lights.new(name, "POINT")
        li.energy, li.color, li.shadow_soft_size = 1800.0, col, 2.0
        lo = bpy.data.objects.new(name, li)
        sc.collection.objects.link(lo)
        lo.location = (-1.2, yy, GROUND_Z + 2.4)
        NIGHT_LIGHTS.append(li)                          # neon: off by day, on at night


def _sky_bg(nt, horizon, mid, zenith, strength):
    """A graded-sky Background node (ColorRamp on the view ray's up-component)."""
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Incoming"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (*horizon, 1.0)
    e[1].position = 1.0; e[1].color = (*zenith, 1.0)
    m = ramp.color_ramp.elements.new(0.4); m.color = (*mid, 1.0)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    return bg


def setup_daynight():
    """A DAY->NIGHT arc: S1 plays in daytime, S2 at night. Everything that defines
    the time of day (sky, sun, exposure, city practicals) is keyframed to hold DAY
    across S1 and NIGHT across S2, switching on the adjacent frames of the cut
    (S1_B/S2_A) so -- like the camera -- no in-between frame ever blends."""
    w = sc.world or bpy.data.worlds.new("DayNight")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    day = _sky_bg(nt, (0.52, 0.60, 0.72), (0.28, 0.45, 0.70), (0.10, 0.30, 0.62), 1.5)
    night = _sky_bg(nt, (0.13, 0.08, 0.045), (0.03, 0.05, 0.11), (0.010, 0.030, 0.12), 1.8)
    nf = nt.nodes.new("ShaderNodeValue")
    nf.name = nf.label = "NightFactor"
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(nf.outputs[0], mix.inputs["Fac"])
    nt.links.new(day.outputs["Background"], mix.inputs[1])
    nt.links.new(night.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    for fr, v in [(1, 0.0), (S1_B, 0.0), (S2_A, 1.0), (END, 1.0)]:
        nf.outputs[0].default_value = v
        nf.outputs[0].keyframe_insert("default_value", frame=fr)
    # S3 dissolves the whole environment to a black void -> fade the night sky out
    _nv = night.inputs["Strength"].default_value
    for fr, v in [(S2_A, _nv), (S2_B, _nv), (S3_A, 0.0), (END, 0.0)]:
        night.inputs["Strength"].default_value = v
        night.inputs["Strength"].keyframe_insert("default_value", frame=fr)

    key = bpy.data.objects.get("Key")     # kill the product-shot studio flood light
    if key and key.type == "LIGHT":
        key.hide_render = key.hide_viewport = True

    sun = bpy.data.objects.get("Sun")
    if sun and sun.type == "LIGHT":
        # day: a bright warm sun from high; night: a dim cool moon grazing from -X
        day_s = (3.4, (1.0, 0.95, 0.84), (math.radians(-55), math.radians(12), math.radians(35)))
        night_s = (float(os.environ.get("HC_MOON", "1.8")), (0.58, 0.62, 0.82),
                   (math.radians(-18), math.radians(58), math.radians(12)))
        def key_sun(st, fr):
            sun.data.energy, sun.data.color, sun.rotation_euler = st[0], st[1], st[2]
            sun.data.keyframe_insert("energy", frame=fr)
            sun.data.keyframe_insert("color", frame=fr)
            sun.keyframe_insert("rotation_euler", frame=fr)
        key_sun(day_s, 1); key_sun(day_s, S1_B)
        key_sun(night_s, S2_A); key_sun(night_s, END)

    # streetlamps + neon: dark by day, full at night
    for li in NIGHT_LIGHTS:
        full = li.energy
        for fr, v in [(1, 0.0), (S1_B, 0.0), (S2_A, full), (END, full)]:
            li.energy = v
            li.keyframe_insert("energy", frame=fr)

    # exposure: bright by day, down for night; then dip through BLACK across the
    # S2->S3 cut and rise back to reveal the isolated cell -> the dissolve
    _exp = float(os.environ.get("HC_EXP", "-1.0"))
    _exp3 = float(os.environ.get("HC_EXP3", "0.5"))    # brighter reveal for the isolated cell
    for fr, v in [(1, -0.5), (S1_B, -0.5), (S2_A, _exp), (S2_B, _exp),
                  (S3_A, -6.0), (S3_A + T3(18), _exp3), (END, _exp3)]:
        sc.view_settings.exposure = v
        try:
            sc.view_settings.keyframe_insert("exposure", frame=fr)
        except (TypeError, RuntimeError):
            pass


def build_city():
    old = bpy.data.objects.get("Ground")
    if old:
        old.hide_render = old.hide_viewport = True      # we own the ground now

    asphalt = new_pbr("Asphalt", (0.045, 0.045, 0.055), rough=0.95)
    concrete = new_pbr("SidewalkMat", (0.26, 0.27, 0.28), rough=0.9)
    curbmat = new_pbr("CurbMat", (0.38, 0.39, 0.41), rough=0.9)
    facade = new_pbr("CityBlock", (0.05, 0.055, 0.075), rough=0.85)     # dark night mass
    pole_m = new_pbr("LampPole", (0.05, 0.05, 0.06), rough=0.5, metal=0.8)
    win_m = emit(new_pbr("WindowLit", (1.0, 0.86, 0.55), rough=0.5), (1.0, 0.86, 0.55), 3.0)
    head_m = emit(new_pbr("LampHead", (1.0, 0.75, 0.42), rough=0.4), (1.0, 0.72, 0.40), 12.0)
    line_m = new_pbr("RoadLine", (0.55, 0.50, 0.22), rough=0.9)

    # --- the street surface (road low, sidewalk 2 cm proud, curb a raised lip) -
    box("Road", (ROAD_X1 - ROAD_X0, 2 * CITY_Y, 0.30),
        ((ROAD_X0 + ROAD_X1) / 2, 0.0, GROUND_Z - 0.15), asphalt)

    if REAL:
        dress_city_real()       # licensed KitBash city over the procedural asphalt
        return

    box("Sidewalk", (0.35 - CURB_X, 2 * CITY_Y, 0.28),
        ((0.35 + CURB_X) / 2, 0.0, GROUND_Z - 0.12), concrete)      # top = GROUND_Z + 0.02
    box("Curb", (0.12, 2 * CITY_Y, 0.16), (CURB_X, 0.0, GROUND_Z + 0.08), curbmat)
    for yy in range(int(-CITY_Y) + 1, int(CITY_Y), 3):              # dashed centre line
        box("Lane_%d" % yy, (0.12, 1.1, 0.02), (-10.0, yy + 0.5, GROUND_Z + 0.01), line_m)

    # --- city blocks: a set-back skyline of lit facades behind and beside the
    #     hive. Lower windows hide behind the wall; the tops rise above it, so
    #     the hive reads as one low facade on a taller city block. -------------
    def building(name, cx, cy, w, d, h, seed):
        box(name, (d, w, h), (cx, cy, GROUND_Z + h / 2), facade)
        r = _rnd.Random(seed)
        cols, rows = max(2, int(w // 1.4)), max(2, int((h - 1.2) // 1.6))
        x_face = cx - d / 2 - 0.02                                  # street-facing (-X) wall
        for c in range(cols):
            for ro in range(rows):
                if r.random() < 0.35:                              # a third of windows dark
                    continue
                wy = cy - w / 2 + (c + 0.5) * (w / cols)
                wz = GROUND_Z + 1.0 + (ro + 0.5) * ((h - 1.4) / rows)
                box("%s_win_%d_%d" % (name, c, ro), (0.05, 0.55, 0.7),
                    (x_face, wy, wz), win_m)

    #          name        cx    cy    w   d   h  seed   (face = cx - d/2 >= 3.2)
    for spec in [("BlockA", 5.5, -8.0, 6, 4, 7, 11), ("BlockB", 7.5, -3.0, 5, 5, 10, 22),
                 ("BlockC", 6.0, 2.5, 5, 4, 6, 33), ("BlockD", 8.5, 7.0, 6, 5, 11, 44),
                 ("BlockE", 5.2, 11.5, 6, 3.6, 7, 55), ("BlockF", 9.5, -11.5, 6, 5, 9, 66)]:
        building(*spec)

    # --- streetlamps along the curb, arms reaching over the road (behind the S2
    #     camera, foreground pools of warm light in S1) ------------------------
    for yy in (-9.5, -4.0, 4.0, 9.5):
        n = "Lamp_%d" % int(yy * 10)
        px = CURB_X - 0.2
        box(n + "_pole", (0.08, 0.08, 2.4), (px, yy, GROUND_Z + 1.2), pole_m)
        box(n + "_arm", (0.9, 0.06, 0.06), (px - 0.45, yy, GROUND_Z + 2.35), pole_m)
        box(n + "_head", (0.30, 0.16, 0.10), (px - 0.85, yy, GROUND_Z + 2.30), head_m)
        li = bpy.data.lights.new(n + "_L", "POINT")               # dark for Cycles Phase 2
        li.energy, li.color, li.shadow_soft_size = 320.0, (1.0, 0.72, 0.40), 0.35
        lo = bpy.data.objects.new(n + "_L", li)
        sc.collection.objects.link(lo)
        lo.location = (px - 0.85, yy, GROUND_Z + 2.25)


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
# Second clip library: Mixamo animations retargeted onto this same Quaternius rig
# (blender/retarget_mixamo.py bakes ~/Downloads/*.fbx -> Actions here). CC0-clean:
# the CC0 body plays the motion; only the motion data carries Mixamo terms. New
# clip names (Sleep_Idle, Sit_Floor_KneeUp, Crawl_Fwd_Loop, ...) slot into play().
MIX_LIB = os.path.join(QUAT, "UAL2_Mixamo.blend")
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
    """Import the UAL mannequin for its actions, then drop its objects; then append
    the retargeted Mixamo clips from the second library. Both sets bind to the
    Quaternius rig by bone name -- no retargeting at play() time."""
    pre = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=UAL_GLB)
    for o in [o for o in bpy.data.objects if o not in pre]:
        bpy.data.objects.remove(o, do_unlink=True)
    if os.path.exists(MIX_LIB):                 # retargeted Mixamo Actions (append by name)
        with bpy.data.libraries.load(MIX_LIB, link=False) as (src, dst):
            dst.actions = list(src.actions)
    for a in bpy.data.actions:
        a.use_fake_user = True      # survive the save even where unused


# blocky-cast look (the semi-real base bodies are ugly; we stylise them into
# clean flat-shaded low-poly forms -- animations untouched). Skin is painted flat
# per person; the uncanny eyes + helper sphere are dropped.
SKIN_RGB = {"dark": (0.34, 0.23, 0.17), "mid": (0.60, 0.43, 0.33), "light": (0.82, 0.63, 0.53),
            "grey": (0.42, 0.42, 0.45)}   # anonymous passers-by
HAIR_RGB = (0.05, 0.04, 0.035)
BLOCK_RATIO = float(os.environ.get("HC_BLOCK", "0.12"))    # decimate ratio (lower = blockier)

def flat_mat(name, color):
    m = new_pbr(name, color, rough=1.0)                    # matte, no spec highlight
    b = principled(m)
    for s in ("Specular IOR Level", "Specular"):
        if s in b.inputs:
            b.inputs[s].default_value = 0.0
    return m

def flat_vc_mat(name, layer):
    m = flat_mat(name, (0.6, 0.6, 0.6))
    nt = m.node_tree
    vcn = nt.nodes.new("ShaderNodeVertexColor")
    vcn.layer_name = layer
    nt.links.new(vcn.outputs["Color"], principled(m).inputs["Base Color"])
    return m

def _blockify(o, ratio):
    for p in o.data.polygons:
        p.use_smooth = False                              # facet it -> low-poly read
    dec = o.modifiers.new("Blocky", "DECIMATE")
    dec.ratio = ratio
    try:                                                  # decimate the rest pose,
        with bpy.context.temp_override(object=o):         # BEFORE the armature deform,
            bpy.ops.object.modifier_move_to_index(modifier=dec.name, index=0)
    except Exception:                                     # so topology stays stable
        pass                                              # (no per-frame flicker)


def make_person(name, sex="m", shirt=(0.5, 0.5, 0.5), pants=(0.3, 0.3, 0.3), skin="dark"):
    """Import a rigged character, dress it in flat matte colour and stylise it into
    a clean blocky low-poly form; hang it under an Empty root at the feet."""
    pre = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=CHAR_GLTF[sex])
    new = [o for o in bpy.data.objects if o not in pre]
    arm = next(o for o in new if o.type == "ARMATURE")
    arm.animation_data_clear()      # an active action would override the NLA
    arm.name = name + "Rig"
    for o in new:
        if o is not arm:
            o.name = name + "_" + o.name
    skin_rgb = SKIN_RGB.get(skin, SKIN_RGB["mid"])

    for o in [o for o in new if o.type == "MESH"]:
        joined = " ".join(s.material.name if s.material else "" for s in o.material_slots).lower()
        if "superhero" in joined:
            # BODY: paint flat colour zones (skin on the head) into the vcol layer.
            # The zone cuts (Z_SHOE/Z_WAIST/Z_NECK) are metres up from the feet, so
            # we partition on WORLD Z, not the mesh's local vert Z. Quaternius imports
            # at world scale 1 (world Z == local Z, unchanged), but a Mixamo-skeleton
            # character arrives with the metre scale on the parent armature (0.01) and
            # the mesh's own local space offset -- there local Z is neither metres nor
            # 0..height, so reading it directly would paint the whole body one zone.
            me = o.data
            vc = me.color_attributes[0]
            mw = o.matrix_world
            for li, loop in enumerate(me.loops):
                z = (mw @ me.vertices[loop.vertex_index].co).z
                if z < Z_SHOE:
                    vc.data[li].color = (*SHOES, 1.0)
                elif z < Z_WAIST:
                    vc.data[li].color = (*pants, 1.0)
                elif z < Z_NECK:
                    vc.data[li].color = (*shirt, 1.0)      # arms/hands too = long sleeves
                else:
                    vc.data[li].color = (*skin_rgb, 1.0)   # head + neck = skin
            o.data.materials.clear()
            o.data.materials.append(flat_vc_mat(name + "_skin", vc.name))
            _blockify(o, BLOCK_RATIO)
        elif "hair" in joined:
            o.data.materials.clear()
            o.data.materials.append(flat_mat(name + "_hair", HAIR_RGB))
            _blockify(o, 0.5)
        else:
            bpy.data.objects.remove(o, do_unlink=True)     # drop eyes + helper sphere

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
build_city()
load_action_library()

# the cast (sex/skin vary the body, shirt+pants colours vary the outfit)
# cell users all wear ONE vivid uniform colour so they read as the cast; the
# passers-by wear ONE muted uniform colour that recedes into the city
CAST_SHIRT, CAST_PANTS = (0.92, 0.44, 0.10), (0.34, 0.18, 0.07)     # uniform warm cast
CROWD_SHIRT, CROWD_PANTS = (0.40, 0.41, 0.43), (0.32, 0.33, 0.35)   # uniform muted crowd
guest = make_person("Guest", "m", CAST_SHIRT, CAST_PANTS)
resident = make_person("Resident", "f", CAST_SHIRT, CAST_PANTS, skin="light")
sitter = make_person("Sitter", "f", CAST_SHIRT, CAST_PANTS)
# passers-by are ANONYMOUS: fully grey (clothes + skin) so the coloured cell
# users read as the cast and the grey crowd flows past as city texture
walker1 = make_person("Walker1", "m", CROWD_SHIRT, CROWD_PANTS, skin="grey")
walker2 = make_person("Walker2", "f", CROWD_SHIRT, CROWD_PANTS, skin="grey")
walker3 = make_person("Walker3", "m", CROWD_SHIRT, CROWD_PANTS, skin="grey")
walker4 = make_person("Walker4", "f", CROWD_SHIRT, CROWD_PANTS, skin="grey")
walker5 = make_person("Walker5", "m", CROWD_SHIRT, CROWD_PANTS, skin="grey")
walker6 = make_person("Walker6", "f", CROWD_SHIRT, CROWD_PANTS, skin="grey")
sleeper_a = make_person("Sleeper_c-3", "f", CAST_SHIRT, CAST_PANTS, skin="light")
sleeper_b = make_person("Sleeper_c-1", "m", CAST_SHIRT, CAST_PANTS)


# Roots carry travel + yaw only; the pose comes from the NLA. Yaw convention
# (character faces local -Y): 0 walks -Y, 180 walks +Y, -90 faces -X (out of
# the wall toward the street).
def stand(rig, frame, x, y, yaw):
    key_obj(rig["root"], frame, loc=(x, y, GROUND_Z), rot=(0, 0, math.radians(yaw)))

def sit(rig, frame, y):
    # facing the street, hips landing on the sill, feet reaching the ground
    key_obj(rig["root"], frame, loc=(-0.20, y, SIT_Z), rot=(0, 0, math.radians(-90)))

# The retargeted Mixamo Sit_Sill_Loop rests its hips at 0.51 above the feet-origin
# (vs the UAL clip's 0.58), so it needs its own root height to land on the sill.
SIT_Z_MIX = SILL_Z + 0.03 - 0.51
def sit_mix(rig, frame, y):
    key_obj(rig["root"], frame, loc=(-0.20, y, SIT_Z_MIX), rot=(0, 0, math.radians(-90)))

def lie(rig, frame, y, cx=0.35):
    # Death01's final pose: on the back, head toward local +Y -> yaw -90 lays
    # the head DEEP into the bore (+X), feet toward the mouth. Seen from the
    # street you get feet/legs, not a foreshortened face (head-out read as a
    # collapsed body from the low pass camera), the spread arms hide at the
    # dark end, and lie/sit/stand share yaw -90 so nobody pirouettes on exit.
    # Body spans ~cx-0.4 .. cx+1.8, head at cx+1.22.
    key_obj(rig["root"], frame, loc=(cx, y, FLOOR_Z), rot=(0, 0, math.radians(-90)))


def lie_sleep(rig, frame, y, cx=0.70):
    # Static sleepers use the retargeted Mixamo Lay_Idle (a flat, relaxed supine
    # rest) instead of the Death01 sprawl. Measured layout matches Death01's: head
    # toward local +Y, feet toward -Y, body flat (lowest ~z=0.05) -> yaw -90 lays
    # the head DEEP into the bore (+X), feet toward the mouth, same as lie(). It's
    # more compact than Death01 (head ~cx+0.71, not +1.22), so cx sits a touch
    # deeper to keep the feet at the mouth plane rather than poking into the street.
    key_obj(rig["root"], frame, loc=(cx, y, FLOOR_Z), rot=(0, 0, math.radians(-90)))


shots = []   # (name, start, end) for the log

# ---- S1  THE LIVING WALL (wide, favours no cell) ----  0:00 .. 0:20
S1_A = 1
# THREE shots. S1 = daytime establisher (short). S2 = night: the guest wakes,
# packs up, leaves, and the cell closes. S3 = the X-RAY CLEAN -- the environment
# dissolves to a void, a side-on view isolates the one cell, its near wall turns
# transparent, and the piston travels the bore cleaning it. The night (S2+S3)
# outweighs the day. Each shot scales its own hand-tuned offsets independently.
S1_SEC = float(os.environ.get("HC_S1", "10"))
S2_SEC = float(os.environ.get("HC_S2", "13"))
S3_SEC = float(os.environ.get("HC_S3", "7"))
S1_B = int(round(S1_SEC * FPS))
S2_A = S1_B + 1
S2_B = S2_A + int(round(S2_SEC * FPS)) - 1
S3_A = S2_B + 1
S3_B = S3_A + int(round(S3_SEC * FPS)) - 1
END = S3_B
_S2_SPAN, _S3_SPAN = 520, 200
def T1(f):                                        # scale S1 offsets (authored on 0..480)
    return max(1, int(round(f * S1_B / 480.0)))
def T2(f):                                        # scale S2 offsets (authored on 0.._S2_SPAN)
    return max(1, int(round(f * (S2_B - S2_A) / _S2_SPAN)))
def T3(f):                                        # scale S3 offsets (authored on 0.._S3_SPAN)
    return max(1, int(round(f * (S3_B - S3_A) / _S3_SPAN)))

# hero-cell X-RAY: give the hero shell its OWN see-through material (neighbours
# share the mesh, so an object-linked slot keeps them opaque); faded clear in S3
XRAY_A = float(os.environ.get("HC_XRAY", "0.10"))
_shell = bpy.data.objects["CapsuleShell"]
if _shell.data.materials and _shell.data.materials[0]:
    _xray_mat = _shell.data.materials[0].copy()
    _xray_mat.name = "HeroShell_xray"
    _shell.material_slots[0].link = "OBJECT"
    _shell.material_slots[0].material = _xray_mat
    def key_xray(frame, a):
        b = principled(_xray_mat)
        if b:
            b.inputs["Alpha"].default_value = a
            b.inputs["Alpha"].keyframe_insert("default_value", frame=frame)
else:
    def key_xray(frame, a):
        pass

# hero PISTON pop: an object-linked material we make glow cyan in S3 so the
# cleaning stroke reads as a bright scanner sweeping the transparent cell
_piston_o = bpy.data.objects["Piston"]
if _piston_o.data.materials and _piston_o.data.materials[0]:
    _pmat = _piston_o.data.materials[0].copy()
    _pmat.name = "HeroPiston_pop"
    _piston_o.material_slots[0].link = "OBJECT"
    _piston_o.material_slots[0].material = _pmat
    _pb = principled(_pmat)
    if _pb:
        _pb.inputs["Emission Color"].default_value = (0.15, 0.75, 1.0, 1.0)   # cool clean glow
    def key_piston_glow(frame, s):
        b = principled(_pmat)
        if b:
            b.inputs["Emission Strength"].default_value = s
            b.inputs["Emission Strength"].keyframe_insert("default_value", frame=frame)
else:
    def key_piston_glow(frame, s):
        pass
key_lens(S1_A, 28)
key_cam(S1_A, (-11.3, -1.0, 1.45), (0.3, -0.5, 0.40))
key_cam(S1_B, (-11.0, 0.8, 1.40), (0.3, 0.5, 0.40))

# parallel life -- nothing is "the" subject:
# the guest is already asleep in the hero cell (their story pays off in S2),
# and two neighbours sleep through the whole film
lie_sleep(guest, S1_A, 0.0)
lie_sleep(sleeper_a, S1_A, -3 * PITCH)
lie_sleep(sleeper_b, S1_A, -1 * PITCH)
# someone sits on the sill of k=-2 for the whole film
sit(sitter, S1_A, -2 * PITCH)
# pedestrians cross the street at different depths / directions / speeds; ALL
# of them are fully clear of the wall span (and of the S2 dolly track, which
# starts around y=-8) before the cut at 480
stand(walker1, S1_A, STREET_X - 0.7, -9.0, 180)
stand(walker1, S1_A + T1(429), STREET_X - 0.7, 11.0, 180)
stand(walker2, S1_A + T1(59), STREET_X - 1.4, 9.5, 0)
stand(walker2, S1_B, STREET_X - 1.4, -12.0, 0)
stand(walker3, S1_A + T1(139), STREET_X - 1.0, 9.0, 0)
stand(walker3, S1_B, STREET_X - 1.0, -11.0, 0)
# two pedestrians are ALREADY mid-frame at the first frame, plus a later crosser,
# so the street reads busy from the open; all end off-frame (|y|>=11) and clear
# the S2 -Y opening before the cut
stand(walker4, S1_A, STREET_X - 0.6, -4.0, 180)
stand(walker4, S1_A + T1(230), STREET_X - 0.6, 12.0, 180)
stand(walker5, S1_A, STREET_X - 1.3, 3.5, 0)
stand(walker5, S1_A + T1(205), STREET_X - 1.3, -11.0, 0)
stand(walker6, S1_A + T1(140), STREET_X - 0.9, 11.0, 0)
stand(walker6, S1_A + T1(380), STREET_X - 0.9, -12.0, 0)
# a resident wakes, leaves cell k=+3 ... and it sweeps closed for cleaning
Y3 = 3 * PITCH
lie(resident, S1_A, Y3)
lie(resident, S1_A + T1(129), Y3)
sit(resident, S1_A + T1(184), Y3)
stand(resident, S1_A + T1(234), -0.5, Y3, -90)
stand(resident, S1_A + T1(299), STREET_X, Y3 + 0.8, -90)
key_obj(resident["root"], S1_A + T1(324), rot=(0, 0, math.radians(-180)))  # turns up-street
stand(resident, S1_A + T1(459), STREET_X - 0.4, Y3 + 6.0, -180)  # off along the street
key_neigh_piston(3, S1_A + T1(319), 0.0)
key_neigh_piston(3, S1_A + T1(429), -STROKE)
# ... while next door a finished cell reopens, ready (the wall breathes)
key_neigh_piston(2, S1_A + T1(339), -STROKE)
key_neigh_piston(2, S1_A + T1(449), 0.0)
shots.append(("S1_living_wall", S1_A, S1_B))

# ---- S2  THE PASS: wake -> pack up -> leave -> the cell closes ----
key_lens(S1_B, 28)                  # hold the wide lens right up to the cut
key_lens(S2_A, 35)
Y0 = -6.0                           # open on the lit/occupied k=-3 cell, not the dark closed end
# glide along the wall, ease to a stop at the hero cell as the guest leaves
key_cam(S2_A, (-3.0, Y0, 0.45), (0.3, Y0 + 2.2, OPEN_CZ + 0.05))
key_cam(S2_A + T2(300), (-3.1, -0.8, 0.45), (0.3, 0.3, OPEN_CZ + 0.05))
key_cam(S2_B, (-3.2, -0.9, 0.45), (0.3, 0.0, OPEN_CZ))
# the guest wakes, packs up (sits on the sill a beat), stands, and leaves
lie_sleep(guest, S2_A + T2(190), 0.0)
sit_mix(guest, S2_A + T2(270), 0.0)                            # sits up = packs up
stand(guest, S2_A + T2(330), -0.5, 0.0, -90)
stand(guest, S2_A + T2(370), STREET_X, 0.6, -90)
key_obj(guest["root"], S2_A + T2(392), rot=(0, 0, math.radians(-180)))   # turns up-street
stand(guest, S2_A + T2(450), STREET_X - 0.6, 5.0, -180)        # gone before the cell closes
# the cell closes behind them: the piston sweeps to flush by the cut to S3
key_xray(S2_A, 1.0)                                             # opaque through S2
key_piston(S2_A + T2(430), 0.0)
key_piston(S2_B, -STROKE)
shots.append(("S2_pass_and_leave", S2_A, S2_B))

# ---- S3  THE X-RAY CLEAN: the world dissolves to a void, a side-on view isolates
# the one cell, its near wall turns transparent, and the piston cleans the bore --
S3_HERO = {"CapsuleShell", "Piston", "WiperSeals", "Luminaire",
           "ChainMagazine", "ChainColumn", "Camera", "Focus"}
key_lens(S2_B, 35)                  # hold S2's lens to the cut
key_lens(S3_A, 55)                  # tighter for the isolate
# side-on to the hero bore (it runs along +X, centred y=0); a slow push in
key_cam(S3_A, (1.15, -3.4, 0.05), (1.15, 0.0, 0.0))
key_cam(S3_B, (1.15, -2.5, 0.02), (1.15, 0.0, 0.0))
# hide everything except the hero cell so the side view isolates it; the dip to
# black across the cut (setup_daynight) masks the pop -> reads as a dissolve
for _o in list(bpy.data.objects):
    if _o.name in S3_HERO:
        continue
    _o.hide_render = False
    _o.keyframe_insert("hide_render", frame=S2_B)
    _o.hide_render = True
    _o.keyframe_insert("hide_render", frame=S3_A)
# brighten the hero cell's own light for the isolated x-ray so the interior reads
_lum = bpy.data.objects.get("Luminaire")
if _lum and _lum.type == "LIGHT":
    _e0 = _lum.data.energy
    _lum.data.energy = _e0
    _lum.data.keyframe_insert("energy", frame=S2_B)
    _lum.data.energy = _e0 * 2.5
    _lum.data.keyframe_insert("energy", frame=S3_A + T3(20))
    _lum.data.keyframe_insert("energy", frame=END)

# the near wall turns transparent and the piston travels the bore, cleaning, and
# eases back open -- a clean start
key_xray(S2_B, 1.0)
key_xray(S3_A + T3(35), XRAY_A)
key_piston_glow(S2_B, 0.0)                                      # normal in S2
key_piston_glow(S3_A + T3(22), 5.0)                            # lights up as the scanner
key_piston_glow(END, 5.0)
key_piston(S3_A, -STROKE)                                       # starts closed/flush
key_piston(S3_A + T3(55), -STROKE)
key_piston(S3_A + T3(180), 0.0)                                 # sweeps back, cleaning, reopens
shots.append(("S3_xray_clean", S3_A, S3_B))


# ---- NLA clip schedules (poses; the roots above carry travel/facing) --------
# Sleep = the static tail of Death01 (the free UAL tier has no sleep loop; at
# these camera distances a held lying pose with the crossfades reads as sleep).
# NB: the lying->sitting crossfade must ride WITH the root's slide out of the
# bore (guest 700..760, resident 130..185) -- an earlier blend makes the body
# sit up inside the bore while the root still lies down (the "sprawl" bug).
# guest wake, upgraded to the retargeted Mixamo clips: a flat supine sleep, a
# relaxed sit-up on the sill, a real sit->stand, then walk off on a breathing idle.
# (UAL Walk_Loop is kept -- the Mixamo walk retarget name-collides with it and is
# unused; the resident/sitter still ride the UAL sit, so sit_mix is guest-only.)
play(guest, [
    ("Lay_Idle", 1, S2_A + T2(268), "loop"),
    ("Sit_Sill_Loop", S2_A + T2(268), S2_A + T2(300), "loop", T2(45)),
    ("Sit_To_Stand", S2_A + T2(300), S2_A + T2(330), "once"),
    ("Walk_Loop", S2_A + T2(330), S2_A + T2(460), "loop"),
    ("Idle_Breathe", S2_A + T2(460), END, "loop"),
])
play(resident, [
    ("Death01", 1, S1_A + T1(178), "still:57"),
    ("Sitting_Idle_Loop", S1_A + T1(178), S1_A + T1(208), "loop", T1(45)),
    ("Sitting_Exit", S1_A + T1(208), S1_A + T1(235), "once"),
    ("Walk_Loop", S1_A + T1(235), S1_A + T1(460), "loop"),
    ("Idle_Loop", S1_A + T1(460), END, "loop"),
])
play(sitter, [("Sitting_Idle_Loop", 1, END, "loop")])
play(walker1, [("Walk_Loop", 1, END, "loop")])
play(walker2, [("Walk_Formal_Loop", 1, END, "loop")])
play(walker3, [("Walk_Loop", 1, END, "loop")])
play(walker4, [("Walk_Loop", 1, END, "loop")])
play(walker5, [("Walk_Formal_Loop", 1, END, "loop")])
play(walker6, [("Walk_Loop", 1, END, "loop")])
play(sleeper_a, [("Lay_Idle", 1, END, "loop")])
play(sleeper_b, [("Lay_Idle", 1, END, "loop")])
# hero interior luminaire + beacon exist on the base cell; the greybox leaves their
# state animation to Phase 2 (lighting), when the day/night arc is built.


if os.environ.get("HC_DEBUG"):
    for o in bpy.data.objects:
        if o.name.startswith("KB_") and o.instance_collection:
            mn = [1e9] * 3; mx = [-1e9] * 3
            for src in o.instance_collection.all_objects:
                if src.type != "MESH":
                    continue
                m = o.matrix_world @ src.matrix_world
                for c in src.bound_box:
                    wv = m @ Vector(c)
                    for i in range(3):
                        mn[i] = min(mn[i], wv[i]); mx[i] = max(mx[i], wv[i])
            print("KBBOX| %-16s x[%6.1f..%6.1f] y[%6.1f..%6.1f] z[%6.1f..%6.1f]"
                  % (o.name, mn[0], mx[0], mn[1], mx[1], mn[2], mx[2]))


# =============================================================================
# render settings (greybox: Workbench draft, low res, fast)
# =============================================================================
sc.frame_start = 1
sc.frame_end = int(os.environ.get("HC_END", END))     # HC_END caps the range for previews
sc.frame_step = int(os.environ.get("HC_FSTEP", "1"))  # render every Nth frame (fast preview)
sc.render.fps = FPS
sc.render.resolution_x, sc.render.resolution_y = (960, 540)
sc.render.resolution_percentage = int(os.environ.get("HC_RESPCT", "100"))
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = OUT
os.makedirs(os.path.dirname(OUT), exist_ok=True)

if REAL:
    # Phase 2/3 look: licensed KitBash city lit at night. Cycles (CPU) is the
    # robust headless choice -- the flatpak Blender falls back to software GL, so
    # EEVEE cannot upload the 4K PBR textures. The KitBash emissive maps (windows,
    # signs, lamp heads) glow directly; the night HDRI + moon fill the rest.
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(os.environ.get("HC_SAMPLES", "48"))
    sc.cycles.use_denoising = True
    # the skyline towers are heavy and static -- reuse their BVH across frames so
    # each frame only re-syncs the cast/pistons that actually move
    sc.render.use_persistent_data = True
    setup_daynight()                    # day (S1) -> night (S2), keyframed at the cut
    sc.render.film_transparent = False
    # AgX rolls the hot KitBash signs/lamps off cleanly; Punchy keeps saturation.
    # Exposure is keyframed (day vs night) inside setup_daynight().
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
elif DRAFT:
    sc.render.engine = "BLENDER_WORKBENCH"
    for m in bpy.data.materials:
        if m.use_nodes and principled(m):
            m.diffuse_color = principled(m).inputs["Base Color"].default_value
    d = sc.display.shading
    # TEXTURE: characters show their PBR textures; untextured walls fall back
    # to the material colour copied above
    d.light = "STUDIO"; d.color_type = "TEXTURE"; d.show_shadows = True; d.show_cavity = True
    # NIGHT: a dark sky behind the dark road/building masses; the warm windows,
    # lamp heads and cells stay the brightest things in frame. Dim the studio
    # light so the scene sits in dusk rather than daylight.
    d.background_type = "VIEWPORT"
    d.background_color = (0.015, 0.02, 0.045)   # deep night-blue sky
    try:
        d.studiolight_intensity = 0.55
    except (AttributeError, TypeError):
        pass
    sc.display.render_aa = "FXAA"
    sc.render.film_transparent = False
else:
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    setup_daynight()

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
