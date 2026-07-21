"""Read and print all aliased parameters from HiveCell.FCStd (verification).

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/verify_params.py
"""
import FreeCAD as App

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"
doc = App.open(DOC)

sheet = next((o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet"), None)
if sheet is None:
    raise SystemExit("No spreadsheet found in document")

aliases = ["statureP95", "lengthClearance", "cavityLength", "shoulderP95",
           "floorWidth", "boreDiameter", "interiorHeight", "wallThickness", "stroke"]

print("--- HiveCell parameters (via FreeCAD API) ---")
for a in aliases:
    try:
        print(f"{a:16s} = {getattr(sheet, a)}")
    except AttributeError:
        print(f"{a:16s} = <missing alias>")

App.closeDocument(doc.Name)
