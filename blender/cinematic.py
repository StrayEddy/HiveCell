"""Render a very simple cinematic of the HiveCell model to renders/cinematic.mp4.

Run headless on the built scene (no window):
  flatpak run --filesystem=<repo> org.blender.Blender --background \
      <repo>/blender/hivecell.blend --python <repo>/blender/cinematic.py
Then encode the PNG frames to mp4 with the system ffmpeg (this Flatpak Blender
has no FFmpeg output):
  ffmpeg -y -framerate 24 -i renders/frames/f_%04d.png \
      -c:v libx264 -pix_fmt yuv420p -crf 18 renders/cinematic.mp4

A slow camera move: an establishing wide of the cell-in-wall that glides in and
settles on the mouth/entry. Uses the scene's existing camera (which tracks the
"Focus" empty) + materials/HDRI/lighting from build_scene.py. EEVEE, so it is
quick. Adjust DURATION/RES below; re-run to re-render.
"""
import bpy

DRAFT = True                       # True: fast Workbench frames. False: EEVEE quality pass.
FPS = 24
DURATION = 30.0                    # seconds
RES = (960, 540) if DRAFT else (1280, 720)
SAMPLES = 16                       # EEVEE TAA samples (a moving shot hides low counts)
# This Flatpak Blender has no FFmpeg output, so render a PNG sequence; a separate
# ffmpeg step (see the module docstring) encodes renders/frames/*.png -> mp4.
FRAMES = "/home/eddy/Projects/HiveCell/renders/frames/f_"

cam = bpy.context.scene.camera
focus = bpy.data.objects.get("Focus")
f_end = int(round(FPS * DURATION))

# A slow, eased (Bezier) multi-shot camera move that always stays in front of the
# wall: establishing wide -> glide down to the mouth -> low hero at the entry ->
# rise + pull back along the barrel -> settle on a 3/4 hero. Each row is
# (time fraction, camera location, focus/aim location).
path = [
    (0.00, (-4.6, -12.0, 5.0), (1.3, 0.0, -0.10)),
    (0.22, (-3.4, -7.6, 2.3), (0.45, 0.0, -0.15)),
    (0.48, (-2.1, -4.9, 0.9), (0.15, 0.0, -0.05)),
    (0.72, (0.7, -8.3, 2.9), (1.7, 0.0, -0.10)),
    (1.00, (-2.6, -10.6, 3.7), (1.3, 0.0, -0.15)),
]
for frac, cloc, floc in path:
    fr = max(1, int(round(frac * f_end)))
    cam.location = cloc
    cam.keyframe_insert(data_path="location", frame=fr)
    if focus:
        focus.location = floc
        focus.keyframe_insert(data_path="location", frame=fr)

sc = bpy.context.scene
sc.frame_start = 1
sc.frame_end = f_end
sc.render.fps = FPS
sc.render.resolution_x, sc.render.resolution_y = RES

if DRAFT:
    # Workbench: the viewport renderer -- near-instant frames, no lighting/reflection
    # solve. Enough to review the camera move + timing; quality comes from the EEVEE
    # pass (DRAFT=False). Push each material's base colour to its viewport colour so
    # the parts stay distinguishable.
    sc.render.engine = "BLENDER_WORKBENCH"
    for m in bpy.data.materials:
        if m.use_nodes:
            b = m.node_tree.nodes.get("Principled BSDF")
            if b:
                m.diffuse_color = b.inputs["Base Color"].default_value
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_shadows = True
    sh.show_cavity = True
    sc.display.render_aa = "FXAA"     # cheapest anti-aliasing
else:
    try:
        sc.eevee.taa_render_samples = SAMPLES
        sc.eevee.use_raytracing = True
    except Exception:
        pass

sc.render.image_settings.file_format = "PNG"
sc.render.filepath = FRAMES        # Blender appends the zero-padded frame number

print("cinematic: %d frames @ %d fps -> %s####.png" % (f_end, FPS, FRAMES))
bpy.ops.render.render(animation=True)
print("cinematic: done", FRAMES)
