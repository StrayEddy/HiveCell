"""Export HiveCell parts as Godot-ready meshes (meters, Y-up) + a manifest.

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/export_godot.py

Writes godot/models/<Part>.obj (one file per part, so the piston stays a
separate animatable node) and godot/models/hivecell.json (dims + timing for
the digital-twin script). FreeCAD is mm + Z-up; Godot is meters + Y-up, so each
mesh is scaled 0.001 and rotated -90 deg about X: (x,y,z)_mm -> (x, z, -y)_m.
The +X motion axis is preserved, so retraction is a single -X translation.
"""
import json
import math
import os
import FreeCAD as App
import MeshPart

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"
OUTDIR = "/home/eddy/Projects/HiveCell/godot/models"
PARTS = ["CapsuleShell", "Piston", "WiperSeals", "ChainMagazine",
         # ADR-0015 cleaning subsystem (fixed space-claim parts)
         "SprayRing", "ServiceSprayRing", "ServiceSqueegee", "SqueegeeDrive",
         "SqueegeeYoke",  # ADR-0021 coupling yoke (SqueegeeChain drawn procedurally, variable length)
         "TrenchDrain", "SumpDrain", "ServicePlant"]
# ChainColumn is drawn procedurally (variable length is physical for a chain)

os.makedirs(OUTDIR, exist_ok=True)
doc = App.open(DOC)

# mm -> m and Z-up -> Y-up in one matrix (uniform scale commutes with rotation).
xform = App.Matrix()
xform.rotateX(math.radians(-90))       # (x, y, z) -> (x, z, -y)
xform.scale(0.001, 0.001, 0.001)

for name in PARTS:
    shape = doc.getObject(name).Shape
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=1.0,
                                  AngularDeflection=0.35, Relative=False)
    mesh.transform(xform)
    path = os.path.join(OUTDIR, name + ".obj")
    mesh.write(path)
    print(f"exported {name}: {mesh.CountFacets} facets -> {path}")

sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet")
install_depth_mm = (sheet.barrelLength.Value + sheet.actuatorGap.Value
                    + sheet.magazineDepth.Value)
manifest = {
    "stroke_m": round(sheet.stroke.Value / 1000.0, 4),
    "barrel_length_m": round(sheet.barrelLength.Value / 1000.0, 4),
    "install_depth_m": round(install_depth_mm / 1000.0, 4),
    "piston_rear_deployed_m": round(sheet.barrelLength.Value / 1000.0, 4),
    "magazine_front_m": round((sheet.barrelLength.Value + sheet.actuatorGap.Value) / 1000.0, 4),
    "chain_width_m": round(sheet.chainWidth.Value / 1000.0, 4),
    "chain_height_m": round(sheet.chainHeight.Value / 1000.0, 4),
    # capsule envelope, for siting the cell in a wall in the twin (mouth opening size)
    "interior_height_m": round(sheet.interiorHeight.Value / 1000.0, 4),
    "cavity_width_m": round(sheet.cavityWidth.Value / 1000.0, 4),
    "corner_radius_m": round(sheet.cornerRadius.Value / 1000.0, 4),
    "wall_thickness_m": round(sheet.wallThickness.Value / 1000.0, 4),
    # interior luminaire (ADR-0014): flush crown strip; the twin builds it procedurally
    # (like ChainColumn) from these dims + shows the state colour / warm glow.
    "luminaire_length_m": round(sheet.luminaireLength.Value / 1000.0, 4),
    "luminaire_width_m": round(sheet.luminaireWidth.Value / 1000.0, 4),
    "luminaire_end_margin_m": round(sheet.luminaireEndMargin.Value / 1000.0, 4),
    "luminaire_crown_m": round(sheet.interiorHeight.Value / 2000.0, 4),  # up-axis coord of the bore crown
    # facility-level siting (ADR-0013 / SAFETY.md): mouth sill ~500 mm above ground.
    # Not a CAD dimension -- an install spec the twin renders (ground + wall context).
    "sill_height_m": 0.5,
    "retract_seconds_real": 600,     # ~10 min real-world retraction
    "moving_parts": ["Piston", "WiperSeals", "ServiceSqueegee", "SqueegeeYoke"],  # seals ride with the piston; the squeegee + its yoke share their own drive; + procedural ChainColumn/SqueegeeChain
    "parts": PARTS,
}
with open(os.path.join(OUTDIR, "hivecell.json"), "w") as f:
    json.dump(manifest, f, indent=2)
print("manifest:", manifest)

App.closeDocument(doc.Name)
