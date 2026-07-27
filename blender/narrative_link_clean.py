"""Wire narrative.blend's S3 hero cell to the CANONICAL cleaning animation.

Architecture (Eddy's call): hivecell.blend OWNS how the machine moves -- the
open/close + cleaning cycle is authored once in build_scene.py and baked into
hivecell.blend as the HC_*_Clean actions. narrative.blend is the film; it does NOT
re-key the mechanism. This script HARD-LINKS those actions (read-only) and plays
them on the S3 hero cell via NLA strips placed at the S3 cut (frame 553), while the
per-shot LOOK (x-ray shell, killing the neon, warm interior, spray glow) stays local
in narrative -- motion is canonical, shading is per-shot (like a real anim/lighting
split).

Dependency: hivecell.blend must be rebuilt (scripts/export_blender.py +
blender/build_scene.py) BEFORE this runs, and re-run this whenever the cleaning
choreography changes. hivecell.blend is gitignored/regenerable.

Run:  /usr/bin/blender --background blender/narrative.blend \
          --python blender/narrative_link_clean.py
(opens + rewrites narrative.blend in place; back it up first).
"""
import bpy
import os

ROOT = "/home/eddy/Projects/HiveCell"
HIVE = os.path.join(ROOT, "blender", "hivecell.blend")
MODELS = os.path.join(ROOT, "blender", "models")
NARR = os.path.join(ROOT, "blender", "narrative.blend")

CUT = 553           # S2->S3 cut: the clean cycle starts here (piston already flush)
CLEAN_LEN = 168     # HC_*_Clean action length (frames 1..168 @ 24fps)
END = CUT + CLEAN_LEN - 1   # 720


# --- slotted-action fcurve access (Blender 5.2) ------------------------------
def fcurves(act):
    fcs = []
    try:
        for lay in act.layers:
            for st in lay.strips:
                for cb in st.channelbags:
                    fcs.extend(cb.fcurves)
    except Exception:
        pass
    if not fcs:
        fcs = list(act.fcurves)
    return fcs


def open_narr():
    bpy.ops.wm.open_mainfile(filepath=NARR)


# --- guard against double-application ----------------------------------------
def already_wired():
    p = bpy.data.objects.get("Piston")
    if p and p.animation_data:
        return any(t.name == "Clean" for t in p.animation_data.nla_tracks)
    return False


# --- link the canonical actions from hivecell.blend --------------------------
def link_clean_actions():
    want = ["HC_Piston_Clean", "HC_WiperSeals_Clean", "HC_Squeegee_Clean"]
    have = {a.name: a for a in bpy.data.actions if a.library and a.name in want}
    missing = [n for n in want if n not in have]
    if missing:
        with bpy.data.libraries.load(HIVE, link=True) as (src, dst):
            dst.actions = [n for n in missing if n in src.actions]
        for a in bpy.data.actions:
            if a.library and a.name in want:
                have[a.name] = a
    for n in want:
        assert n in have, "linked action missing: " + n
    return have


# --- import cleaning geometry (local mesh; native CAD frame aligns w/ hero) ---
def import_obj(part, mat):
    o = bpy.data.objects.get(part)
    if o:
        return o
    bpy.ops.wm.obj_import(filepath=os.path.join(MODELS, part + ".obj"),
                          up_axis="Z", forward_axis="Y")
    objs = list(bpy.context.selected_objects)
    o = objs[0]
    o.name = part
    for x in objs[1:]:
        x.name = part + "_x"
    o.data.materials.clear()
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def mat_pbr(name, base, metallic, rough, emit=None, emit_str=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if emit is not None:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = emit_str
    return m


# --- NLA plumbing ------------------------------------------------------------
def strip(track, name, start, action, a0, a1, blend, extrap):
    s = track.strips.new(name, int(start), action)
    s.action_frame_start = a0
    s.action_frame_end = a1
    s.frame_start = start
    s.frame_end = start + (a1 - a0)
    s.blend_type = blend
    s.extrapolation = extrap
    return s


def rewire_local(obj, clean_action):
    """obj has a hand-keyed S1/S2 action: trim it to < CUT, drop it to a base NLA
    track (holds), and add the linked clean action on top from CUT (REPLACE)."""
    ad = obj.animation_data
    local = ad.action if ad else None
    frs = []
    if local:
        for fc in fcurves(local):
            kps = fc.keyframe_points
            for i in range(len(kps) - 1, -1, -1):   # reverse: wrappers stay valid
                if kps[i].co.x >= CUT:
                    kps.remove(kps[i])
            fc.update()
            frs += [kp.co.x for kp in fc.keyframe_points]
    if ad is None:
        ad = obj.animation_data_create()
    ad.action = None
    ad.use_nla = True
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
    if local and frs:
        t0 = ad.nla_tracks.new()
        t0.name = "S1_S2"
        strip(t0, "S1_S2", int(min(frs)), local, min(frs), max(frs), "REPLACE", "HOLD")
    t1 = ad.nla_tracks.new()
    t1.name = "Clean"
    strip(t1, "Clean", CUT, clean_action, 1, CLEAN_LEN, "REPLACE", "NOTHING")


def rewire_new(obj, clean_action):
    ad = obj.animation_data or obj.animation_data_create()
    ad.action = None
    ad.use_nla = True
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
    t1 = ad.nla_tracks.new()
    t1.name = "Clean"
    strip(t1, "Clean", CUT, clean_action, 1, CLEAN_LEN, "REPLACE", "NOTHING")


def key_hide(obj):
    """Hidden before the cut, visible for S3 (constant-interp)."""
    for f, v in [(1, True), (CUT - 1, True), (CUT, False), (END, False)]:
        obj.hide_render = v
        obj.hide_viewport = v
        obj.keyframe_insert("hide_render", frame=f)
        obj.keyframe_insert("hide_viewport", frame=f)
    if obj.animation_data and obj.animation_data.action:
        for fc in fcurves(obj.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


# --- per-shot LOOK -----------------------------------------------------------
def key_scalar(node_tree, node_name, input_key, keys):
    nt = node_tree
    if nt.animation_data is None:
        nt.animation_data_create()
    inp = nt.nodes[node_name].inputs[input_key]
    for f, v in keys:
        inp.default_value = v
        inp.keyframe_insert("default_value", frame=f)


def kill_neon():
    """Zero the S3 piston 'pop' emission -- the invented neon glow is gone; the
    piston now reads as a real metal part lit by the interior luminaire."""
    m = bpy.data.materials.get("cell_HeroPiston_pop")
    if not m or not m.node_tree.animation_data or not m.node_tree.animation_data.action:
        return
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Strength"].default_value = 0.0
    for fc in fcurves(m.node_tree.animation_data.action):
        if "Emission Strength" in fc.data_path or "inputs[29]" in fc.data_path:
            for kp in fc.keyframe_points:
                kp.co.y = 0.0
                kp.handle_left.y = 0.0
                kp.handle_right.y = 0.0
            fc.update()


def warm_luminaire():
    """The ADR-0014 crown luminaire is the interior source during the wash: it
    warms up as the cell closes, rakes the chamber while the squeegee works, then
    eases as the cell reopens. Preserve the S1/S2 level before the cut."""
    m = bpy.data.materials.get("cell_Luminaire")
    nt = m.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    src = None
    if out and out.inputs["Surface"].links:
        src = out.inputs["Surface"].links[0].from_node
    if src is None:
        src = nt.nodes.get("Emission") or nt.nodes["Principled BSDF"]
    skey = "Strength" if src.type == "EMISSION" else "Emission Strength"
    base = src.inputs[skey].default_value or 3.0
    if src.type == "EMISSION":
        src.inputs["Color"].default_value = (1.0, 0.66, 0.32, 1.0)   # warm amber
    key_scalar(nt, src.name, skey, [
        (CUT - 14, base),            # preserve S1/S2 level up to the cut
        (CUT + 12, base * 3.0 + 6),  # warm up as the wash begins
        (CUT + 105, base * 3.0 + 6), # hold through the squeegee passes
        (CUT + 140, base + 2),       # ease as the cell reopens
        (END, base + 2),
    ])


def spray_fx(rings):
    """Cheap watery shimmer on the two spray rings during the wash window."""
    for o in rings:
        m = o.data.materials[0]
        nt = m.node_tree
        key_scalar(nt, "Principled BSDF", "Emission Strength", [
            (CUT, 0.0), (CUT + 8, 7.0), (CUT + 32, 2.0), (CUT + 57, 7.0),
            (CUT + 82, 2.0), (CUT + 100, 0.0), (END, 0.0)])


def hold_xray():
    m = bpy.data.materials.get("cell_HeroShell_xray")
    if not m or not m.node_tree.animation_data:
        return
    a = m.node_tree.animation_data.action
    if not a:
        return
    for fc in fcurves(a):
        if "inputs[4]" in fc.data_path or fc.data_path.endswith("Alpha.default_value"):
            last = max(fc.keyframe_points, key=lambda k: k.co.x)
            m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = last.co.y
            m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].keyframe_insert(
                "default_value", frame=END)


# --- run ---------------------------------------------------------------------
open_narr()
if already_wired():
    print("ABORT: narrative.blend already wired to the clean cycle "
          "(restore blender/narrative_pre_s3rework.blend to redo).")
else:
    acts = link_clean_actions()
    mat_sq = mat_pbr("cell_Squeegee", (0.12, 0.13, 0.15), 0.4, 0.45)
    mat_spray = mat_pbr("cell_Spray", (0.7, 0.85, 0.95), 0.0, 0.2,
                        emit=(0.75, 0.9, 1.0), emit_str=0.0)
    sq = import_obj("ServiceSqueegee", mat_sq)
    sr_f = import_obj("SprayRing", mat_spray)
    sr_d = import_obj("ServiceSprayRing", mat_spray)

    # MOTION (canonical, linked from hivecell.blend)
    rewire_local(bpy.data.objects["Piston"], acts["HC_Piston_Clean"])
    rewire_local(bpy.data.objects["WiperSeals"], acts["HC_WiperSeals_Clean"])
    rewire_new(sq, acts["HC_Squeegee_Clean"])
    for o in (sq, sr_f, sr_d):
        key_hide(o)

    # LOOK (per-shot, local)
    kill_neon()
    warm_luminaire()
    spray_fx([sr_f, sr_d])
    hold_xray()

    bpy.context.scene.frame_set(CUT + 40)   # a wash frame, for the saved viewport
    bpy.ops.wm.save_as_mainfile(filepath=NARR)
    print("WIRED narrative.blend S3 -> canonical clean cycle. squeegee stow X=%.2f"
          % sq.matrix_world.translation.x)
