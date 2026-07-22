"""FreeCAD-FEM structural check of the piston (first-order).

Run headless (FEM pipeline is bundled in the FreeCAD Flatpak: ccx + gmsh):
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/fem_piston.py

Meshes the piston, assigns stainless steel, and applies three loads at once:
  1. self-weight (gravity),
  2. the actuator thrust on the rear cap (ACTUATOR_N, the closing-stroke design
     force from actuator_sizing.py, ~5.5 kN),
  3. a representative occupant load on the front cap (OCC_LOAD_N, someone leaning
     on the deployed back wall).
The perimeter side faces are the guide-bearing band and are held fixed -- they
react everything, so the two large flat caps (the weak features of a thin-shell
plug) carry the loads in bending. Solves with CalculiX (ccx) and reports max von
Mises stress, max displacement, and mass. Answers: does the lightweighted piston
keep stress below yield and deflection small under the drive + occupant loads?

WALL_MM = 0 runs the SOLID piston -- robust, and a stiffness/stress baseline +
the solid-mass reality check. WALL_MM > 0 shells the plug to that wall (open
service side): the physically-relevant lightweighted case, but a thin wall needs
a finer ELEM_MM and may need mesh tuning. Everything here is first-order; the
loads/material are flagged assumptions. The actuator thrust is spread over the
whole rear cap (a GLOBAL check); the local contact stress under the 60x60 chain
patch is a separate, more demanding check not modeled here.

Practical note: a reliable thin-wall SOLID run (>=2 elements through a 6 mm wall,
i.e. ELEM_MM<=3) over this ~1x1x0.3 m plug is millions of quadratic tets and OOMs
FreeCAD's mesh conversion on a 16 GB box. Coarse runs validate MASS fine; for
reliable thin-wall STRESS use 2D shell elements (or a bigger machine). This is
not the binding constraint anyway -- the loads are light for a stainless plug, so
MASS drives the design; see the coarse-run numbers and the README/SAFETY notes.

Env overrides: WALL_MM, ELEM_MM, ACTUATOR_N, OCC_LOAD_N
  (e.g. WALL_MM=6 ELEM_MM=15 flatpak run ... for a fast mass check).
"""
import os
import FreeCAD as App
import ObjectsFem
from femtools import ccxtools
from femmesh.gmshtools import GmshTools

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"

# --- parameters (assumptions flagged) --------------------------------------
WALL_MM = float(os.environ.get("WALL_MM", "0"))        # 0 = solid; >0 = shell
ELEM_MM = float(os.environ.get("ELEM_MM", "40"))       # gmsh element size
# actuator thrust on the rear cap: closing-stroke DESIGN force from actuator_sizing.py
ACTUATOR_N = float(os.environ.get("ACTUATOR_N", "5546"))
# occupant leaning on the deployed back wall (front cap): ~one P95 person's weight
OCC_LOAD_N = float(os.environ.get("OCC_LOAD_N", "1000"))
CCX = "/app/bin/ccx"

E_MPA = 200000.0     # stainless 304
NU = 0.30
RHO = 8000.0         # kg/m^3
YIELD_MPA = 215.0    # 304 approx


def main():
    doc = App.open(DOC)
    piston = doc.getObject("Piston")
    shape = piston.Shape

    if WALL_MM > 0.0:
        # Lightweight: remove the rear (max-X) face and thicken inward.
        rear = max(range(len(shape.Faces)), key=lambda i: shape.Faces[i].CenterOfMass.x)
        shape = shape.makeThickness([shape.Faces[rear]], -WALL_MM, 1e-3)

    geo = doc.addObject("Part::Feature", "PistonFEM")
    geo.Shape = shape
    doc.recompute()

    # Front cap (min-X centroid) = occupant's back wall; rear cap (max-X) = actuator
    # coupling; every other face is the perimeter guide band, held fixed. The band
    # reacts the loads so the two large flat caps carry them in bending -- a
    # conservative idealisation targeting the weak features of a thin-shell plug.
    faces = geo.Shape.Faces
    front = min(range(len(faces)), key=lambda i: faces[i].CenterOfMass.x)
    rear = max(range(len(faces)), key=lambda i: faces[i].CenterOfMass.x)
    front_name = "Face%d" % (front + 1)
    rear_name = "Face%d" % (rear + 1)
    band = ["Face%d" % (i + 1) for i in range(len(faces)) if i not in (front, rear)]
    occ_mpa = OCC_LOAD_N / faces[front].Area        # N/mm^2 = MPa
    act_mpa = ACTUATOR_N / faces[rear].Area

    analysis = ObjectsFem.makeAnalysis(doc, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiX")
    solver.AnalysisType = "static"
    solver.GeometricalNonlinearity = "linear"
    analysis.addObject(solver)

    mat = ObjectsFem.makeMaterialSolid(doc, "Stainless304")
    md = mat.Material
    md["Name"] = "Stainless-304"
    md["YoungsModulus"] = "%f MPa" % E_MPA
    md["PoissonRatio"] = str(NU)
    md["Density"] = "%f kg/m^3" % RHO
    mat.Material = md
    analysis.addObject(mat)

    fixed = ObjectsFem.makeConstraintFixed(doc, "GuideBand")
    fixed.References = [(geo, band)]
    analysis.addObject(fixed)

    occ = ObjectsFem.makeConstraintPressure(doc, "OccupantLoad")
    occ.References = [(geo, [front_name])]
    occ.Pressure = "%f MPa" % occ_mpa
    occ.Reversed = False                              # pushes into the plug (+X)
    analysis.addObject(occ)

    act = ObjectsFem.makeConstraintPressure(doc, "ActuatorThrust")
    act.References = [(geo, [rear_name])]
    act.Pressure = "%f MPa" % act_mpa
    act.Reversed = False                              # chain pushes the piston (-X into plug)
    analysis.addObject(act)

    grav = ObjectsFem.makeConstraintSelfWeight(doc, "Gravity")
    analysis.addObject(grav)

    mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
    mesh.Shape = geo
    mesh.CharacteristicLengthMax = "%f mm" % ELEM_MM
    mesh.CharacteristicLengthMin = "%f mm" % ELEM_MM
    mesh.ElementOrder = "2nd"
    analysis.addObject(mesh)
    GmshTools(mesh).create_mesh()
    fm = mesh.FemMesh
    print("mesh: %d nodes, %d volume elements" % (fm.NodeCount, fm.VolumeCount))

    # Honesty guard: thin-wall bending needs >= ~2 elements through the wall.
    under_resolved = WALL_MM > 0.0 and ELEM_MM > WALL_MM / 2.0
    if under_resolved:
        print("WARNING: element %.0f mm > wall/2 (%.1f mm) -> <2 elements through the "
              "wall, bending UNDER-RESOLVED. Mass is fine; STRESS IS UNRELIABLE. Use "
              "ELEM_MM <= %.1f (heavy) or 2D shell elements." % (
                  ELEM_MM, WALL_MM / 2.0, WALL_MM / 2.0))

    fea = ccxtools.FemToolsCcx(analysis, solver)
    fea.update_objects()
    fea.setup_working_dir()
    fea.setup_ccx(CCX)
    msg = fea.check_prerequisites()
    if msg:
        print("PREREQ:", msg)
    fea.purge_results()
    fea.write_inp_file()
    fea.ccx_run()
    fea.load_results()

    res = None
    for o in doc.Objects:
        if o.isDerivedFrom("Fem::FemResultObject"):
            res = o
    if res is None or not res.vonMises:
        print("no results produced")
        return

    max_vm = max(res.vonMises)                     # MPa
    max_disp = max(res.DisplacementLengths)         # mm
    mass = geo.Shape.Volume / 1e9 * RHO             # kg
    sf = (YIELD_MPA / max_vm) if max_vm > 0 else float("inf")

    print("--- FEM piston check (first-order) ---")
    print("case            : %s, elem %.0f mm" % (
        ("SHELL %.0f mm" % WALL_MM) if WALL_MM > 0 else "SOLID", ELEM_MM))
    print("loads           : gravity + actuator %.0f N (rear) + occupant %.0f N (front)" % (
        ACTUATOR_N, OCC_LOAD_N))
    print("mass            : %8.1f kg" % mass)
    print("max von Mises   : %8.2f MPa   (yield ~%.0f MPa, 304)" % (max_vm, YIELD_MPA))
    print("safety factor   : %8.2f     (yield / max stress)" % sf)
    print("max displacement: %8.3f mm" % max_disp)
    if under_resolved:
        verdict = "MASS ok; STRESS UNRELIABLE (mesh too coarse for the wall)"
    else:
        verdict = "OK (SF>=2)" if sf >= 2.0 else "REVIEW (SF<2)"
    print("verdict         : %s" % verdict)

    App.closeDocument(doc.Name)


main()
