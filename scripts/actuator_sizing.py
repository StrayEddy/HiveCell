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
RETURN_MARGIN = 1.3      # SF4 return element vs. resisting force (ADR-0009/pin_relief.py)

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
lips = int(sheet.sealLipCount)   # SF3 wiper lips per piston (front + rear)

# forces -- each lip drags along the full perimeter, so total contact = perim*lips
f_seal = SEAL_DRAG_PER_M * perim * lips
f_fric = MU_GUIDE * m_light * G
f_res = f_seal + f_fric

# SF4 return element (ADR-0009 / pin_relief.py): a stored-energy spring biases the
# piston toward DEPLOYED so a power-loss pin relieves passively. It RESISTS closing
# (the drive fights it) and ASSISTS opening -- so the CLOSING stroke sizes the drive.
f_return = RETURN_MARGIN * f_res           # >= resisting, to fully unload a pin
f_close = f_res + f_return                  # closing: seal drag + guide + return spring
f_open = f_res - f_return                    # opening: spring-assisted (may be < 0)
f_design = SAFETY * f_close                  # size on the demanding (closing) stroke

# speed / power / energy (closing is the demanding stroke)
v = (sheet.stroke.Value / 1000.0) / RETRACT_S      # m/s
p_mech = f_close * v
p_elec = p_mech / ETA
energy_wh = p_elec * RETRACT_S / 3600.0

print("--- actuator sizing (first-order) ---")
print(f"piston mass  SOLID : {m_solid:8.0f} kg   <-- reality check: MUST lightweight")
print(f"piston mass  light : {m_light:8.0f} kg   (~{LIGHT_WALL_MM:.0f} mm shell estimate)")
print(f"seal perimeter     : {perim:8.2f} m   ({lips} lips -> {perim * lips:.2f} m contact)")
print(f"force seal drag    : {f_seal:8.0f} N   (@ {SEAL_DRAG_PER_M:.0f} N/m x {lips} lips)")
print(f"force guide fric   : {f_fric:8.1f} N   (mu={MU_GUIDE})")
print(f"force resistive    : {f_res:8.0f} N   (seal drag + guide)")
print(f"SF4 return spring  : {f_return:8.0f} N   (biases toward deployed; ADR-0009)")
print(f"force CLOSE resist : {f_close:8.0f} N   (drive fights seal drag + return spring)")
print(f"force OPEN  resist : {f_open:8.0f} N   (spring-assisted; <0 => spring drives, drive brakes)")
print(f"force DESIGN (x{SAFETY:.0f}): {f_design:8.0f} N   <-- pick actuator >= this (closing stroke)")
print(f"  (was {SAFETY * f_res:.0f} N before the SF4 return element)")
print(f"travel speed       : {v * 1000:8.2f} mm/s  ({v:.5f} m/s)")
print(f"power  mechanical  : {p_mech:8.1f} W")
print(f"power  electrical  : {p_elec:8.1f} W   (eta={ETA})")
print(f"energy per stroke  : {energy_wh:8.2f} Wh")

App.closeDocument(doc.Name)
