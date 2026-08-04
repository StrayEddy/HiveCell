"""Seal-drag sensitivity sweep -- pre-compute the decision the bench test informs.

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/seal_drag_sweep.py

Seal drag (SF3) is the master unknown, estimated across ~16-700 N/m (per lip).
Rather than wait for the measurement, this sweeps SEAL_DRAG_PER_M across that whole
range through the SAME force model as actuator_sizing.py and pin_relief.py, and
prints how the actuator, the SF4 return spring, energy, and the drive-architecture
decision (ADR-0010) change. Once the bench test (docs/seal_drag_bench_test.md)
returns a number, the design branch is already a lookup in the table below.

Formulas + constants MIRROR actuator_sizing.py / pin_relief.py (those remain the
source of truth). Cross-check: at 150 N/m this reproduces ~1206 N resisting and
the ~13 N/m passive-relief threshold documented in ADR-0009/0011.
"""
import math
import FreeCAD as App

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"

# --- constants (identical to actuator_sizing.py / pin_relief.py) -------------
RHO_SS = 8000.0           # kg/m^3  stainless steel
G = 9.81                  # m/s^2
MU_GUIDE = 0.01           # low-friction linear guidance / wear rings
RETRACT_S = 600.0         # s   ~10 min retraction requirement
SAFETY = 2.0              # design safety factor on force
ETA = 0.5                 # drivetrain efficiency
LIGHT_WALL_MM = 6.0       # equivalent shell thickness for a lightweighted piston
RETURN_MARGIN = 1.3       # SF4 return element vs. resisting force (ADR-0009)
F_SAFE_SUSTAINED = 100.0  # N   safe residual pin target (= SF2 cap; likely optimistic;
                          #     sourced: docs/force_limit_injury_data.md, ADR-0024)

# --- drag values to sweep (N/m per lip): the credible range + design landmarks
SWEEP = [10, 16, 25, 40, 60, 100, 150, 200, 300, 450, 700]

doc = App.open(DOC)
sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet")
piston = doc.getObject("Piston")

# geometry-derived constants (independent of seal drag) ----------------------
area = piston.Shape.Area / 1e6                       # m^2
m_light = area * (LIGHT_WALL_MM / 1000.0) * RHO_SS   # kg
w = sheet.cavityWidth.Value - 2 * sheet.runningClearance.Value
h = sheet.interiorHeight.Value - 2 * sheet.runningClearance.Value
r = sheet.cornerRadius.Value - sheet.runningClearance.Value
perim = (2 * (w - 2 * r) + 2 * (h - 2 * r) + 2 * math.pi * r) / 1000.0  # m
lips = int(sheet.sealLipCount)
contact = perim * lips                                # m of lip contact
f_guide = MU_GUIDE * m_light * G                      # N (constant)
stroke_m = sheet.stroke.Value / 1000.0
v = stroke_m / RETRACT_S                              # m/s

# the ONE physics-derived threshold: below this, passive relief alone is safe
drag_passive = (F_SAFE_SUSTAINED - f_guide) / contact

# engineering bands for the seal spec (grounded in seal_drag.py scenarios):
#   ~40 = low-friction target (ADR-0011); ~150 = dry lip nominal; ~300 = dry+grit
BAND_LOWFRICTION = 40.0
BAND_NOMINAL = 150.0
BAND_HIGH = 300.0


def force_chain(drag):
    f_seal = drag * contact
    f_res = f_seal + f_guide                       # resisting (seal + guide)
    f_return = RETURN_MARGIN * f_res               # SF4 return spring
    f_close = f_res + f_return                     # drive fights seal + spring
    f_design = SAFETY * f_close                    # actuator sizing target
    spring_kj = f_return * stroke_m / 1000.0       # stored energy (deploy must damp)
    energy_wh = (f_close * v / ETA) * RETRACT_S / 3600.0
    passive_ok = f_res <= F_SAFE_SUSTAINED
    return f_seal, f_res, f_return, f_design, spring_kj, energy_wh, passive_ok


def verdict(drag, passive_ok):
    if passive_ok:
        return "PASSIVE-OK: spring optional -> ADR-0010 likely NOT needed"
    if drag <= BAND_LOWFRICTION:
        return "LOW-FRICTION: light drive; ADR-0010 optional"
    if drag <= BAND_NOMINAL:
        return "NOMINAL: spring mandatory; ADR-0010 warranted"
    if drag <= BAND_HIGH:
        return "HIGH: big spring/forces; ADR-0010 strongly warranted; fix seal"
    return "SEVERE: forces 2-4x; rework mechanism (interference/lips/seal tech)"


print("=== seal-drag sensitivity sweep (SF3 -> everything) ===")
print(f"geometry: perimeter {perim:.2f} m x {lips} lips = {contact:.2f} m contact; "
      f"light piston {m_light:.0f} kg; guide friction {f_guide:.0f} N; stroke {stroke_m:.2f} m")
print(f"HARD threshold: seal drag <= {drag_passive:.1f} N/m makes PASSIVE fail-open relief "
      f"safe on its own (no mandatory return spring) -> ADR-0010's premise falls away.")
print(f"bench test target: docs/seal_drag_bench_test.md  (measures N/m per lip)\n")

hdr = f"{'N/m':>5} {'seal N':>7} {'resist N':>8} {'spring N':>8} {'design N':>8} " \
      f"{'spring kJ':>9} {'Wh':>5} {'passive?':>8}  decision"
print(hdr)
print("-" * len(hdr))
for drag in SWEEP:
    f_seal, f_res, f_return, f_design, spring_kj, energy_wh, passive_ok = force_chain(drag)
    print(f"{drag:5.0f} {f_seal:7.0f} {f_res:8.0f} {f_return:8.0f} {f_design:8.0f} "
          f"{spring_kj:9.2f} {energy_wh:5.2f} {str(passive_ok):>8}  {verdict(drag, passive_ok)}")

print()
print("=== decision map (what the measured number will mean) ===")
print(f"  drag <= {drag_passive:4.1f} N/m : passive relief safe; SF4 spring minimal/none;")
print(f"                    a simple back-drivable drive suffices -> ADR-0010 likely moot.")
print(f"  {drag_passive:4.1f}-{BAND_LOWFRICTION:.0f} N/m   : low-friction regime; modest spring; light actuator;")
print(f"                    ADR-0010 optional (nice-to-have, not forced).")
print(f"  {BAND_LOWFRICTION:.0f}-{BAND_NOMINAL:.0f} N/m    : full-stroke return spring mandatory -> reusing it as the")
print(f"                    opener (ADR-0010 single-acting tension-close) is warranted.")
print(f"  {BAND_NOMINAL:.0f}-{BAND_HIGH:.0f} N/m   : large forces + big stored energy (damper needed);")
print(f"                    ADR-0010 strongly warranted AND the seal spec must improve.")
print(f"  > {BAND_HIGH:.0f} N/m      : forces 2-4x the model; the mechanism assumptions need")
print(f"                    rework (cut interference, drop to one lip, change seal tech).")
print()
print("Next: run the bench test, read your measured N/m against the table, and set")
print("ADR-0010's status accordingly (proposed -> accepted/withdrawn). Sweep values")
print("feed straight from actuator_sizing.py / pin_relief.py via SEAL_DRAG_PER_M=<n>.")

App.closeDocument(doc.Name)
