"""SF4 pin-relief check -- does a power-loss pin relieve passively? (ADR-0009)

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/pin_relief.py

Scenario (FMEA F3): SF1 mis-detects an occupant, the piston pins them, THEN power
is lost. ADR-0009 makes the drive back-drivable in the occupant zone so the pin
should relieve passively. But the SF3 wiper seal adds a large, roughly-constant
DRAG that opposes any motion -- including the tissue recoil trying to push the
piston back. This script asks: can the pin relieve to a safe force on its own, or
is a stored-energy return element required?

Key physics (model-independent): with the drive dead, the piston backs off only
while the tissue reaction exceeds the seal drag. It STALLS when tissue force ==
seal drag. So without a return element the residual pin force cannot fall below
the seal drag, whatever the tissue stiffness. The verdict therefore hinges on
seal drag vs. a safe sustained contact force.

All ASSUMPTIONS are constants below and clearly flagged (seal drag and the
biomechanics numbers are the biggest unknowns).
"""
import math
import FreeCAD as App

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"

# --- assumptions (refine with real data / tests) ---------------------------
RHO_SS = 8000.0           # kg/m^3  stainless steel
G = 9.81                  # m/s^2
MU_GUIDE = 0.01           # low-friction linear guidance / wear rings
SEAL_DRAG_PER_M = 150.0   # N per metre of seal lip (per lip; BIGGEST unknown)
LIGHT_WALL_MM = 6.0       # equivalent shell thickness for a lightweighted piston
SAFETY = 2.0              # design factor on actuator force (matches actuator_sizing)
ETA = 0.5                 # drivetrain efficiency (for the closing-force burden note)

# safety target + biomechanics (FLAGGED: first-order, not certified)
F_SAFE_SUSTAINED = 120.0  # N  target residual pin, = SF2 cap. NOTE: a safe
                          #    INDEFINITE clamp is likely lower -> conservative here.
RETURN_MARGIN = 1.3       # design margin on a return element
TISSUE_STIFFNESS = 30.0   # N/mm  representative soft-tissue stiffness (context only:
                          #    sets initial pin + relief distance, NOT the verdict)

doc = App.open(DOC)
sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet")
piston = doc.getObject("Piston")

# --- resisting force: seal drag (SF3) + guide friction ----------------------
area = piston.Shape.Area / 1e6                       # m^2
m_light = area * (LIGHT_WALL_MM / 1000.0) * RHO_SS   # kg
w = sheet.cavityWidth.Value - 2 * sheet.runningClearance.Value
h = sheet.interiorHeight.Value - 2 * sheet.runningClearance.Value
r = sheet.cornerRadius.Value - sheet.runningClearance.Value
perim = (2 * (w - 2 * r) + 2 * (h - 2 * r) + 2 * math.pi * r) / 1000.0  # m
lips = int(sheet.sealLipCount)

f_seal = SEAL_DRAG_PER_M * perim * lips
f_guide = MU_GUIDE * m_light * G
f_resist = f_seal + f_guide          # opposes any back-drive (horizontal: no gravity term)

# --- verdict 1: passive relief alone ---------------------------------------
# The piston stalls when tissue reaction == f_resist, so that is the residual pin.
residual_passive = f_resist          # floor on the pin with no return element
passive_ok = f_resist <= F_SAFE_SUSTAINED

# --- return element needed to fully unload the person -----------------------
# To keep backing off until tissue force == 0, the return force must exceed the
# resisting drag with no tissue help: F_return >= f_resist.
f_return = RETURN_MARGIN * f_resist

# --- cost: closing now also fights the return element -----------------------
# (Return element biases toward OPEN; the flush latch holds it off when closed.)
f_close_resist = f_seal + f_guide + f_return
f_close_design = SAFETY * f_close_resist

# --- sensitivity: seal drag that WOULD make passive relief safe -------------
drag_per_m_for_passive = (F_SAFE_SUSTAINED - f_guide) / (perim * lips)

# --- context: worst-case initial pin + relief distance ----------------------
# Worst case at power loss: drive at design force, net into tissue after seal drag.
f_drive_design = SAFETY * f_resist   # ~ actuator_sizing design force
f_pin_initial = max(f_drive_design - f_resist, 0.0)
relief_mm_to_floor = max(f_pin_initial - residual_passive, 0.0) / TISSUE_STIFFNESS

print("--- SF4 pin-relief check (first-order, ADR-0009) ---")
print(f"seal drag (SF3)      : {f_seal:8.0f} N   ({lips} lips x {perim:.2f} m @ {SEAL_DRAG_PER_M:.0f} N/m)")
print(f"guide friction       : {f_guide:8.1f} N")
print(f"resisting force      : {f_resist:8.0f} N   <-- back-drive must beat this")
print(f"safe sustained pin   : {F_SAFE_SUSTAINED:8.0f} N   (target residual; likely optimistic)")
print()
print(f"PASSIVE residual pin : {residual_passive:8.0f} N   (stalls when tissue == seal drag)")
print(f"passive relief safe? : {str(passive_ok):>8s}   "
      f"({'ok' if passive_ok else 'NO -- residual is ~%.0fx the safe force' % (residual_passive / F_SAFE_SUSTAINED)})")
print()
print(f"=> return element    : {f_return:8.0f} N   (>= resisting x{RETURN_MARGIN:.1f}, to fully unload)")
print(f"   closing burden    : {f_close_resist:8.0f} N resistive -> {f_close_design:8.0f} N design (x{SAFETY:.0f})")
print(f"   (vs {SAFETY * f_resist:.0f} N design without a return element)")
print()
print(f"OR reduce seal drag  : <= {drag_per_m_for_passive:5.1f} N/m  would make passive relief safe")
print(f"   (assumed {SEAL_DRAG_PER_M:.0f} N/m; a >{SEAL_DRAG_PER_M / max(drag_per_m_for_passive, 1e-6):.0f}x cut -- unlikely for a lip seal)")
print()
print(f"context: worst initial pin ~{f_pin_initial:.0f} N; passive backs off ~{relief_mm_to_floor:.0f} mm "
      f"to the {residual_passive:.0f} N floor (tissue k={TISSUE_STIFFNESS:.0f} N/mm, illustrative)")

App.closeDocument(doc.Name)
