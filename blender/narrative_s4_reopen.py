"""S4 -- THE REOPEN / DAWN. Close "One Night" on the hero cell.

By the end of S3 the wash is done and the piston is parked flush (X=-STK). Eddy
hand-blocked S4's MOTION and CAMERA already in narrative.blend:
  * Piston/WiperSeals: an "Open" NLA track (f721-779, HOLD_FORWARD) sweeps the
    piston flush -> deployed (cavity OPEN) and holds it open to 840.
  * Camera: a hard cut at 721 to a new S4 framing, then a gentle settle to 840.

What S3 left held into S4 was the LOOK: the environment is still S3's black void
(NightFactor=1, night sky strength 0, exposure 0.5) and the hero shell is still
x-ray transparent. This script authors the DAWN look OVER those held frames --
the void warms to a pre-dawn sky, the shell resolves from x-ray back to SOLID,
and the sterile white service luminaire eases out as dawn takes over. We stay on
the ISOLATED hero cell (no environment un-dissolve) to match S3's treatment; the
"pull back to the wall" bookend was the rejected option.

LOOK only -- it does NOT touch motion or camera (those are Eddy's hand blocking).
All ramps read the value S3 held at S3_END and ease FROM it, so re-running is
idempotent-ish and the S2/S3 look before the cut is never disturbed.

Run:  /usr/bin/blender --background blender/narrative.blend \
          --python blender/narrative_s4_reopen.py
(rewrites narrative.blend in place; the pre-S4 state is committed in git.)
"""
import bpy
import math

NARR = "/home/eddy/Projects/HiveCell/blender/narrative.blend"

S3_END = 720        # last wash frame; piston parked flush, void, x-ray shell
S4_A = 721          # hard cut into S4 (matches the camera/piston blocking)
DAWN = 810          # dawn fully established; the last ~30 frames hold "ready"
END = 840

# --- tunables (aesthetic; hand-tune in Blender -- this is a scaffold) ---------
NIGHTFACTOR_DAWN = 0.25   # ease the night<->day sky mix toward day for pre-dawn
LUMINAIRE_DAWN = 6.0      # sterile service light eased down as dawn takes over
EXPOSURE_DAWN = 0.9       # gentle lift for the dawn reveal (S3 held 0.5)


# --- slotted-action fcurve access (Blender 5.2, matches narrative_link_clean) --
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


def val_at(act, match, frame):
    """Value the given fcurve (data_path contains `match`) holds at `frame`."""
    if not act:
        return None
    for fc in fcurves(act):
        if match in fc.data_path:
            return fc.evaluate(frame)
    return None


def ramp(inp, keys, ease="BEZIER"):
    """Key an input socket's default_value over (frame, value) pairs."""
    for f, v in keys:
        inp.default_value = v
        inp.keyframe_insert("default_value", frame=f)
    # set interpolation on the just-written keys where we can find them
    return


def node_anim(nt):
    if nt.animation_data is None:
        nt.animation_data_create()
    return nt


# --- 1. de-x-ray: the shell resolves from the S3 cutaway back to SOLID ---------
def resolve_shell():
    m = bpy.data.materials.get("cell_HeroShell_xray")
    if not m or not m.node_tree:
        print("  [skip] cell_HeroShell_xray missing")
        return
    nt = node_anim(m.node_tree)
    b = nt.nodes["Principled BSDF"]
    a0 = val_at(nt.animation_data.action, "Alpha", S3_END)
    if a0 is None:
        a0 = b.inputs["Alpha"].default_value
    # hold the S3 transparency to the cut, then resolve to solid, hold "ready"
    ramp(b.inputs["Alpha"], [
        (S3_END, a0), (S4_A, a0), (S4_A + 30, 1.0), (END, 1.0),
    ])
    print("  shell x-ray %.2f -> 1.0 (solid) by f%d" % (a0, S4_A + 30))


# --- 2. luminaire: the sterile white service light eases out for dawn ----------
def ease_luminaire():
    m = bpy.data.materials.get("cell_Luminaire")
    if not m or not m.node_tree:
        print("  [skip] cell_Luminaire missing")
        return
    nt = node_anim(m.node_tree)
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    src = None
    if out and out.inputs["Surface"].links:
        src = out.inputs["Surface"].links[0].from_node
    if src is None:
        src = nt.nodes.get("Emission") or nt.nodes["Principled BSDF"]
    skey = "Strength" if src.type == "EMISSION" else "Emission Strength"
    # the strength fcurve stores by socket INDEX (e.g. Emission inputs[1]) so its
    # data_path has no "Strength" text -- match the socket's own path, not the name.
    sock_path = src.inputs[skey].path_from_id("default_value")
    s0 = val_at(nt.animation_data.action, sock_path, S3_END)
    if s0 is None:
        s0 = val_at(nt.animation_data.action, "inputs[1]", S3_END)
    if s0 is None:
        s0 = src.inputs[skey].default_value
    ramp(src.inputs[skey], [
        (S3_END, s0), (DAWN, LUMINAIRE_DAWN), (END, LUMINAIRE_DAWN),
    ])
    print("  luminaire %.0f -> %.0f (dawn takes over) by f%d" % (s0, LUMINAIRE_DAWN, DAWN))


# --- 3. world: the black void warms to a pre-dawn sky --------------------------
def warm_world():
    w = bpy.context.scene.world
    if not w or not w.node_tree:
        print("  [skip] no world node tree")
        return
    nt = node_anim(w.node_tree)
    act = nt.animation_data.action
    nf = nt.nodes.get("NightFactor")
    if nf:
        f0 = val_at(act, 'NightFactor"].outputs[0]', S3_END)
        if f0 is None:
            f0 = nf.outputs[0].default_value
        ramp(nf.outputs[0], [
            (S3_END, f0), (S4_A, f0), (DAWN, NIGHTFACTOR_DAWN), (END, NIGHTFACTOR_DAWN),
        ])
        print("  NightFactor %.2f -> %.2f (night gives way to dawn)" % (f0, NIGHTFACTOR_DAWN))
    # the night sky was dimmed to 0 for the S3 void; lift it back so a sky exists
    # to warm (the sun does the warmth; keeping the mix low reads pre-dawn).
    ns = nt.nodes.get("Background.001")
    if ns:
        s0 = val_at(act, 'Background.001"].inputs[1]', S3_END)
        if s0 is None:
            s0 = ns.inputs[1].default_value
        ramp(ns.inputs[1], [
            (S3_END, s0), (S4_A, s0), (DAWN, 1.4), (END, 1.4),
        ])
        print("  night-sky strength %.2f -> 1.4 (void -> sky)" % s0)


# --- 4. sun: the cool S2/S3 moon becomes a low, warm dawn sun ------------------
def dawn_sun():
    sun = bpy.data.objects.get("Sun")
    if not sun or sun.type != "LIGHT":
        print("  [skip] no Sun")
        return
    # read what S3 held, then rise + warm it. low grazing angle = dawn.
    e0 = sun.data.energy
    dawn = (2.6, (1.0, 0.80, 0.62),
            (math.radians(-8), math.radians(70), math.radians(6)))   # low, warm, side
    sun.data.keyframe_insert("energy", frame=S3_END)
    sun.data.keyframe_insert("color", frame=S3_END)
    sun.keyframe_insert("rotation_euler", frame=S3_END)
    sun.data.energy, sun.data.color, sun.rotation_euler = dawn
    for fr in (DAWN, END):
        sun.data.keyframe_insert("energy", frame=fr)
        sun.data.keyframe_insert("color", frame=fr)
        sun.keyframe_insert("rotation_euler", frame=fr)
    print("  sun -> low warm dawn (energy %.1f -> %.1f)" % (e0, dawn[0]))


# --- 5. exposure: gentle lift for the dawn reveal ------------------------------
def lift_exposure():
    sc = bpy.context.scene
    v = sc.view_settings
    e0 = 0.5
    if sc.animation_data and sc.animation_data.action:
        got = val_at(sc.animation_data.action, "exposure", S3_END)
        if got is not None:
            e0 = got
    for fr, val in [(S3_END, e0), (S4_A, e0), (DAWN, EXPOSURE_DAWN), (END, EXPOSURE_DAWN)]:
        v.exposure = val
        try:
            v.keyframe_insert("exposure", frame=fr)
        except (TypeError, RuntimeError):
            pass
    print("  exposure %.2f -> %.2f" % (e0, EXPOSURE_DAWN))


# --- run ----------------------------------------------------------------------
bpy.ops.wm.open_mainfile(filepath=NARR)
print("S4 dawn look -> narrative.blend (f%d..%d):" % (S4_A, END))
resolve_shell()
ease_luminaire()
warm_world()
dawn_sun()
lift_exposure()
bpy.context.scene.frame_set(DAWN)   # a dawn frame for the saved viewport
bpy.ops.wm.save_as_mainfile(filepath=NARR)
print("SAVED S4 dawn look.")
