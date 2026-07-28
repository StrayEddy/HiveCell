"""Fix the S2 guest wake: a REAL lie->sit motion before he stands & leaves.

The old wake crossfaded Lay_Idle straight into a seated idle (Sit_Sill_Loop),
which morphed the body from lying to sitting -- it read badly. Mixamo's free tier
has no "sit up from lying" clip, but "Lying Down" (Lie_Down) IS one played
BACKWARDS (seated -> supine, reversed = supine -> seated). Because retarget_mixamo.py
bakes a key EVERY frame, reversing is exact: keep each fcurve's frame positions and
reverse its value sequence.

Three gotchas this script handles (see [[mixamo-retarget-pipeline]]):
  1. GROUNDING. The retarget bakes a per-clip pelvis world-translation delta, so
     absolute pelvis Z is NOT comparable across clips. The raw reversed clip made
     the body dip below the cell floor then pop up. Fix: overwrite the sit-up's
     pelvis-Z channel with a monotonic ramp from Lay_Idle's supine Z to
     Sit_To_Stand's seated-start Z (both are values the guest-root Z was already
     tuned around), so the body stays planted. Leave the root travel alone.
  2. QUATERNION BLEND FLIP. Walk_Loop's calf quaternion is near-antipodal to the
     stand's, so ANY partial NLA blend flips the leg for ~1 frame (a violent
     glitch). Walk_Loop is shared (can't renegate it) -> HARD CUT: Walk blend_in=0,
     starting on its both-feet-planted opening frame right after the stand.
  3. T-POSE FLASH. Sit_To_Stand shipped with blend_out=8; with no track beneath,
     the fade drifted the bones toward rest pose (arms out) for a few frames. Zero
     the blend_out and hold the stand (HOLD_FORWARD) to the cut.

Idempotent: rebuilds Sit_Up_FromLie + the SitUp track each run. Root travel and the
existing Sit_To_Stand / Walk_Loop / Idle_Breathe strips are reused (only re-timed).

Run:  /usr/bin/blender -b blender/narrative.blend --factory-startup \
          -P blender/narrative_guest_sit.py     (rewrites narrative.blend in place)
"""
import bpy

NARR = "/home/eddy/Projects/HiveCell/blender/narrative.blend"
LIB = "/home/eddy/Projects/HiveCell/assets/quaternius/UAL2_Mixamo.blend"

SIT_START = 372          # guest starts sitting up here (Lay_Idle held until now)
SPAN = 44                # sit-up duration in frames (Lie_Down's 173 compressed)
STAND_START = SIT_START + SPAN - 4   # 412: Sit_To_Stand takes over as the sit settles
WALK_START = 438         # walk begins right after the stand completes (hard cut)


def fcs(act):
    out = []
    try:
        for lay in act.layers:
            for st in lay.strips:
                for cb in st.channelbags:
                    out.extend(cb.fcurves)
    except Exception:
        pass
    return out or list(act.fcurves)


def pelvis_z_fcurve(act):
    for fc in fcs(act):
        if "pelvis" in fc.data_path and fc.data_path.endswith("location") and fc.array_index == 2:
            return fc
    return None


bpy.ops.wm.open_mainfile(filepath=NARR)

# --- 1. get Lie_Down, build the reversed sit-up action -----------------------
lie = bpy.data.actions.get("Lie_Down")
if not lie:
    with bpy.data.libraries.load(LIB, link=False) as (src, dst):
        dst.actions = [n for n in src.actions if n == "Lie_Down"]
    lie = bpy.data.actions.get("Lie_Down")

old = bpy.data.actions.get("Sit_Up_FromLie")
if old:
    bpy.data.actions.remove(old)
rev = lie.copy()
rev.name = "Sit_Up_FromLie"
rev.use_fake_user = True
for fc in fcs(rev):
    kps = fc.keyframe_points
    ys = [k.co.y for k in kps]
    n = len(ys)
    for i, k in enumerate(kps):
        k.co.y = ys[n - 1 - i]          # dense per-frame keys => exact time reverse
        k.interpolation = "LINEAR"
    fc.update()

# grounding: replace pelvis Z with a monotonic supine->seated ramp (no dip/pop)
zL = pelvis_z_fcurve(bpy.data.actions["Lay_Idle"]).evaluate(1)
zS = pelvis_z_fcurve(bpy.data.actions["Sit_To_Stand"]).evaluate(1)
zfc = pelvis_z_fcurve(rev)
kps = zfc.keyframe_points
for i in range(len(kps) - 1, -1, -1):
    kps.remove(kps[i])
kps.insert(1, zL).interpolation = "BEZIER"
kps.insert(173, zS).interpolation = "BEZIER"
zfc.update()
print("Sit_Up_FromLie built; pelvis Z ramp %.3f -> %.3f" % (zL, zS))

# --- 2. rewire the guest wake NLA --------------------------------------------
rig = bpy.data.objects["GuestRig"]
ad = rig.animation_data


def find(name):
    for t in ad.nla_tracks:
        for s in t.strips:
            if s.name == name:
                return t, s
    return None, None


for tr in list(ad.nla_tracks):          # idempotent: drop a prior SitUp track
    if tr.name == "SitUp":
        ad.nla_tracks.remove(tr)
_, sill = find("Sit_Sill_Loop_401")     # remove the old lie->sit crossfade
if sill:
    for t in ad.nla_tracks:
        if sill in list(t.strips):
            t.strips.remove(sill)
            break

up = ad.nla_tracks.new()
up.name = "SitUp"
ns = up.strips.new("Sit_Up_FromLie", SIT_START, rev)
try:
    ns.action_slot = rev.slots[0]
except Exception:
    pass
ns.action_frame_start = 1
ns.action_frame_end = 173
ns.scale = float(SPAN) / 172.0          # compress the reversed clip into SPAN frames
ns.frame_start = SIT_START
ns.blend_type = "REPLACE"
ns.blend_in = 8
ns.blend_out = 0
ns.extrapolation = "NOTHING"

_, sts = find("Sit_To_Stand_420")
if sts:
    sts.frame_start = STAND_START
    sts.blend_in = 6
    sts.blend_out = 0                   # no fade -> no T-pose drift to rest
    sts.extrapolation = "HOLD_FORWARD"  # hold the stand to the walk cut

_, walk = find("Walk_Loop_438")
if walk:
    walk.frame_start = WALK_START
    walk.blend_in = 0                   # HARD CUT (avoids the calf quaternion flip)

bpy.ops.wm.save_as_mainfile(filepath=NARR)
print("SAVED guest sit-fix: sit-up f%d(+%d) -> stand f%d -> walk f%d"
      % (SIT_START, SPAN, STAND_START, WALK_START))
