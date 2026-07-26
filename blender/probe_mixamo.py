"""Probe a Mixamo FBX for the rig facts the narrative timeline is calibrated to.

Purpose: before deciding to swap the Quaternius rig for a Mixamo-skeleton
character (see narrative_cinematic.py header + the make_person / sit / lie / stand
constants), we need to KNOW the new rig's numbers rather than guess them. This
imports one FBX headless and prints, in the same idiom as the script's "Empirical
rig facts" comment block:

  * unit SCALE      -- Mixamo FBX usually lands at 100x (centimetres); height in
                       metres tells us the correction factor to apply
  * FACING yaw      -- Quaternius faces local -Y; Mixamo typically +Y. Derived
                       from the feet (ankle->toe horizontal), so it works on a
                       plain T-pose character with no animation
  * key HEIGHTS     -- feet (origin check), hips (sit-height basis), head, hands
  * posed HIP RANGE -- if the FBX carries a clip (a Mixamo *animation* download,
                       not a bare character), the min/max hip Z across the frames
                       -- this is what a sit / crawl / lie root offset keys off

Run (flatpak Blender, same pattern as render_narrative.sh):
  HC_FBX=/path/to/Mixamo.fbx \
  flatpak run --filesystem=/home/eddy/Projects/HiveCell org.blender.Blender \
      --background --python /home/eddy/Projects/HiveCell/blender/probe_mixamo.py

The FBX path comes from $HC_FBX, or the first argument after a `--` on the
command line. Nothing is saved or rendered -- it only prints.
"""
import bpy
import os
import sys
import math
from mathutils import Vector


def fbx_path():
    env = os.environ.get("HC_FBX", "").strip()
    if env:
        return env
    if "--" in sys.argv:                       # blender passes script args after `--`
        rest = sys.argv[sys.argv.index("--") + 1:]
        if rest:
            return rest[0]
    return ""


def wipe_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def find_bone(pbones, *suffixes):
    """Mixamo names are like 'mixamorig:Hips'; match case-insensitively on the
    tail so we survive prefix/colon mangling by the importer."""
    low = {pb.name.lower(): pb for pb in pbones}
    for suf in suffixes:
        s = suf.lower()
        for name, pb in low.items():
            if name.endswith(s):
                return pb
    return None


def whead(arm, pb):
    """World-space head of a posed bone."""
    return arm.matrix_world @ pb.head


def main():
    path = fbx_path()
    print("=" * 72)
    if not path:
        print("PROBE ERROR: no FBX given. Set HC_FBX=/path/to/file.fbx "
              "(or pass it after `--`).")
        return
    if not os.path.exists(path):
        print("PROBE ERROR: FBX not found: %s" % path)
        return

    wipe_scene()
    try:
        bpy.ops.import_scene.fbx(filepath=path)
    except Exception as e:                      # importer disabled / bad file
        print("PROBE ERROR: FBX import failed: %r" % e)
        return

    print("PROBE FBX:", path)
    objs = list(bpy.data.objects)
    arm = next((o for o in objs if o.type == "ARMATURE"), None)
    meshes = [o for o in objs if o.type == "MESH"]
    if arm is None:
        print("PROBE ERROR: no armature in the FBX.")
        return

    # --- SCALE: overall world-space height across all mesh geometry -----------
    if meshes:
        zs, allpts = [], []
        for o in meshes:
            for c in o.bound_box:
                wv = o.matrix_world @ Vector(c)
                allpts.append(wv)
        zmin = min(p.z for p in allpts)
        zmax = max(p.z for p in allpts)
        height = zmax - zmin
    else:
        zmin = zmax = height = float("nan")
    print("-" * 72)
    print("SCALE")
    print("  object matrix_world scale : %s" % (tuple(round(v, 4) for v in arm.matrix_world.to_scale()),))
    print("  mesh height (world Z)     : %.4f   (feet z=%.4f  crown z=%.4f)" % (height, zmin, zmax))
    if height > 10:
        print("  -> looks like CENTIMETRES; apply scale ~%.4f to reach ~1.8 m" % (1.8 / height))
    elif height > 0:
        print("  -> already ~metres (Quaternius was ~1.77 m)")

    # --- BONES ----------------------------------------------------------------
    pbones = arm.pose.bones
    names = [pb.name for pb in pbones]
    mix = any("mixamorig" in n.lower() for n in names)
    print("-" * 72)
    print("SKELETON")
    print("  bone count : %d   mixamorig-prefixed: %s" % (len(names), mix))
    print("  sample     : %s" % ", ".join(names[:6]))

    hips = find_bone(pbones, "Hips", "pelvis")
    head = find_bone(pbones, "Head")
    footL = find_bone(pbones, "LeftFoot", "foot_l")
    footR = find_bone(pbones, "RightFoot", "foot_r")
    toeL = find_bone(pbones, "LeftToeBase", "LeftToe_End", "ball_l")
    handR = find_bone(pbones, "RightHand", "hand_r")
    upLegL = find_bone(pbones, "LeftUpLeg", "thigh_l")
    upLegR = find_bone(pbones, "RightUpLeg", "thigh_r")

    # --- FACING: ankle -> toe, projected horizontal. Report as a yaw and as a
    #     compass so it maps onto the script's yaw convention (Quaternius faces
    #     local -Y; stand/sit/lie use -90 to face out of the wall, toward -X). --
    print("-" * 72)
    print("FACING")
    if footL and toeL:
        fwd = whead(arm, toeL) - whead(arm, footL)
        fwd.z = 0.0
        if fwd.length > 1e-5:
            fwd.normalize()
            yaw = math.degrees(math.atan2(fwd.y, fwd.x))
            comp = {0: "+X", 90: "+Y", 180: "-X", -90: "-Y", -180: "-X"}
            near = min(comp, key=lambda a: abs(((yaw - a + 180) % 360) - 180))
            print("  forward (ankle->toe) : (%.3f, %.3f)  yaw=%.1f deg  ~faces %s"
                  % (fwd.x, fwd.y, yaw, comp[near]))
            print("  (Quaternius faces -Y. If this differs, every stand/sit/lie "
                  "yaw in the timeline shifts by the delta.)")
        else:
            print("  ankle and toe coincide horizontally -- can't derive facing.")
    else:
        print("  no foot/toe bones found -- can't derive facing from feet.")

    # --- KEY HEIGHTS (rest / current pose) ------------------------------------
    print("-" * 72)
    print("KEY HEIGHTS (world Z, current frame)")
    for label, pb in [("feet(min mesh z)", None), ("hips", hips), ("head", head),
                      ("hand_r", handR), ("foot_l", footL)]:
        if pb is None and label.startswith("feet"):
            print("  %-16s : %.4f" % (label, zmin))
        elif pb is not None:
            print("  %-16s : %.4f   (bone '%s')" % (label, whead(arm, pb).z, pb.name))

    # --- ANIMATED HIP RANGE: only meaningful if the FBX carries a clip ---------
    print("-" * 72)
    print("POSED HIP RANGE (only if this FBX is an animation, not a bare character)")
    ad = arm.animation_data
    action = ad.action if (ad and ad.action) else None
    if action and hips:
        f0, f1 = (int(action.frame_range[0]), int(action.frame_range[1]))
        dg = bpy.context.evaluated_depsgraph_get()
        lo, hi, lo_f, hi_f = 1e9, -1e9, f0, f0
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            z = whead(arm, arm.pose.bones[hips.name]).z
            if z < lo:
                lo, lo_f = z, f
            if z > hi:
                hi, hi_f = z, f
        print("  action '%s'  frames %d..%d" % (action.name, f0, f1))
        print("  hip Z min : %.4f (frame %d)   max : %.4f (frame %d)   travel: %.4f"
              % (lo, lo_f, hi, hi_f, hi - lo))
        print("  -> a low plateau ~ sit/crawl/lie hip height; feed it into a "
              "root offset the way SIT_Z does for Quaternius.")
    else:
        print("  no action on the armature (this is a T-pose character export) --")
        print("  re-run on a Mixamo *animation* FBX to get sit/crawl hip heights.")

    print("=" * 72)
    print("PROBE DONE")


main()
