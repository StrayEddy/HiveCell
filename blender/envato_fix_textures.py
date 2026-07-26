"""Repoint KitBash image paths to the textures Envato actually ships beside the
blend. The blends reference a shared '//../../../KB3DTextures/4k/<name>.png'
library that the Elements download doesn't include -- instead every texture is
flattened into the item folder. We index the item folder by basename and rewrite
each image filepath to the real file (absolute; these blends are local, gitignored
and re-downloadable). Run headless per blend, saves in place."""
import bpy, os, glob

ENV = "/home/eddy/Projects/HiveCell/assets/envato"
p = bpy.data.filepath
item = os.path.relpath(p, ENV).split(os.sep)[0]
itemroot = os.path.join(ENV, item)

index = {}
for f in glob.glob(itemroot + "/**/*.png", recursive=True):
    index.setdefault(os.path.basename(f).lower(), f)

fixed = missing = 0
misses = []
for im in bpy.data.images:
    if not im.filepath or im.packed_file:
        continue
    bn = os.path.basename(im.filepath.replace("\\", "/")).lower()
    if bn in index:
        im.filepath = index[bn]
        try:
            im.reload()
        except RuntimeError:
            pass
        fixed += 1
    else:
        missing += 1
        misses.append(bn)

bpy.ops.wm.save_mainfile()
print("FIX| %-34s fixed=%-4d missing=%-3d %s"
      % (item, fixed, missing, ("MISS:" + ",".join(misses[:4])) if misses else ""))
