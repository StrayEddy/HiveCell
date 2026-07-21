"""Actuator sizing for HiveCell -- first-order numbers (reproducible).

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/actuator_sizing.py

Horizontal, very slow motion => inertia negligible, gravity carried by the
guidance. Actuator fights seal drag + guide friction only. All ASSUMPTIONS are
constants below and clearly the biggest unknowns (esp. seal drag); refine later.
"""
import math
import FreeCAD as App

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"

# --- assumptions (refine with real data / tests) ---------------------------
RHO_SS = 8000.0          # kg/m^3  stainless steel
G = 9.81                 # m/s^2
MU_GUIDE = 0.01          # low-friction linear guidance / wear rings
SEAL_DRAG_PER_M = 150.0  # N per metre of seal lip (moderate; BIGGEST unknown)
RETRACT_S = 600.0        # s   ~10 min retraction requirement
SAFETY = 2.0             # design safety factor on force
ETA = 0.5                # drivetrain efficiency (screw + gearing + motor)
LIGHT_WALL_MM = 6.0      # equivalent shell thickness for a lightweighted piston

doc = App.open(DOC)
sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet")
piston = doc.getObject("Piston")

# masses
v_solid = piston.Shape.Volume / 1e9            # m^3
m_solid = v_solid * RHO_SS                      # kg (the "reality check")
area = piston.Shape.Area / 1e6                  # m^2 total surface
m_light = area * (LIGHT_WALL_MM / 1000.0) * RHO_SS   # kg (thin-shell estimate)

# seal perimeter (rounded-rectangle piston cross-section)
w = sheet.cavityWidth.Value - 2 * sheet.runningClearance.Value
h = sheet.interiorHeight.Value - 2 * sheet.runningClearance.Value
r = sheet.cornerRadius.Value - sheet.runningClearance.Value
perim = (2 * (w - 2 * r) + 2 * (h - 2 * r) + 2 * math.pi * r) / 1000.0  # m

# forces
f_seal = SEAL_DRAG_PER_M * perim
f_fric = MU_GUIDE * m_light * G
f_res = f_seal + f_fric
f_design = SAFETY * f_res

# speed / power / energy
v = (sheet.stroke.Value / 1000.0) / RETRACT_S      # m/s
p_mech = f_res * v
p_elec = p_mech / ETA
energy_wh = p_elec * RETRACT_S / 3600.0

print("--- actuator sizing (first-order) ---")
print(f"piston mass  SOLID : {m_solid:8.0f} kg   <-- reality check: MUST lightweight")
print(f"piston mass  light : {m_light:8.0f} kg   (~{LIGHT_WALL_MM:.0f} mm shell estimate)")
print(f"seal perimeter     : {perim:8.2f} m")
print(f"force seal drag    : {f_seal:8.0f} N   (@ {SEAL_DRAG_PER_M:.0f} N/m)")
print(f"force guide fric   : {f_fric:8.1f} N   (mu={MU_GUIDE})")
print(f"force resistive    : {f_res:8.0f} N")
print(f"force DESIGN (x{SAFETY:.0f}): {f_design:8.0f} N   <-- pick actuator >= this")
print(f"travel speed       : {v * 1000:8.2f} mm/s  ({v:.5f} m/s)")
print(f"power  mechanical  : {p_mech:8.1f} W")
print(f"power  electrical  : {p_elec:8.1f} W   (eta={ETA})")
print(f"energy per stroke  : {energy_wh:8.2f} Wh")

App.closeDocument(doc.Name)
