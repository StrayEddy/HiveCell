"""Build the HiveCell full-model Blender scene (investor-grade render base).

Run headless (no window -- Cycles renders to a file):
  flatpak run org.blender.Blender --background \
      --python /home/eddy/Projects/HiveCell/blender/build_scene.py

Imports the FreeCAD-exported parts (blender/models/*.obj, meters, Z-up),
assembles the full model, sets the cell INTO a wall with its mouth sill ~500 mm
above the ground (ADR-0013 siting), assigns PBR materials, lights it studio-
style, frames a hero camera, then saves blender/hivecell.blend and renders
renders/preview.png. Regenerate the meshes first with scripts/export_blender.py.

For photoreal stainless it uses a CC0 studio HDRI at blender/hdri/studio.hdr --
run scripts/fetch_assets.sh once to download it (else it falls back to a
procedural gradient world). GPU (OptiX/CUDA) is used if the Flatpak can reach it.

Design lives HERE (materials/lighting/camera) + in the CAD; re-run to rebuild.
"""
import bpy
import json
import math
import os
from mathutils import Vector

ROOT = "/home/eddy/Projects/HiveCell"
MODELS = os.path.join(ROOT, "blender", "models")
OUT_BLEND = os.path.join(ROOT, "blender", "hivecell.blend")
OUT_PREVIEW = os.path.join(ROOT, "renders", "preview.png")

# Render look: "night" = interior-light hero (dark scene, the ADR-0014 warm crown
# luminaire is the focal source, warm glow rakes the stainless); "studio" = the
# original bright product shot. Override with HIVECELL_RENDER=studio.
MODE = os.environ.get("HIVECELL_RENDER", "night")

with open(os.path.join(MODELS, "scene.json")) as f:
    S = json.load(f)


# --- helpers -----------------------------------------------------------------
def pbr(name, base, metallic=0.0, roughness=0.5, anisotropic=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    if "Anisotropic" in b.inputs:
        b.inputs["Anisotropic"].default_value = anisotropic
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND"
    return m


def brushed(mat, rough_lo, rough_hi, scale=520.0):
    """Fake a brushed-metal finish: fine bands drive a tight roughness variation
    (along X, the barrel's length), for a directional satin sheen under the HDRI."""
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 1.5
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (rough_lo, rough_lo, rough_lo, 1.0)
    ramp.color_ramp.elements[1].color = (rough_hi, rough_hi, rough_hi, 1.0)
    nt.links.new(tex.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Roughness"])
    return mat


def box(name, size, center, mat):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=center)  # unit cube -1..1
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    return o


def import_part(part, mat):
    bpy.ops.wm.obj_import(filepath=os.path.join(MODELS, part + ".obj"),
                          up_axis="Z", forward_axis="Y")
    objs = list(bpy.context.selected_objects)
    for o in objs:
        o.name = part
        o.data.materials.clear()
        o.data.materials.append(mat)
        # smooth shading so the rounded corners read as curved, not faceted
        for p in o.data.polygons:
            p.use_smooth = True
    return objs


# --- clean slate -------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- materials ---------------------------------------------------------------
mat_steel = brushed(pbr("Steel", (0.64, 0.66, 0.69), metallic=1.0, anisotropic=0.3), 0.18, 0.30)
mat_piston = brushed(pbr("PistonSteel", (0.80, 0.82, 0.85), metallic=1.0, anisotropic=0.4), 0.14, 0.24)
mat_seal = pbr("Seal", (0.05, 0.05, 0.06), metallic=0.0, roughness=0.85)
mat_mag = pbr("Magazine", (0.22, 0.23, 0.26), metallic=1.0, roughness=0.45)
mat_chain = pbr("Chain", (0.45, 0.47, 0.50), metallic=1.0, roughness=0.35)
mat_wall = pbr("Wall", (0.40, 0.40, 0.42), metallic=0.0, roughness=0.85)
mat_floor = pbr("Floor", (0.16, 0.17, 0.18), metallic=0.0, roughness=0.95)

PART_MAT = {
    "CapsuleShell": mat_steel, "Piston": mat_piston, "WiperSeals": mat_seal,
    "ChainMagazine": mat_mag, "ChainColumn": mat_chain,
}

# --- import the full model ---------------------------------------------------
imported = {}
for part in S["parts"]:
    imported[part] = import_part(part, PART_MAT[part])

shell = bpy.data.objects["CapsuleShell"]
bb = [shell.matrix_world @ Vector(c) for c in shell.bound_box]
zmin = min(v.z for v in bb)
zmax = max(v.z for v in bb)
ymin = min(v.y for v in bb)
ymax = max(v.y for v in bb)
xmin = min(v.x for v in bb)
print("SHELL bbox  X[%.3f]  Y[%.3f,%.3f]  Z[%.3f,%.3f]" % (xmin, ymin, ymax, zmin, zmax))

t = S["wall_thickness_m"]
sill = S["sill_height_m"]
floor_z = (zmin + t) - sill            # interior floor is sill above the ground

# --- ground + wall the cell is set into --------------------------------------
box("Ground", (16.0, 12.0, 0.2), (1.2, 0.0, floor_z - 0.1), mat_floor)

reveal = 0.03
ob = zmin - reveal                      # opening bottom (barrel outer)
ot = zmax + reveal                      # opening top
ohw = (ymax - ymin) * 0.5 + reveal      # opening half-width (Y)
whw = ohw + 1.6                         # wall half-span (Y) -- a wall segment, not a plane
wtop = ot + 1.0                         # wall top (Z)
fd = 0.25                               # facade depth (X in [mouth, +fd])
cx = S["mouth_x_m"] + fd * 0.5
box("Wall_spandrel", (fd, 2 * whw, ob - floor_z), (cx, 0.0, (floor_z + ob) * 0.5), mat_wall)
box("Wall_head", (fd, 2 * whw, wtop - ot), (cx, 0.0, (ot + wtop) * 0.5), mat_wall)
box("Wall_jambL", (fd, whw - ohw, ot - ob), (cx, -(ohw + whw) * 0.5, (ob + ot) * 0.5), mat_wall)
box("Wall_jambR", (fd, whw - ohw, ot - ob), (cx, (ohw + whw) * 0.5, (ob + ot) * 0.5), mat_wall)

# --- ADR-0014 interior luminaire: warm crown strip + co-located wash light ----
# An emissive strip at the bore crown running along X (CAD/manifest dims), plus a
# rectangular area light so the strip actually washes the interior. In night mode
# this is the dominant source; in studio mode it's a subtle present-but-not-hero.
AMBER = (1.0, 0.62, 0.26)                       # ADR-0014 warm night-glow (sleep-safe)
lum_margin = S["luminaire_end_margin_m"]
lum_len = S["luminaire_length_m"]
lum_wid = S["luminaire_width_m"]
lum_cx = S["mouth_x_m"] + lum_margin + lum_len * 0.5
lum_y = (ymin + ymax) * 0.5
lum_z = zmax - 0.04                             # just under the bore crown
lum_mat = bpy.data.materials.new("Luminaire")
lum_mat.use_nodes = True
_lnt = lum_mat.node_tree
_em = _lnt.nodes.new("ShaderNodeEmission")
_em.inputs["Color"].default_value = (*AMBER, 1.0)
_em.inputs["Strength"].default_value = 3.8 if MODE == "night" else 1.2
_lnt.links.new(_em.outputs["Emission"], _lnt.nodes["Material Output"].inputs["Surface"])
box("Luminaire", (lum_len, lum_wid, 0.02), (lum_cx, lum_y, lum_z), lum_mat)
bpy.ops.object.light_add(type="AREA", location=(lum_cx, lum_y, lum_z - 0.02))
lum_light = bpy.context.active_object
lum_light.name = "LuminaireLight"
lum_light.data.shape = "RECTANGLE"
lum_light.data.size = 0.16
lum_light.data.size_y = lum_len                 # a long strip light down the bore
lum_light.data.color = AMBER
lum_light.data.energy = 70.0 if MODE == "night" else 16.0   # points -Z, washes the bore

# --- lighting (studio 3-point + soft world) ----------------------------------
world = bpy.data.worlds.new("W")
world.use_nodes = True
wn = world.node_tree
bg = wn.nodes["Background"]
HDRI = os.path.join(ROOT, "blender", "hdri", "studio.hdr")
if os.path.exists(HDRI):
    # Real studio HDRI: gives the stainless proper softbox reflections + fill.
    env = wn.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI)
    mapp = wn.nodes.new("ShaderNodeMapping")
    tex = wn.nodes.new("ShaderNodeTexCoord")
    mapp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(110))  # aim softboxes
    wn.links.new(tex.outputs["Generated"], mapp.inputs["Vector"])
    wn.links.new(mapp.outputs["Vector"], env.inputs["Vector"])
    # Show the HDRI only to reflection/lighting rays; give the CAMERA a clean neutral
    # backdrop (a busy studio photo behind the product looks unprofessional).
    lp = wn.nodes.new("ShaderNodeLightPath")
    mix = wn.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (0.72, 0.74, 0.78, 1.0)   # B: camera backdrop
    wn.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    wn.links.new(env.outputs["Color"], mix.inputs[6])       # A: HDRI (reflections/light)
    wn.links.new(mix.outputs[2], bg.inputs[0])
    bg.inputs[1].default_value = 1.0
    print("world: HDRI", HDRI)
else:
    # Fallback: neutral studio gradient (brighter top, darker floor).
    grad = wn.nodes.new("ShaderNodeTexGradient")
    ramp = wn.nodes.new("ShaderNodeValToRGB")
    tex = wn.nodes.new("ShaderNodeTexCoord")
    mapp = wn.nodes.new("ShaderNodeMapping")
    mapp.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    wn.links.new(tex.outputs["Generated"], mapp.inputs["Vector"])
    wn.links.new(mapp.outputs["Vector"], grad.inputs["Vector"])
    wn.links.new(grad.outputs["Color"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].color = (0.10, 0.11, 0.13, 1.0)
    ramp.color_ramp.elements[1].color = (0.55, 0.58, 0.62, 1.0)
    wn.links.new(ramp.outputs["Color"], bg.inputs[0])
    bg.inputs[1].default_value = 1.2
    print("world: gradient fallback (no HDRI)")
bpy.context.scene.world = world

if MODE == "night":
    # Deep, dim night: the warm crown luminaire becomes the brightest thing in
    # frame, so it reads as a light and its glow rakes across the stainless.
    nworld = bpy.data.worlds.new("W_night")
    nworld.use_nodes = True
    nbg = nworld.node_tree.nodes["Background"]
    nbg.inputs[0].default_value = (0.02, 0.026, 0.04, 1.0)   # cool near-black
    nbg.inputs[1].default_value = 0.22                       # enough ambient to read the form
    bpy.context.scene.world = nworld
    print("world: night (dark) — luminaire is the hero source")


def area_light(name, loc, energy, size, target):
    bpy.ops.object.light_add(type="AREA", location=loc)
    o = bpy.context.active_object
    o.name = name
    o.data.energy = energy
    o.data.size = size
    c = o.constraints.new("TRACK_TO")
    c.target = target
    return o


focus = bpy.data.objects.new("Focus", None)          # aim point for lights + cam
bpy.context.collection.objects.link(focus)
focus.location = (1.0, 0.0, (floor_z + zmax) * 0.5)

# HDRI provides the ambient fill + reflections; add just a sun for a crisp
# grounding shadow and one soft key to shape the barrel.
bpy.ops.object.light_add(type="SUN")
sun = bpy.context.active_object
sun.data.angle = math.radians(3.0)
sun.rotation_euler = (math.radians(58), 0.0, math.radians(40))
if MODE == "night":
    sun.data.energy = 0.45                 # cool moon rim: lifts the wall/stainless form
    sun.data.color = (0.55, 0.70, 1.0)
    area_light("Key", (-3.0, -4.0, 3.5), 45.0, 4.0, focus)   # dim cool fill (shape only)
else:
    sun.data.energy = 1.1
    area_light("Key", (-3.0, -4.0, 3.5), 250.0, 4.0, focus)

# --- hero camera: broadside 3/4 showing the whole assembly, wall at the mouth,
# barrel -> chain -> magazine receding, all elevated above the ground ---------
if MODE == "night":
    # Look INTO the mouth from the room side so the glowing crown + warm interior
    # read (a broadside only shows the opaque exterior barrel, not the light).
    zc = (zmin + zmax) * 0.5
    cam_loc, lens = (-3.7, -2.3, zc + 0.72), 38   # pulled back: wall + glowing mouth read
    focus.location = (0.6, 0.0, zc)
else:
    cam_loc, lens = (-1.2, -8.5, 2.6), 45
    focus.location = (1.35, 0.0, (floor_z + zmax) * 0.5)
bpy.ops.object.camera_add(location=cam_loc)
cam = bpy.context.active_object
cam.data.lens = lens
c = cam.constraints.new("TRACK_TO")
c.target = focus
bpy.context.scene.camera = cam

# --- render settings ---------------------------------------------------------
sc = bpy.context.scene
# EEVEE (fast, works great for interactive shading-view tweaking) -- the .blend
# opens ready to work in EEVEE every time. Engine id varies by Blender version.
engines = sc.render.bl_rna.properties["engine"].enum_items.keys()
EEVEE = next((e for e in engines if "EEVEE" in e), "BLENDER_EEVEE_NEXT")
sc.render.engine = EEVEE
print("render engine:", EEVEE)
# Raytraced reflections so the stainless still reflects the HDRI in EEVEE.
try:
    sc.eevee.use_raytracing = True
except Exception as e:
    print("eevee raytracing unavailable:", e)
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass
sc.render.resolution_x = 1792
sc.render.resolution_y = 1008
sc.render.film_transparent = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.exposure = -0.15 if MODE == "night" else 0.0
os.makedirs(os.path.dirname(OUT_PREVIEW), exist_ok=True)
sc.render.filepath = OUT_PREVIEW

# Prefer a shaded viewport every time: set every 3D viewport to Material Preview.
# (The active-workspace switch needs a real UI, so blender/finalize_shading.py --
# run in a GUI after this -- makes the Shading tab active and re-saves.)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "MATERIAL"

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("saved", OUT_BLEND)
bpy.ops.render.render(write_still=True)
print("rendered", OUT_PREVIEW)
