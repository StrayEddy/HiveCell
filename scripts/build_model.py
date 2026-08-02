"""Build the HiveCell parametric model from scratch (THE SOURCE OF TRUTH).

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/build_model.py

Regenerates cad/HiveCell.FCStd. Author design changes HERE (edit the PARAMS
table or the geometry functions), never by hand in the GUI -- GUI edits get
overwritten on the next run. The GUI is a viewer, not a pencil.

Coordinate convention (fixed for the whole project):
  origin = center of the public wall opening, on the capsule centerline
  +X = depth into the wall (the motion axis; piston travels +X to close)
  +Z = up,  +Y = width.  Units = millimeters.

Living space = a rounded-rectangular capsule (Japanese capsule-hotel style):
a box whose four long edges (running along +X) are rounded. The flat back
face is the piston that pushes in/out and ends flush with the exterior wall.
"""
import FreeCAD as App
import Part
import Sketcher

OUT = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"

# --- Master parameters: (alias, value/formula, comment) ---------------------
# Envelope numbers come from human anthropometrics (P95 = 95th percentile,
# a size only 5% of people exceed -> we size clearances to the big user).
# 'structural' numbers are placeholders until load analysis (clearly marked).
PARAMS = [
    ("statureP95",      "1880 mm",                       "P95 male stature ~= lying length"),
    ("lengthClearance", "320 mm",                        "foot + head/pillow gap (tuned so cavityLength=2200)"),
    ("cavityLength",    "=statureP95 + lengthClearance", "usable interior length (derived)"),
    ("cavityWidth",     "1000 mm",                       "interior width Y (capsule-hotel style)"),
    ("interiorHeight",  "1100 mm",                       "interior height Z, floor to crown"),
    ("cornerRadius",    "125 mm",                        "radius of the 4 rounded long corners"),
    ("shoulderP95",     "530 mm",                        "P95 shoulder breadth (floor must exceed this)"),
    ("floorWidth",      "=cavityWidth - 2 * cornerRadius", "flat floor width (derived); > shoulderP95"),
    ("wallThickness",   "6 mm",                          "STRUCTURAL PLACEHOLDER - TBD by analysis"),
    ("stroke",          "=cavityLength",                 "piston travel, deployed -> flush (derived)"),
    ("runningClearance","3 mm",                          "piston-to-bore gap per side (seals bridge it)"),
    ("sealLipThickness","8 mm",                          "axial thickness of each wiper lip (SF3)"),
    ("sealLipCount",    "2",                             "wiper lips per piston: front + rear (gap fill + hygiene scrape)"),
    ("sealInterference","0.8 mm",                        "lip compression onto the bore (contact; used for drag)"),
    ("pistonLength",    "300 mm",                        "piston depth along X"),
    ("squeegeeThickness","50 mm",                        "traveling service squeegee thickness along X [ADR-0019]"),
    ("squeegeeStow",    "80 mm",                         "stow bay behind the deployed piston (extends the barrel) for the service squeegee [ADR-0019]"),
    ("barrelLength",    "=cavityLength + pistonLength + squeegeeStow",  "sleeve: houses the deployed piston + the stowed service squeegee (ADR-0019)"),
    ("actuatorGap",     "60 mm",                         "gap: deployed piston rear to magazine front"),
    ("chainWidth",      "60 mm",                         "rigid-chain cross-section width Y (representative)"),
    ("chainHeight",     "60 mm",                         "rigid-chain cross-section height Z (representative)"),
    ("squeegeeChainOffsetY","430 mm",                    "squeegee-drive chain lane, offset +Y INSIDE the sealed bore (no wall slot); shares the chamber with the central piston chain by temporal exclusivity [ADR-0021]"),
    ("magazineDepth",   "300 mm",                        "chain magazine/drive extent along X (compact)"),
    ("magazineSize",    "650 mm",                        "chain magazine Y and Z (holds the coiled chain)"),
    ("luminaireWidth",  "140 mm",                        "interior light strip width Y (top-centre, flush crown) [ADR-0014]"),
    ("luminaireDepth",  "4 mm",                          "diffuser recess into the crown wall (< wallThickness)"),
    ("luminaireEndMargin", "150 mm",                     "strip setback from each cavity end along X"),
    ("luminaireLength", "=cavityLength - 2 * luminaireEndMargin", "lit length along X (derived)"),
    # --- ADR-0015 cleaning subsystem: SPACE CLAIM (representative, not selected) ---
    ("sprayRingRadial",  "50 mm",  "spray-ring radial thickness, hugging the barrel [ADR-0015]"),
    ("sprayRingDepth",   "80 mm",  "spray-ring extent along X"),
    ("sprayRingSetback", "=pistonLength + 40 mm", "front ring: just PAST the closed piston so it sprays the sealed chamber [ADR-0018]"),
    ("serviceRingSetback","60 mm", "service ring setback BEHIND the deployed piston face (X=cavityLength+this); never in the occupant space [ADR-0018]"),
    ("serviceRingDepth", "80 mm",  "service spray-ring extent along X"),
    ("sillHeight",          "500 mm", "mouth sill height above the pavement [ADR-0013]"),
    ("trenchWidth",         "300 mm", "pavement trench-drain width along X, in front of the mouth [ADR-0016]"),
    ("trenchDepth",         "120 mm", "trench-drain channel depth Z"),
    ("trenchMargin",        "120 mm", "trench length beyond the cavity width on each side (Y)"),
    ("sumpWidth",           "140 mm", "back wash-media sump width along X, hidden under the deployed piston [ADR-0017]"),
    ("sumpLength",          "320 mm", "sump length across Y"),
    ("sumpDepth",           "120 mm", "sump pit depth below the bore floor -> sewer"),
    ("servicePlantSize",    "900 mm", "back-of-house plant Y/Z envelope around the actuator (heater/steam, disinfectant reservoir + doser, dry-air blower, pump) [ADR-0015]"),
]


def build_parameters(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "Parameters")
    sheet.Label = "Parameters"
    for row, (alias, value, comment) in enumerate(PARAMS, start=1):
        sheet.set(f"A{row}", alias)
        sheet.set(f"B{row}", value)
        sheet.setAlias(f"B{row}", alias)
        sheet.set(f"C{row}", comment)
    doc.recompute()
    return sheet


def build_cavity_reference(doc, sheet):
    """CavityReference: the human keep-out volume -- the sacred empty space no
    real part may intrude on. A rounded-rectangular capsule extruded along +X,
    from X=0 (wall plane / opening) to X=cavityLength (deep end / piston)."""
    body = doc.addObject("PartDesign::Body", "CavityReference")
    doc.recompute()

    # Seed sizes for the sketch geometry; live values come from expressions.
    w = sheet.cavityWidth.Value       # global Y  -> sketch-local Y
    h = sheet.interiorHeight.Value    # global Z  -> sketch-local X
    hw, hh = w / 2.0, h / 2.0

    sk = body.newObject("Sketcher::SketchObject", "CavitySketch")
    # Sketch on the global YZ plane (normal = +X) so the Pad extrudes along the
    # motion axis. Rotate sketch-local +Z onto global +X (90 deg about Y).
    sk.Placement = App.Placement(App.Vector(0, 0, 0),
                                 App.Rotation(App.Vector(0, 1, 0), 90))

    V = App.Vector
    # Rectangle as 4 line segments (local: X = height axis, Y = width axis).
    sk.addGeometry(Part.LineSegment(V(-hh, -hw, 0), V(hh, -hw, 0)), False)  # 0 bottom
    sk.addGeometry(Part.LineSegment(V(hh, -hw, 0), V(hh, hw, 0)), False)   # 1 right
    sk.addGeometry(Part.LineSegment(V(hh, hw, 0), V(-hh, hw, 0)), False)   # 2 top
    sk.addGeometry(Part.LineSegment(V(-hh, hw, 0), V(-hh, -hw, 0)), False)  # 3 left

    C = Sketcher.Constraint
    sk.addConstraint(C("Coincident", 0, 2, 1, 1))
    sk.addConstraint(C("Coincident", 1, 2, 2, 1))
    sk.addConstraint(C("Coincident", 2, 2, 3, 1))
    sk.addConstraint(C("Coincident", 3, 2, 0, 1))
    sk.addConstraint(C("Horizontal", 0))
    sk.addConstraint(C("Horizontal", 2))
    sk.addConstraint(C("Vertical", 1))
    sk.addConstraint(C("Vertical", 3))
    sk.addConstraint(C("Symmetric", 0, 1, 2, 1, -1, 1))  # center on origin
    ch = sk.addConstraint(C("DistanceX", 0, 1, 0, 2, h))  # height (local X span)
    cw = sk.addConstraint(C("DistanceY", 1, 1, 1, 2, w))  # width  (local Y span)
    sk.setExpression(f"Constraints[{ch}]", "Parameters.interiorHeight")
    sk.setExpression(f"Constraints[{cw}]", "Parameters.cavityWidth")
    doc.recompute()

    pad = body.newObject("PartDesign::Pad", "CavitySolid")
    pad.Profile = sk
    pad.Length = sheet.cavityLength.Value
    pad.setExpression("Length", "Parameters.cavityLength")
    sk.Visibility = False
    doc.recompute()

    # Round only the 4 edges running along X (the capsule's long corners).
    names = []
    for i, e in enumerate(pad.Shape.Edges):
        vs = e.Vertexes
        if len(vs) == 2:
            d = vs[1].Point.sub(vs[0].Point)
            if abs(d.x) > 1e-6 and abs(d.y) < 1e-6 and abs(d.z) < 1e-6:
                names.append(f"Edge{i + 1}")
    fillet = body.newObject("PartDesign::Fillet", "CavityFillet")
    fillet.Base = (pad, names)
    fillet.Radius = sheet.cornerRadius.Value
    fillet.setExpression("Radius", "Parameters.cornerRadius")
    doc.recompute()
    return body, fillet


def rounded_box_shape(width, height, length, radius, x0=0.0):
    """A solid rounded-rectangular prism: box centered on the X axis in Y/Z,
    spanning x0..x0+length, with the 4 edges along X filleted to `radius`."""
    box = Part.makeBox(length, width, height, App.Vector(x0, -width / 2.0, -height / 2.0))
    long_edges = []
    for e in box.Edges:
        vs = e.Vertexes
        if len(vs) == 2:
            d = vs[1].Point.sub(vs[0].Point)
            if abs(d.x) > 1e-6 and abs(d.y) < 1e-6 and abs(d.z) < 1e-6:
                long_edges.append(e)
    if radius > 0 and long_edges:
        return box.makeFillet(radius, long_edges)
    return box


def build_capsule_shell(doc, sheet):
    """CapsuleShell: the fixed barrel the occupant lies in and the piston slides
    through -- a rounded-rectangular sleeve of uniform wallThickness, open at
    BOTH ends (front = public opening / piston seal; back = service side). The
    flat back wall the occupant sees is the piston (a later part), not this shell."""
    w = sheet.cavityWidth.Value
    h = sheet.interiorHeight.Value
    r = sheet.cornerRadius.Value
    t = sheet.wallThickness.Value
    L = sheet.barrelLength.Value

    # Inner surface == the keep-out envelope. Shell OUTWARD by t so we never
    # steal from the sleeper's space; outer corner R = inner R + t (uniform wall).
    outer = rounded_box_shape(w + 2 * t, h + 2 * t, L, r + t, x0=0.0)
    inner = rounded_box_shape(w, h, L + 2.0, r, x0=-1.0)  # overhang => clean through-cut
    shell = doc.addObject("Part::Feature", "CapsuleShell")
    shell.Shape = outer.cut(inner)
    doc.recompute()
    return shell


def build_piston(doc, sheet):
    """Piston: the single moving part -- a rounded-rectangular plug riding in the
    bore with `runningClearance` per side (seals bridge the gap, added later). Its
    flat front face is the occupant's back wall (deployed) and the flush exterior
    wall (closed). Modeled as a solid plug at the DEPLOYED position (front face at
    X=cavityLength); lightweighting (ribs/shelled face) comes later."""
    w = sheet.cavityWidth.Value
    h = sheet.interiorHeight.Value
    r = sheet.cornerRadius.Value
    c = sheet.runningClearance.Value
    pl = sheet.pistonLength.Value
    front = sheet.cavityLength.Value  # deployed: front face at the deep end

    piston = doc.addObject("Part::Feature", "Piston")
    piston.Shape = rounded_box_shape(w - 2 * c, h - 2 * c, pl, r - c, x0=front)
    doc.recompute()
    return piston


def build_wiper_seals(doc, sheet):
    """WiperSeals (SF3): compliant lip rings on the piston perimeter that fill the
    runningClearance gap so there is NO open moving 3 mm shear line (hazard H2).
    Two lips (front + rear) also scrape the bore for hygiene. Modeled here as the
    gap-filling ring geometry; the lips are elastomer/brush and COMPLIANT -- a
    finger at the gap deflects the lip instead of being sheared. The rings ride
    with the piston (shown at the DEPLOYED pose, like the piston)."""
    w = sheet.cavityWidth.Value
    h = sheet.interiorHeight.Value
    r = sheet.cornerRadius.Value
    c = sheet.runningClearance.Value
    pl = sheet.pistonLength.Value
    lip = sheet.sealLipThickness.Value
    front = sheet.cavityLength.Value          # deployed piston front face
    back = front + pl                          # piston rear

    def ring(x0):
        # Fill the annulus: outer = bore inner surface, inner = piston outer surface.
        outer = rounded_box_shape(w, h, lip, r, x0=x0)
        inner = rounded_box_shape(w - 2 * c, h - 2 * c, lip + 2.0, r - c, x0=x0 - 1.0)
        return outer.cut(inner)

    front_ring = ring(front)                   # occupant-facing edge
    rear_ring = ring(back - lip)               # service-side edge
    seals = doc.addObject("Part::Feature", "WiperSeals")
    seals.Shape = Part.makeCompound([front_ring, rear_ring])
    doc.recompute()
    return seals


def build_chain_actuator(doc, sheet):
    """Rigid-chain ('zip-chain') actuator. A special chain whose links lock straight
    to PUSH the piston but bend to coil into a compact magazine, so there is NO long
    retract tube -- keeping install depth shallow. The exposed rigid column genuinely
    changes length as chain feeds from / returns to the coil (total length conserved
    in the magazine), which is physically correct (unlike a solid rod). Guidance:
    the non-circular bore stops rotation and supports the piston at the front.
    ChainMagazine is fixed; ChainColumn is shown here at the DEPLOYED pose (short)."""
    bl = sheet.barrelLength.Value
    gap = sheet.actuatorGap.Value
    cw = sheet.chainWidth.Value
    ch = sheet.chainHeight.Value
    md = sheet.magazineDepth.Value
    ms = sheet.magazineSize.Value
    mag_front = bl + gap

    magazine = doc.addObject("Part::Feature", "ChainMagazine")
    magazine.Shape = Part.makeBox(md, ms, ms, App.Vector(mag_front, -ms / 2.0, -ms / 2.0))
    # exposed rigid chain at deployed pose: piston rear -> magazine front (short)
    column = doc.addObject("Part::Feature", "ChainColumn")
    column.Shape = Part.makeBox(gap, cw, ch, App.Vector(bl, -cw / 2.0, -ch / 2.0))
    doc.recompute()
    return magazine, column


def build_luminaire(doc, sheet):
    """Luminaire (ADR-0014): the interior light + status strip. A warm, blue-depleted
    diffuser recessed FLUSH into the crown (top) of the FIXED barrel, running along the
    bore. Flush with the bore ceiling so the piston's top wiper cleans it every sweep and
    it adds no gap (SF3); seated within the wall thickness so it never intrudes on the
    keep-out cavity. Top-mounted so a lying occupant / bedding can't cover it. It carries
    both the warm night-glow (sleep-safe) and the state colour (green/amber/red)."""
    w = sheet.luminaireWidth.Value
    d = sheet.luminaireDepth.Value
    L = sheet.luminaireLength.Value
    x0 = sheet.luminaireEndMargin.Value
    z0 = sheet.interiorHeight.Value / 2.0          # inner crown = bore ceiling (flush)
    lum = doc.addObject("Part::Feature", "Luminaire")
    lum.Shape = Part.makeBox(L, w, d, App.Vector(x0, -w / 2.0, z0))
    doc.recompute()
    return lum


def build_cleaning(doc, sheet):
    """ADR-0015 / 0016 / 0017 cleaning subsystem -- SPACE CLAIM only (representative
    volumes, not selected components -- like the actuator geometry). The cell PUSHES
    everything OUT the mouth and traps nothing; the service side stays sealed. Motion-
    driven 'wash-in-transit'. Drainage is SPLIT: gross SOLIDS ride the closing sweep out
    the mouth to a flush pavement grate; the WASH MEDIA (hot water + detergent +
    disinfectant) drains INTERNALLY to a back sump -> sewer, so hot chemical water never
    sheets across the street. No cleaning hardware on the public face (priority #1).
      SprayRing     front nozzle ring hugging the barrel just PAST the closed piston, so it
                    sprays the sealed chamber's front + rinses the piston face in transit
                    (detergent -> 82-90 C hot water/steam -> disinfectant).
      ServiceSprayRing  a second ring DEEP on the service side, behind the deployed piston
                    face, so it is NEVER in the occupant space; washes the sealed chamber's
                    far end when the cell is closed [ADR-0018].
      TrenchDrain   a flush, grated channel set into the PAVEMENT at the mouth base for
                    the ejected SOLIDS + rain -> sewer. Streetscape infrastructure, not an
                    appendage -- bolted, walk-on, serviced from below.
      SumpDrain     the internal WASH-MEDIA drain: a sump in the bore floor at the deep
                    end, positioned UNDER the piston when it is deployed to the very back,
                    so it is never exposed in the occupied cavity or to the public. The
                    floor slopes to it; hot water + chemicals drain here -> sewer (ADR-0017).
      ServicePlant  back-of-house envelope AROUND the actuator (hot-water/steam gen,
                    disinfectant reservoir + doser, dry-air blower, pump) -- widens the
                    cross-section but adds NO install depth (sits over the actuator zone).
    Public opening is at X=0; +X runs into the wall (service side)."""
    w = sheet.cavityWidth.Value
    h = sheet.interiorHeight.Value
    r = sheet.cornerRadius.Value
    t = sheet.wallThickness.Value
    bl = sheet.barrelLength.Value
    gap = sheet.actuatorGap.Value
    md = sheet.magazineDepth.Value
    pl = sheet.pistonLength.Value
    c = sheet.runningClearance.Value
    parts = {}

    # 1. in-bore spray ring: nozzle ring OUTSIDE the barrel (bore stays clear)
    mr = sheet.sprayRingRadial.Value
    mdp = sheet.sprayRingDepth.Value
    ms0 = sheet.sprayRingSetback.Value
    outer = rounded_box_shape(w + 2 * t + 2 * mr, h + 2 * t + 2 * mr, mdp, r + t + mr, x0=ms0)
    inner = rounded_box_shape(w + 2 * t, h + 2 * t, mdp + 2.0, r + t, x0=ms0 - 1.0)
    ring = doc.addObject("Part::Feature", "SprayRing")
    ring.Shape = outer.cut(inner)
    parts["SprayRing"] = ring

    # 1b. service-side spray ring: DEEP, behind the deployed piston face, so it is never
    #     in the occupant space; washes the sealed chamber's far end when closed [ADR-0018]
    srs = sheet.serviceRingSetback.Value
    srd = sheet.serviceRingDepth.Value
    srx = sheet.cavityLength.Value + srs
    souter = rounded_box_shape(w + 2 * t + 2 * mr, h + 2 * t + 2 * mr, srd, r + t + mr, x0=srx)
    sinner = rounded_box_shape(w + 2 * t, h + 2 * t, srd + 2.0, r + t, x0=srx - 1.0)
    sring = doc.addObject("Part::Feature", "ServiceSprayRing")
    sring.Shape = souter.cut(sinner)
    parts["ServiceSprayRing"] = sring

    # 1c. traveling service squeegee: a wiper that runs the FULL sealed chamber while the
    #     piston is parked flush -- a car wash over the stopped piston, scrubbing from inside
    #     the bore + driving the wash media to the sump. Modeled STOWED behind the deployed
    #     piston (in the barrel's stow bay); lives entirely service-side, never seen by the
    #     user. Needs its own light drive (fights only wiper drag, not seal pressure) [ADR-0019]
    sqth = sheet.squeegeeThickness.Value
    sqx = sheet.cavityLength.Value + pl                       # right behind the deployed piston back
    band = 120.0                                             # radial wiper-band width
    qouter = rounded_box_shape(w - 2 * c, h - 2 * c, sqth, r - c, x0=sqx)
    qinner = rounded_box_shape(w - 2 * c - 2 * band, h - 2 * c - 2 * band, sqth + 2.0,
                               max(0.0, r - c - band), x0=sqx - 1.0)
    squeegee = doc.addObject("Part::Feature", "ServiceSqueegee")
    squeegee.Shape = qouter.cut(qinner)
    parts["ServiceSqueegee"] = squeegee

    # 1d. dedicated squeegee drive (ADR-0020): the squeegee's OWN compact rigid-chain, a
    #     modular unit that nests in the back-of-house BESIDE the piston's actuator (no added
    #     depth) so it can be bench-tested + swapped independently. Fixed magazine, like the piston's.
    ms = sheet.magazineSize.Value
    sdw, sdh = 260.0, 520.0                                   # drive magazine cross-section Y, Z
    drive = doc.addObject("Part::Feature", "SqueegeeDrive")
    drive.Shape = Part.makeBox(md, sdw, sdh,
                               App.Vector(bl + gap, ms / 2.0 + 40.0, -sdh / 2.0))
    parts["SqueegeeDrive"] = drive

    # 1e. drive chain + coupling yoke [ADR-0021]. The rigid chain runs INSIDE the sealed bore in
    #     an OFFSET +Y lane (no wall slot, ADR-0007): valid because the piston (central) and the
    #     squeegee (offset) never share the chamber at once -- piston deployed => squeegee stowed;
    #     cleaning => piston parked flush at the mouth so the whole chamber is free. A short rigid
    #     yoke reaches from the offset chain out to the ring's +Y frame; the bore guides against
    #     rack (like the piston in its non-circular bore). Shown at the STOWED pose (chain
    #     retracted, exposed column short) to match the stowed ServiceSqueegee.
    cw = sheet.chainWidth.Value
    ch = sheet.chainHeight.Value
    offY = sheet.squeegeeChainOffsetY.Value
    sq_back = sqx + sqth                                      # stowed squeegee back face
    mag_front = bl + gap                                      # drive magazine front
    chain = doc.addObject("Part::Feature", "SqueegeeChain")
    chain.Shape = Part.makeBox(mag_front - sq_back, cw, ch,
                               App.Vector(sq_back, offY - cw / 2.0, -ch / 2.0))
    parts["SqueegeeChain"] = chain
    # yoke: bridges the offset chain (Y=offY) out to the ring's +Y frame at the bore wall, at the
    #       squeegee back. Representative bracket -- transfers push on the +Y side only (never -Y).
    yoke_y0 = offY - cw / 2.0
    yoke_y1 = w / 2.0 - c                                     # ring +Y outer frame (bore wall)
    yoke = doc.addObject("Part::Feature", "SqueegeeYoke")
    yoke.Shape = Part.makeBox(40.0, yoke_y1 - yoke_y0, 160.0,
                              App.Vector(sq_back, yoke_y0, -80.0))
    parts["SqueegeeYoke"] = yoke

    # 2. flush pavement trench drain at the mouth base (ground = sill height below the
    #    bore floor) -- catches the SOLIDS the closing sweep ejects, + rain -> sewer
    tw = sheet.trenchWidth.Value
    tdp = sheet.trenchDepth.Value
    tm = sheet.trenchMargin.Value
    ground = -(h / 2.0 + t) - sheet.sillHeight.Value          # pavement level (Z)
    # a real GRATED cover, not a plain trough: slots run across the channel (along X)
    # so the solids the closing sweep ejects drop through into the channel -> sewer.
    # Solid base + Y end-frame + X side-rails keep it a drain, not an open hole.
    # (slot pattern is a local detail, cf. the SqueegeeDrive cross-section above.)
    tlen = w + 2 * tm                                          # grate span across the mouth (Y)
    bar_w, slot_w = 14.0, 22.0                                 # grate bar / open slot (Y)
    side_rail, end_margin = 8.0, 25.0                          # solid X edges + Y end frame
    slot_depth = 70.0                                          # slot cut depth into the tdp channel
    grate = Part.makeBox(tw, tlen, tdp, App.Vector(-tw, -tlen / 2.0, ground - tdp))
    y = -tlen / 2.0 + end_margin
    while y + slot_w <= tlen / 2.0 - end_margin:
        grate = grate.cut(Part.makeBox(
            tw - 2 * side_rail, slot_w, slot_depth + 1.0,
            App.Vector(-tw + side_rail, y, ground - slot_depth)))
        y += bar_w + slot_w
    trench = doc.addObject("Part::Feature", "TrenchDrain")
    trench.Shape = grate
    parts["TrenchDrain"] = trench

    # 3. internal back sump: takes the WASH MEDIA (hot water + chemicals) to sewer,
    #    hidden UNDER the piston when it is deployed to the very back (never in the open
    #    cavity or on the public face); the bore floor slopes to it [ADR-0017]
    sw = sheet.sumpWidth.Value
    sl = sheet.sumpLength.Value
    sdp = sheet.sumpDepth.Value
    scx = sheet.cavityLength.Value + pl / 2.0                 # mid deployed-piston body (robust to barrel length)
    sump = doc.addObject("Part::Feature", "SumpDrain")
    sump.Shape = Part.makeBox(sw, sl, sdp, App.Vector(scx - sw / 2.0, -sl / 2.0, -(h / 2.0) - sdp))
    parts["SumpDrain"] = sump

    # 4. back-of-house plant envelope wrapping the actuator zone (no added depth)
    sp = sheet.servicePlantSize.Value
    plant = doc.addObject("Part::Feature", "ServicePlant")
    plant.Shape = Part.makeBox(gap + md, sp, sp, App.Vector(bl, -sp / 2.0, -sp / 2.0))
    parts["ServicePlant"] = plant

    doc.recompute()
    return parts


def main():
    if App.ActiveDocument and App.ActiveDocument.Name == "HiveCell":
        App.closeDocument("HiveCell")
    doc = App.newDocument("HiveCell")

    sheet = build_parameters(doc)
    ref_body, _tip = build_cavity_reference(doc, sheet)
    shell = build_capsule_shell(doc, sheet)
    piston = build_piston(doc, sheet)
    seals = build_wiper_seals(doc, sheet)
    build_chain_actuator(doc, sheet)
    lum = build_luminaire(doc, sheet)
    clean = build_cleaning(doc, sheet)
    ref_body.Visibility = False  # keep-out is a reference; hide so the shell shows

    doc.recompute()
    doc.saveAs(OUT)

    t = sheet.wallThickness.Value
    L = sheet.barrelLength.Value
    bb = shell.Shape.BoundBox
    axis_pt = App.Vector(L / 2.0, 0, 0)                                        # in the void
    wall_pt = App.Vector(L / 2.0, sheet.cavityWidth.Value / 2.0 + t / 2.0, 0)  # in the wall
    print("--- build_model.py OK ---")
    print(f"saved: {OUT}")
    print(f"CapsuleShell bbox (mm): X={bb.XLength:.0f}  Y={bb.YLength:.0f}  Z={bb.ZLength:.0f}")
    print(f"expected (inner+2t):    X={L:.0f}  Y={sheet.cavityWidth.Value + 2 * t:.0f}  "
          f"Z={sheet.interiorHeight.Value + 2 * t:.0f}")
    print(f"solids: {len(shell.Shape.Solids)}  valid: {shell.Shape.isValid()}")
    print(f"hollow check: centre-in-void={shell.Shape.isInside(axis_pt, 0.01, True)} "
          f"(want False)  point-in-wall={shell.Shape.isInside(wall_pt, 0.01, True)} (want True)")

    pbb = piston.Shape.BoundBox
    c = sheet.runningClearance.Value
    overlap = shell.Shape.common(piston.Shape).Volume
    print(f"Piston bbox (mm):       X={pbb.XLength:.0f}  Y={pbb.YLength:.0f}  Z={pbb.ZLength:.0f}")
    print(f"expected (bore-2c):     X={sheet.pistonLength.Value:.0f}  "
          f"Y={sheet.cavityWidth.Value - 2 * c:.0f}  Z={sheet.interiorHeight.Value - 2 * c:.0f}")
    print(f"deployed front face X={pbb.XMin:.0f} (want {sheet.cavityLength.Value:.0f})  "
          f"back X={pbb.XMax:.0f} (want {sheet.cavityLength.Value + sheet.pistonLength.Value:.0f}; "
          f"barrel {L:.0f} adds a stow bay behind it, ADR-0019)")
    print(f"piston<->wall overlap volume={overlap:.1f} mm^3 (want ~0: {c:.0f} mm clearance)")

    sbb = seals.Shape.BoundBox
    seal_in_shell = shell.Shape.common(seals.Shape).Volume
    seal_in_piston = piston.Shape.common(seals.Shape).Volume
    print(f"WiperSeals (SF3): {int(sheet.sealLipCount)} lips x "
          f"{sheet.sealLipThickness.Value:.0f} mm, fill {c:.0f} mm gap; "
          f"volume={seals.Shape.Volume / 1000.0:.1f} cm^3")
    print(f"seals bbox (mm):        X={sbb.XLength:.0f}  Y={sbb.YLength:.0f}  Z={sbb.ZLength:.0f}")
    print(f"seal<->shell overlap={seal_in_shell:.1f} (want ~0, touches bore)  "
          f"seal<->piston overlap={seal_in_piston:.1f} (want ~0, hugs piston)")

    install_depth = (sheet.barrelLength.Value + sheet.actuatorGap.Value
                     + sheet.magazineDepth.Value)
    print(f"Rigid-chain: magazine {sheet.magazineDepth.Value:.0f} deep x "
          f"{sheet.magazineSize.Value:.0f} sq, chain {sheet.chainWidth.Value:.0f}x{sheet.chainHeight.Value:.0f}")
    print(f"Total install depth behind wall: {install_depth:.0f} mm ({install_depth / 1000:.2f} m)")

    lbb = lum.Shape.BoundBox
    lum_in_cavity = ref_body.Shape.common(lum.Shape).Volume       # must be ~0 (flush, no intrusion)
    lum_in_wall = shell.Shape.common(lum.Shape).Volume            # ~full volume (seated in the crown wall)
    print(f"Luminaire (ADR-0014): crown strip {sheet.luminaireLength.Value:.0f} x "
          f"{sheet.luminaireWidth.Value:.0f} mm, {sheet.luminaireDepth.Value:.0f} mm deep, flush at crown")
    print(f"luminaire bbox (mm):    X={lbb.XLength:.0f}  Y={lbb.YLength:.0f}  Z={lbb.ZLength:.0f}  "
          f"(crown Z={sheet.interiorHeight.Value / 2:.0f}..{sheet.interiorHeight.Value / 2 + sheet.luminaireDepth.Value:.0f})")
    print(f"lum<->cavity intrusion={lum_in_cavity:.1f} mm^3 (want ~0: flush, no keep-out steal)  "
          f"lum<->wall seated={lum_in_wall / 1000.0:.1f} cm^3 (want ~full: in the crown wall)")

    # ADR-0015 cleaning subsystem (space claim) --------------------------------
    ring = clean["SprayRing"]
    sring = clean["ServiceSprayRing"]
    mbb = ring.Shape.BoundBox
    smbb = sring.Shape.BoundBox
    print("--- ADR-0015/0018 cleaning (space claim) ---")
    print(f"SprayRing (front): X={mbb.XMin:.0f}..{mbb.XMax:.0f} (past closed piston "
          f"{sheet.pistonLength.Value:.0f})  cavity intrusion={ref_body.Shape.common(ring.Shape).Volume:.1f} (want ~0)")
    print(f"ServiceSprayRing (deep): X={smbb.XMin:.0f}..{smbb.XMax:.0f} (behind deployed face "
          f"{sheet.cavityLength.Value:.0f})  cavity intrusion={ref_body.Shape.common(sring.Shape).Volume:.1f} (want ~0: never in cavity)")
    qbb = clean["ServiceSqueegee"].Shape.BoundBox
    print(f"ServiceSqueegee (traveling wiper): stows X={qbb.XMin:.0f}..{qbb.XMax:.0f} behind the deployed "
          f"piston; travels the sealed chamber when the piston is parked flush")
    dbb = clean["SqueegeeDrive"].Shape.BoundBox
    print(f"SqueegeeDrive (modular, swappable): X={dbb.XMin:.0f}..{dbb.XMax:.0f} Y={dbb.YMin:.0f}..{dbb.YMax:.0f} "
          f"-- own rigid-chain, nests beside the piston actuator (install depth unchanged)")
    scb = clean["SqueegeeChain"].Shape.BoundBox
    ykb = clean["SqueegeeYoke"].Shape.BoundBox
    chain_intr = ref_body.Shape.common(clean["SqueegeeChain"].Shape).Volume
    yoke_intr = ref_body.Shape.common(clean["SqueegeeYoke"].Shape).Volume
    print(f"SqueegeeChain+Yoke (ADR-0021 coupling): chain in an OFFSET +Y lane inside the bore "
          f"Y={scb.YMin:.0f}..{scb.YMax:.0f} (wall at {sheet.cavityWidth.Value / 2.0:.0f}); yoke reaches "
          f"Y={ykb.YMin:.0f}..{ykb.YMax:.0f} to the ring frame")
    print(f"    no wall slot; cavity intrusion chain={chain_intr:.1f} yoke={yoke_intr:.1f} (want ~0: "
          f"both stow behind the deployed piston, X>{sheet.cavityLength.Value:.0f})")
    for nm in ("TrenchDrain", "SumpDrain", "ServicePlant"):
        b = clean[nm].Shape.BoundBox
        print(f"{nm}: X={b.XMin:.0f}..{b.XMax:.0f}  Y={b.YLength:.0f}  Z={b.ZMin:.0f}..{b.ZMax:.0f} mm")
    sb = clean["SumpDrain"].Shape.BoundBox
    print(f"TrenchDrain at pavement (solids); SumpDrain X={sb.XMin:.0f}..{sb.XMax:.0f} sits under the "
          f"deployed piston ({sheet.cavityLength.Value:.0f}..{sheet.barrelLength.Value:.0f}) -> hidden when open")
    sp = sheet.servicePlantSize.Value
    print(f"back-of-house cross-section now ~{sp:.0f} mm sq (actuator magazine was "
          f"{sheet.magazineSize.Value:.0f}); install depth UNCHANGED at "
          f"{install_depth:.0f} mm ({install_depth / 1000:.2f} m) -- plant wraps the actuator zone")


main()
