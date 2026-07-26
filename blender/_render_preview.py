import bpy, os, time
ROOT = "/home/eddy/Projects/HiveCell"
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "blender", "narrative.blend"))
sc = bpy.context.scene

sc.render.resolution_percentage = 75         # mid res (base 960x540 -> 720x405)
sc.cycles.samples = 24                        # fewer samples -> faster
sc.cycles.use_denoising = True                # essential at low samples
sc.frame_step = int(os.environ.get("HC_FSTEP", "12"))   # very low fps: every Nth frame

sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(ROOT, "renders", "narrative", "f_")

# optional single-frame timing test: HC_TESTFRAME=360
tf = os.environ.get("HC_TESTFRAME")
rx = sc.render.resolution_x * sc.render.resolution_percentage // 100
ry = sc.render.resolution_y * sc.render.resolution_percentage // 100
print("PREVIEW: %dx%d  samples=%d  denoise=%s  step=%d  (1..%d)"
      % (rx, ry, sc.cycles.samples, sc.cycles.use_denoising, sc.frame_step, sc.frame_end))

t0 = time.time()
if tf:
    sc.frame_set(int(tf))
    bpy.ops.render.render(write_still=True)
    print("TESTFRAME %s rendered in %.1fs" % (tf, time.time() - t0))
else:
    bpy.ops.render.render(animation=True)
    print("preview render done in %.1fs" % (time.time() - t0))
