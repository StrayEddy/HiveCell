"""Seal-drag sanity check -- is the 150 N/m assumption realistic? (SF3)

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/seal_drag.py

actuator_sizing.py / pin_relief.py assume SEAL_DRAG_PER_M = 150 N per metre of
lip -- and it DOMINATES everything (design force, the SF4 return spring, energy).
This derives the drag from first principles instead, to bound it:

    drag per metre = mu * p_contact * contact_width           [N/m]
    total seal force = (drag per metre) * perimeter * lips     [N]

The friction coefficient is the big driver. Literature for DRY rubber-on-steel
reciprocating contact is HIGH -- mu ~ 1.0-1.4 (NBR in air 1.34-1.44; rubber-alu
~1.1) -- much higher than a lubricated hydraulic seal (~0.1-0.3). Our wiper is
DRY and in a gritty street environment, so the high end is a real risk.

All numbers are first-order ranges, clearly flagged. Sources noted at the bottom.
"""
import FreeCAD as App

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"
SEAL_DRAG_PER_M_ASSUMED = 150.0   # the current assumption we are checking

# --- scenarios: (label, mu, contact_pressure_MPa, contact_width_mm) ---------
# mu: dry rubber-steel ~1.0-1.4 (research); lubricated/PTFE much lower.
# p_contact: wiper lip contact pressure, interference-driven, ~0.2-1.0 MPa.
# contact_width: lip line-contact width ~0.2-0.5 mm.
SCENARIOS = [
    ("LOW  (PTFE-faced / lubricated, soft lip)", 0.4, 0.20, 0.20),
    ("NOMINAL (dry elastomer lip)",              1.0, 0.50, 0.30),
    ("HIGH (dry + grit, stiff lip)",             1.4, 1.00, 0.50),
]

doc = App.open(DOC)
sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet")

# seal perimeter (rounded-rectangle piston cross-section), same as actuator_sizing
import math
w = sheet.cavityWidth.Value - 2 * sheet.runningClearance.Value
h = sheet.interiorHeight.Value - 2 * sheet.runningClearance.Value
r = sheet.cornerRadius.Value - sheet.runningClearance.Value
perim = (2 * (w - 2 * r) + 2 * (h - 2 * r) + 2 * math.pi * r) / 1000.0  # m
lips = int(sheet.sealLipCount)

print("--- seal-drag first-principles check (SF3) ---")
print(f"perimeter {perim:.2f} m x {lips} lips = {perim * lips:.2f} m of lip contact")
print(f"assumption under test: {SEAL_DRAG_PER_M_ASSUMED:.0f} N/m  "
      f"-> {SEAL_DRAG_PER_M_ASSUMED * perim * lips:.0f} N total\n")
print(f"{'scenario':<42s}{'N/m':>7s}{'total N':>9s}{'vs 150':>8s}")
for label, mu, p_mpa, cw_mm in SCENARIOS:
    per_m = mu * (p_mpa * 1e6) * (cw_mm / 1000.0)        # N/m
    total = per_m * perim * lips                          # N
    ratio = per_m / SEAL_DRAG_PER_M_ASSUMED
    print(f"{label:<42s}{per_m:7.0f}{total:9.0f}{ratio:7.1f}x")

print()
print("verdict: 150 N/m is a plausible NOMINAL for a dry elastomer lip, but the")
print("credible range spans ~25-700 N/m. A dry, gritty, unlubricated street wiper")
print("can sit ABOVE 150 -> seal drag (hence design force + SF4 spring + energy) may")
print("be 2-4x worse than modelled. Everything scales with it, so the design should")
print("SPECIFY a low-friction seal (PTFE-faced / lubricated / brush) and/or fewer")
print("lips + less interference, and this number must be measured on a real sample.")

App.closeDocument(doc.Name)

# Sources (dry rubber-steel friction coefficients):
# - NBR in air/hydrogen mu 1.34-1.44; rubber-alu ~1.1 (reciprocating rig):
#   https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12845665/
# - O-ring / rubber friction under load: https://www.sciencedirect.com/science/article/pii/S0142941821003238
# - Lip-seal contact width/pressure profile: https://www.sciencedirect.com/science/article/abs/pii/S0301679X05002380
