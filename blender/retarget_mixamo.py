"""Retarget Mixamo FBX clips onto the Quaternius (UE-mannequin) rig and bake them
to Actions, so the CC0 cast can play Mixamo motion with NO character swap and NO
retargeting addon. Both rigs are standard A-pose humanoids -- _rest_compare.py
showed limb bones agree to ~1 deg and the worst bone (neck) to ~17 deg -- so a
world-space rest-delta transfer is robust:

  desired_target_world_rot = (src_posed_rot . src_rest_rot^-1) . target_rest_rot

i.e. copy each bone's world-space rotation *change from its own rest* onto the
target bone's rest. The pelvis also takes the source hip's world translation
delta (in metres -- world space already absorbs Mixamo's 0.01 object scale), so
crouches / lying / sitting drop the body correctly. Everything is baked to
rotation_quaternion (+ pelvis location) keyframes -> plain Actions that behave
exactly like the UAL clips in narrative_cinematic.py's play() / NLA system.

Modes:
  HC_TEST=1            retarget ONE clip (HC_ONE, default "Sleeping Idle"),
                       apply it to the Quaternius body and render a verification
                       still to renders/retarget_<clip>.png -- eyeball it first.
  (default)            retarget every FBX in HC_DIR and save the baked Actions to
                       assets/quaternius/UAL2_Mixamo.blend (fake-user'd), the
                       second clip library narrative_cinematic.py will load.

Run (flatpak, --filesystem=home to reach ~/Downloads):
  HC_TEST=1 flatpak run --filesystem=home org.blender.Blender \
      --background --python blender/retarget_mixamo.py
"""
import bpy, os, glob, math
from mathutils import Vector, Matrix

ROOT = "/home/eddy/Projects/HiveCell"
QUAT = os.path.join(ROOT, "assets/quaternius/Universal Base Characters[Standard]",
                    "Base Characters", "Godot - UE", "Superhero_Male_FullBody.gltf")
DIR = os.environ.get("HC_DIR", "/home/eddy/Downloads")
OUTLIB = os.path.join(ROOT, "assets/quaternius/UAL2_Mixamo.blend")
TEST = os.environ.get("HC_TEST", "0") == "1"
ONE = os.environ.get("HC_ONE", "Sleeping Idle")

# Mixamo bone -> Quaternius (UE mannequin) bone. Fingers omitted (left at rest).
MAP = {"Hips": "pelvis", "Spine": "spine_01", "Spine1": "spine_02", "Spine2": "spine_03",
       "Neck": "neck_01", "Head": "Head",
       "LeftShoulder": "clavicle_l", "LeftArm": "upperarm_l", "LeftForeArm": "lowerarm_l",
       "LeftHand": "hand_l", "RightShoulder": "clavicle_r", "RightArm": "upperarm_r",
       "RightForeArm": "lowerarm_r", "RightHand": "hand_r",
       "LeftUpLeg": "thigh_l", "LeftLeg": "calf_l", "LeftFoot": "foot_l", "LeftToeBase": "ball_l",
       "RightUpLeg": "thigh_r", "RightLeg": "calf_r", "RightFoot": "foot_r", "RightToeBase": "ball_r"}
# clean Action names for the ones we keep (file stem -> Action)
RENAME = {"Sleeping Idle": "Sleep_Idle", "Laying Idle": "Lay_Idle",
          "Sitting Idle": "Sit_Sill_Loop", "Sitting Idle (1)": "Sit_Floor_KneeUp",
          "Sit To Stand": "Sit_To_Stand", "Stand Up": "Stand_Up_Low",
          "Crawling": "Crawl_Fwd_Loop", "Kneeling Down": "Kneel_Down",
          "Picking Up": "Pick_Up", "Breathing Idle": "Idle_Breathe",
          "Standard Walk": "Walk_Std_Loop", "Walking (1)": "Walk_Loop",
          "Lying Down": "Lie_Down", "Sitting": "Sit_Down"}


def norm3(m4):
    """3x3 rotation of a 4x4, columns normalized (strip object/import scale)."""
    m = m4.to_3x3()
    for i in range(3):
        c = m.col[i]
        if c.length > 1e-9:
            m.col[i] = c.normalized()
    return m


def bonemap(src_arm, tgt_arm):
    """Resolve MAP against the actual bone names present on both rigs."""
    def bysuf(arm, suf):
        for b in arm.data.bones:
            if b.name.lower().endswith(suf.lower()):
                return b.name
        return None
    pairs = []
    for mx, qt in MAP.items():
        sn = bysuf(src_arm, mx)
        tn = bysuf(tgt_arm, qt)
        if sn and tn:
            pairs.append((sn, tn))
    return pairs


def depth(bone):
    d, b = 0, bone
    while b.parent:
        d += 1
        b = b.parent
    return d


def import_arm(path, gltf):
    pre = set(bpy.data.objects)
    (bpy.ops.import_scene.gltf if gltf else bpy.ops.import_scene.fbx)(filepath=path)
    new = [o for o in bpy.data.objects if o not in pre]
    return next(o for o in new if o.type == "ARMATURE"), new


def retarget(src_arm, tgt_arm, action_name):
    """Bake src_arm's current action onto tgt_arm as a new Action."""
    act = src_arm.animation_data.action
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    pairs = bonemap(src_arm, tgt_arm)

    # precompute rest world-rotations (constant) and rest world head positions
    Sw, Tw = src_arm.matrix_world, tgt_arm.matrix_world
    src_rest_rot, src_rest_head = {}, {}
    tgt_rest_rot, tgt_rest_head = {}, {}
    for sn, tn in pairs:
        sb, tb = src_arm.data.bones[sn], tgt_arm.data.bones[tn]
        src_rest_rot[sn] = norm3(Sw @ sb.matrix_local)
        src_rest_head[sn] = (Sw @ sb.matrix_local).translation.copy()
        tgt_rest_rot[tn] = norm3(Tw @ tb.matrix_local)
        tgt_rest_head[tn] = (Tw @ tb.matrix_local).translation.copy()

    # target bones root-to-leaf so a parent is posed before its children
    order = sorted(pairs, key=lambda p: depth(tgt_arm.data.bones[p[1]]))
    pelvis_tn = MAP["Hips"]

    # fresh action on the target
    tgt_arm.animation_data_clear()
    ad = tgt_arm.animation_data_create()
    new_act = bpy.data.actions.new(action_name)
    ad.action = new_act
    for _, tn in order:
        tgt_arm.pose.bones[tn].rotation_mode = "QUATERNION"

    vlu = bpy.context.view_layer.update
    scene = bpy.context.scene
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        for sn, tn in order:
            spb = src_arm.pose.bones[sn]
            tpb = tgt_arm.pose.bones[tn]
            sp_rot = norm3(Sw @ spb.matrix)
            delta = sp_rot @ src_rest_rot[sn].inverted()
            tpr = delta @ tgt_rest_rot[tn]                      # desired world 3x3
            if tn == pelvis_tn:
                sp_head = (Sw @ spb.matrix).translation
                head = tgt_rest_head[tn] + (sp_head - src_rest_head[sn])
            else:
                head = (Tw @ tpb.matrix).translation            # follow posed parent
            world = Matrix.Translation(head) @ tpr.to_4x4()
            tpb.matrix = Tw.inverted() @ world
            vlu()                                               # propagate to children
        for _, tn in order:
            tpb = tgt_arm.pose.bones[tn]
            tpb.keyframe_insert("rotation_quaternion", frame=f)
            if tn == pelvis_tn:
                tpb.keyframe_insert("location", frame=f)
    new_act.use_fake_user = True
    return new_act, f0, f1


def load_target():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tgt, tnew = import_arm(QUAT, True)
    tgt.name = "QuatTarget"
    return tgt, tnew


def do_one(path, tgt):
    stem = os.path.basename(path).replace(".fbx", "")
    name = RENAME.get(stem, stem.replace(" ", "_"))
    src, snew = import_arm(path, False)
    act, f0, f1 = retarget(src, tgt, name)
    # drop the source objects + its action so the file stays clean
    src_act = None
    for o in list(snew):
        bpy.data.objects.remove(o, do_unlink=True)
    print("  baked %-22s -> Action '%s'  (%d frames)" % (stem, name, f1 - f0 + 1))
    return act


def render_test(tgt, tnew, clip_stem):
    """Apply the just-baked action, jump to a representative frame, render a still."""
    act = tgt.animation_data.action
    mid = int(sum(act.frame_range) / 2)
    bpy.context.scene.frame_set(mid)
    # simple 3/4 camera + sun looking at the body
    cam_d = bpy.data.cameras.new("C"); cam = bpy.data.objects.new("C", cam_d)
    bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
    cam.location = (2.6, -2.6, 1.3); cam.rotation_euler = (math.radians(72), 0, math.radians(45))
    sun_d = bpy.data.lights.new("S", "SUN"); sun_d.energy = 4
    sun = bpy.data.objects.new("S", sun_d); bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = sc.render.resolution_y = 700
    out = os.path.join(ROOT, "renders", "retarget_%s.png" % clip_stem.replace(" ", "_"))
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("  verification still -> %s  (frame %d)" % (out, mid))


def main():
    tgt, tnew = load_target()
    if TEST:
        path = os.path.join(DIR, ONE + ".fbx")
        if not os.path.exists(path):
            print("TEST clip not found:", path); return
        print("RETARGET TEST:", ONE)
        do_one(path, tgt)
        render_test(tgt, tnew, ONE)
        return
    files = sorted(glob.glob(os.path.join(DIR, "*.fbx")))
    print("RETARGET ALL: %d clips -> %s" % (len(files), OUTLIB))
    kept = []
    for p in files:
        # each bake replaces tgt's action; collect the datablocks, they persist
        act = do_one(p, tgt)
        kept.append(act)
    tgt.animation_data_clear()
    bpy.ops.wm.save_as_mainfile(filepath=OUTLIB)
    print("saved %d actions to %s" % (len(kept), OUTLIB))


main()
