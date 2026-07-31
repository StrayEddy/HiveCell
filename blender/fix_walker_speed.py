"""Fix the background pedestrians' foot-slide: their empties (WalkerN) translated
2x-12x faster than the in-place walk cycle's stride, on eased (bezier) curves.

The Walk_Loop / Walk_Formal_Loop clips advance ~1.36 m per 32f gait cycle
(measured foot-bone stride) => a natural ground speed of ~1.0 m/s. This retimes
each walker to a constant (LINEAR) ~1.05 m/s: keep the authored START keyframe,
END position and DIRECTION (the staged path is unchanged), and recompute the END
FRAME from that speed, clamped to frame 552 where the rig walk NLA ends (so the
empty never travels while the cycle isn't playing).

Run: /usr/bin/blender -b blender/narrative.blend --factory-startup -P blender/fix_walker_speed.py
"""
import bpy, os

ROOT = "/home/eddy/Projects/HiveCell"
NARR = os.path.join(ROOT, "blender", "narrative.blend")
SPEED = 1.05          # m/s, ~ the clips' measured natural walk speed (1.02)
WALK_END = 552        # last frame the rig walk NLA plays


def loc_fcurves(act):
    src = []
    try:
        for lay in act.layers:
            for st in lay.strips:
                for cb in st.channelbags:
                    src.extend(cb.fcurves)
    except Exception:
        pass
    if not src:
        src = list(act.fcurves)
    return {fc.array_index: fc for fc in src if fc.data_path == "location"}


bpy.ops.wm.open_mainfile(filepath=NARR)
fps = bpy.context.scene.render.fps

for n in range(1, 7):
    emp = bpy.data.objects.get("Walker%d" % n)
    fcs = loc_fcurves(emp.animation_data.action)
    assert set(fcs) >= {0, 1, 2}, "Walker%d missing loc channels" % n
    assert all(len(fcs[i].keyframe_points) == 2 for i in (0, 1, 2)), \
        "Walker%d: expected 2 keys/channel" % n

    start_f = fcs[1].keyframe_points[0].co.x
    p0 = tuple(fcs[i].keyframe_points[0].co.y for i in (0, 1, 2))
    p1 = tuple(fcs[i].keyframe_points[1].co.y for i in (0, 1, 2))
    dist = sum((p1[i] - p0[i]) ** 2 for i in range(3)) ** 0.5

    dur_f = dist / SPEED * fps
    new_end = min(int(round(start_f + dur_f)), WALK_END)
    new_end = max(new_end, int(start_f) + 1)
    real_speed = dist / ((new_end - start_f) / fps)

    for i in (0, 1, 2):
        kps = fcs[i].keyframe_points
        kps[1].co.x = new_end
        kps[1].handle_left.x = new_end - 2
        kps[1].handle_right.x = new_end + 2
        for k in kps:
            k.interpolation = "LINEAR"
        fcs[i].extrapolation = "CONSTANT"      # hold pos outside the travel span
        fcs[i].update()

    print("Walker%d  dist=%.1fm  frames %d->%d  speed=%.2f m/s%s"
          % (n, dist, int(start_f), new_end, real_speed,
             "  (clamped to walk end)" if new_end == WALK_END and dur_f + start_f > WALK_END else ""))

bpy.ops.wm.save_as_mainfile(filepath=NARR)
print("SAVED", NARR)
