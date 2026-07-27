import bpy, os, time
ROOT = "/home/eddy/Projects/HiveCell"


def env(k, d):
    return os.environ.get(k, d)


bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "blender", "narrative.blend"))
sc = bpy.context.scene

# --- CPU only. The Quadro M1200 is Maxwell (sm_50); Blender 5.2 + CUDA 13 can't
#     build a Cycles kernel for it, so GPU rendering is not viable on this box.
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'

# --- keep the blend's authored resolution / samples / denoise (source of
#     truth). HC_SAMPLES=N overrides samples without editing the blend -- handy
#     because the blend is often saved at low spp (e.g. 4) for viewport speed.
sc.render.resolution_percentage = int(env("HC_PCT", "100"))   # HC_PCT=40 -> low-res
if env("HC_SAMPLES", ""):
    sc.cycles.samples = int(env("HC_SAMPLES", ""))

# --- baked-in speedups (non-destructive; source textures + blend untouched):
#     * Texture limit clamps oversized KitBash maps. At 960x540 a 1024 cap is
#       ~5.8x faster and ~half the RAM with no visible loss (SSIM 0.999). Bump
#       to 2048 for 2K+ output. HC_TEXLIMIT=OFF disables.
#     * Persistent data reuses the built scene/BVH across frames.
lim = env("HC_TEXLIMIT", "1024")
if lim != "OFF":
    sc.render.use_simplify = True
    sc.cycles.texture_limit_render = lim
    sc.cycles.texture_limit = lim
sc.render.use_persistent_data = True

# --- frame rate: HC_FSTEP timeline-frames per rendered frame at 24fps base.
#     24 = 1fps, 12 = 2fps, 96 = 0.25fps.
sc.frame_step = int(env("HC_FSTEP", "24"))

out_dir = os.path.join(ROOT, "renders", env("HC_OUT", "narrative"))
os.makedirs(out_dir, exist_ok=True)
for f in os.listdir(out_dir):                    # clear stale frames of a prior step
    if f.startswith("f_") and f.endswith(".png"):
        os.remove(os.path.join(out_dir, f))
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(out_dir, "f_")

nframes = len(range(sc.frame_start, sc.frame_end + 1, sc.frame_step))
print("RENDER-CPU %dx%d spp=%d denoise=%s texlimit=%s persistent=%s step=%d -> %d frames"
      % (sc.render.resolution_x, sc.render.resolution_y, sc.cycles.samples,
         sc.cycles.use_denoising, lim, sc.render.use_persistent_data,
         sc.frame_step, nframes))

t0 = time.time()
bpy.ops.render.render(animation=True)
print("RENDER-CPU done in %.1fs" % (time.time() - t0))
