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


def main():
    if App.ActiveDocument and App.ActiveDocument.Name == "HiveCell":
        App.closeDocument("HiveCell")
    doc = App.newDocument("HiveCell")

    sheet = build_parameters(doc)
    _body, tip = build_cavity_reference(doc, sheet)

    doc.recompute()
    doc.saveAs(OUT)

    bb = tip.Shape.BoundBox
    floor = sheet.floorWidth.Value
    shoulder = sheet.shoulderP95.Value
    n_fillets = len(tip.Base[1]) if tip.Base else 0
    print("--- build_model.py OK ---")
    print(f"saved: {OUT}")
    print(f"Capsule bbox (mm):  X={bb.XLength:.0f}  Y={bb.YLength:.0f}  Z={bb.ZLength:.0f}")
    print(f"expected:           X=2200  Y=1000  Z=1100")
    print(f"rounded long edges: {n_fillets} (expected 4)")
    print(f"flat floor width:   {floor:.0f} mm  vs shoulderP95 {shoulder:.0f} mm  "
          f"-> {'OK' if floor > shoulder else 'TOO NARROW'}")


main()
