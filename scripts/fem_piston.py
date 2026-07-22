"""FreeCAD-FEM structural check of the piston (first-order).

Run headless (FEM pipeline is bundled in the FreeCAD Flatpak: ccx + gmsh):
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/fem_piston.py

Meshes the piston, assigns stainless steel, applies gravity + a design face
load, solves with CalculiX (ccx), and reports max von Mises stress, max
displacement, and mass. Answers: does the piston keep stress below yield and
deflection small under load?

WALL_MM = 0 runs the SOLID piston -- robust, and a stiffness/stress baseline +
the solid-mass reality check. WALL_MM > 0 shells the plug to that wall (open
service side): the physically-relevant lightweighted case, but a thin wall needs
a finer ELEM_MM and may need mesh tuning. Everything here is first-order; the
loads/material are flagged assumptions.

Env overrides: WALL_MM, ELEM_MM, FACE_LOAD_N (e.g. WALL_MM=6 ELEM_MM=8 ...).
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
FACE_LOAD_N = float(os.environ.get("FACE_LOAD_N", "2000"))  # face design load
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

    # Front face (min-X centroid) takes the load; all other faces are fixed
    # (guide + actuator coupling) -- a conservative plate-bending idealisation.
    faces = geo.Shape.Faces
    front = min(range(len(faces)), key=lambda i: faces[i].CenterOfMass.x)
    front_name = "Face%d" % (front + 1)
    other = ["Face%d" % (i + 1) for i in range(len(faces)) if i != front]
    face_area_mm2 = faces[front].Area
    pressure_mpa = FACE_LOAD_N / face_area_mm2      # N/mm^2 = MPa

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

    fixed = ObjectsFem.makeConstraintFixed(doc, "Fixed")
    fixed.References = [(geo, other)]
    analysis.addObject(fixed)

    pres = ObjectsFem.makeConstraintPressure(doc, "FaceLoad")
    pres.References = [(geo, [front_name])]
    pres.Pressure = "%f MPa" % pressure_mpa
    pres.Reversed = False
    analysis.addObject(pres)

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
    print("case            : %s, elem %.0f mm, face load %.0f N" % (
        ("SHELL %.0f mm" % WALL_MM) if WALL_MM > 0 else "SOLID", ELEM_MM, FACE_LOAD_N))
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
