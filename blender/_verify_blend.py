import bpy, os
ROOT = "/home/eddy/Projects/HiveCell"
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "blender", "narrative.blend"))
sc = bpy.context.scene

print("=" * 70)
print("narrative.blend INVENTORY")
print("frame range: %d..%d   engine: %s" % (sc.frame_start, sc.frame_end, sc.render.engine))

# linked libraries (currently expected: none -- everything baked local)
libs = list(bpy.data.libraries)
print("-" * 70)
print("LINKED LIBRARIES: %d" % len(libs))
for lb in libs:
    print("  %s" % lb.filepath)

# objects by type
from collections import Counter
by_type = Counter(o.type for o in bpy.data.objects)
print("-" * 70)
print("OBJECTS: %d total  %s" % (len(bpy.data.objects), dict(by_type)))

# the cell parts (hero + clones) -- these are what we'd relink to hivecell.blend
cell_pfx = ("CapsuleShell", "Piston", "WiperSeals", "ChainMagazine", "ChainColumn", "Luminaire")
cell_objs = [o for o in bpy.data.objects if any(o.name.startswith(p) for p in cell_pfx)]
linked_data = sum(1 for o in cell_objs if o.data and o.data.library)
print("-" * 70)
print("CELL PART OBJECTS: %d   (mesh data linked from a library: %d)"
      % (len(cell_objs), linked_data))

# animation: keyframed objects + channels, and NLA tracks
kf_objs = 0
kf_channels = 0
nla_chars = []
for o in bpy.data.objects:
    ad = o.animation_data
    if not ad:
        continue
    if ad.action:
        kf_objs += 1
    n_tracks = len(ad.nla_tracks)
    n_strips = sum(len(t.strips) for t in ad.nla_tracks)
    if n_tracks:
        nla_chars.append((o.name, n_tracks, n_strips))
# also material-node animation (xray alpha, piston glow, day/night)
mat_anim = [m.name for m in bpy.data.materials
            if m.node_tree and m.node_tree.animation_data and m.node_tree.animation_data.action]
world_anim = bool(sc.world and sc.world.node_tree and sc.world.node_tree.animation_data
                  and sc.world.node_tree.animation_data.action)
print("-" * 70)
print("ANIMATION")
print("  objects with an action (keyframes): %d" % kf_objs)
print("  armatures/objects with NLA tracks : %d" % len(nla_chars))
for nm, nt, ns in sorted(nla_chars):
    print("      %-16s tracks=%d strips=%d" % (nm, nt, ns))
print("  material node-trees animated (xray/piston/etc): %d  %s" % (len(mat_anim), mat_anim[:6]))
print("  world node-tree animated (day/night arc): %s" % world_anim)
print("=" * 70)
