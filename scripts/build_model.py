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
    ("pistonLength",    "300 mm",                        "piston depth along X"),
    ("barrelLength",    "=cavityLength + pistonLength",  "sleeve length: houses the deployed piston"),
    ("actuatorRodDia",  "70 mm",                         "drive rod / screw diameter (representative)"),
    ("actuatorBodyDia", "160 mm",                        "actuator motor+screw housing diameter (representative)"),
    ("actuatorBodyLength", "700 mm",                     "actuator housing length"),
    ("actuatorGap",     "60 mm",                         "gap: deployed piston rear to housing front"),
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


def build_actuator(doc, sheet):
    """Electric linear actuator (representative): a central rod + motor/screw
    housing behind the piston, in the service area. The rod translates -X to
    close and +X to deploy; the non-circular bore stops the piston rotating and
    provides front guidance (no external rails -- they'd need a slot through the
    sealed bore). Modeled at the DEPLOYED pose (rod short). Unit selection follows
    scripts/actuator_sizing.py (design force ~1.2 kN)."""
    bl = sheet.barrelLength.Value
    gap = sheet.actuatorGap.Value
    rod_r = sheet.actuatorRodDia.Value / 2.0
    body_r = sheet.actuatorBodyDia.Value / 2.0
    body_l = sheet.actuatorBodyLength.Value
    X = App.Vector(1, 0, 0)

    rod = doc.addObject("Part::Feature", "ActuatorRod")
    rod.Shape = Part.makeCylinder(rod_r, gap, App.Vector(bl, 0, 0), X)
    housing = doc.addObject("Part::Feature", "ActuatorHousing")
    housing.Shape = Part.makeCylinder(body_r, body_l, App.Vector(bl + gap, 0, 0), X)
    doc.recompute()
    return rod, housing


def main():
    if App.ActiveDocument and App.ActiveDocument.Name == "HiveCell":
        App.closeDocument("HiveCell")
    doc = App.newDocument("HiveCell")

    sheet = build_parameters(doc)
    ref_body, _tip = build_cavity_reference(doc, sheet)
    shell = build_capsule_shell(doc, sheet)
    piston = build_piston(doc, sheet)
    build_actuator(doc, sheet)
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
          f"back X={pbb.XMax:.0f} (want barrelLength {L:.0f})")
    print(f"piston<->wall overlap volume={overlap:.1f} mm^3 (want ~0: {c:.0f} mm clearance)")

    install_depth = (sheet.barrelLength.Value + sheet.actuatorGap.Value
                     + sheet.actuatorBodyLength.Value)
    print(f"Actuator: rod {sheet.actuatorRodDia.Value:.0f}dia, "
          f"housing {sheet.actuatorBodyDia.Value:.0f}dia x {sheet.actuatorBodyLength.Value:.0f}")
    print(f"Total install depth behind wall: {install_depth:.0f} mm ({install_depth / 1000:.2f} m)")


main()
