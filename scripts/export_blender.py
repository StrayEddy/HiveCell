"""Export HiveCell parts as Blender-ready meshes (meters, Z-up) + a manifest.

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/export_blender.py

Writes blender/models/<Part>.obj (one file per part, so each gets its own
material) and blender/models/scene.json (dims for siting the cell in a wall).
Finer tessellation than the Godot export -- these feed Cycles hero renders, so
the rounded corners must look smooth. FreeCAD and Blender are BOTH Z-up + this
scales mm -> m, so no rotation is needed (unlike the Godot Y-up export).
"""
import json
import os
import FreeCAD as App
import MeshPart

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"
OUTDIR = "/home/eddy/Projects/HiveCell/blender/models"
PARTS = ["CapsuleShell", "Piston", "WiperSeals", "ChainMagazine", "ChainColumn",
         # ADR-0015 cleaning subsystem (fixed space-claim parts)
         "SprayRing", "ServiceSprayRing", "TrenchDrain", "SumpDrain", "ServicePlant"]

# Fine tessellation for smooth render silhouettes (mm units, pre-scale).
LINEAR_DEFLECTION = 0.2      # max chord error, mm (Godot used 1.0)
ANGULAR_DEFLECTION = 0.15    # rad

os.makedirs(OUTDIR, exist_ok=True)
doc = App.open(DOC)

# mm -> m only; keep Z-up (Blender is Z-up, same as FreeCAD).
xform = App.Matrix()
xform.scale(0.001, 0.001, 0.001)

for name in PARTS:
    shape = doc.getObject(name).Shape
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=LINEAR_DEFLECTION,
                                  AngularDeflection=ANGULAR_DEFLECTION, Relative=False)
    mesh.transform(xform)
    path = os.path.join(OUTDIR, name + ".obj")
    mesh.write(path)
    print(f"exported {name}: {mesh.CountFacets} facets -> {path}")

sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet")
scene = {
    "interior_height_m": round(sheet.interiorHeight.Value / 1000.0, 4),
    "cavity_width_m": round(sheet.cavityWidth.Value / 1000.0, 4),
    "corner_radius_m": round(sheet.cornerRadius.Value / 1000.0, 4),
    "wall_thickness_m": round(sheet.wallThickness.Value / 1000.0, 4),
    "barrel_length_m": round(sheet.barrelLength.Value / 1000.0, 4),
    "cavity_length_m": round(sheet.cavityLength.Value / 1000.0, 4),
    # interior luminaire (ADR-0014): flush crown strip; the render builds it procedurally
    # (emissive) from these dims + shows the state colour / warm glow.
    "luminaire_length_m": round(sheet.luminaireLength.Value / 1000.0, 4),
    "luminaire_width_m": round(sheet.luminaireWidth.Value / 1000.0, 4),
    "luminaire_end_margin_m": round(sheet.luminaireEndMargin.Value / 1000.0, 4),
    "luminaire_crown_m": round(sheet.interiorHeight.Value / 2000.0, 4),  # up-axis coord of the bore crown
    # facility siting (ADR-0013 / SAFETY.md): mouth sill ~500 mm above ground.
    "sill_height_m": 0.5,
    "mouth_x_m": 0.0,             # public opening plane (barrel min X)
    "parts": PARTS,
}
with open(os.path.join(OUTDIR, "scene.json"), "w") as f:
    json.dump(scene, f, indent=2)
print("scene:", scene)

App.closeDocument(doc.Name)
