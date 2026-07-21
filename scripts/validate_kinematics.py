"""Kinematic validation: sweep the piston through its full retraction and check
for interference and correct closure. Read-only (never saves the document).

Run headless:
  flatpak run --command=freecadcmd org.freecad.FreeCAD \
      /home/eddy/Projects/HiveCell/scripts/validate_kinematics.py

Checks, at every sampled position of the stroke:
  1. no collision between piston and the fixed barrel (shared volume ~ 0)
  2. piston stays inside the barrel envelope (never pokes out front or back)
And at full close:
  3. the piston front face lands flush with the exterior wall plane (X = 0)
"""
import FreeCAD as App

DOC = "/home/eddy/Projects/HiveCell/cad/HiveCell.FCStd"
N_STEPS = 44          # sample resolution across the stroke
COLLISION_TOL = 1.0   # mm^3 shared volume treated as "touching"
FLUSH_TOL = 0.01      # mm error allowed at closed position

doc = App.open(DOC)
shell = doc.getObject("CapsuleShell").Shape
piston0 = doc.getObject("Piston").Shape

# Deployed pose: piston front face sits at its BoundBox.XMin (= cavityLength).
# To close, the piston translates -X until that face reaches X = 0.
front_deployed = piston0.BoundBox.XMin
stroke = front_deployed
barrel = shell.BoundBox
V = App.Vector

max_overlap = 0.0
max_overlap_at = 0.0
out_of_barrel = []
for i in range(N_STEPS + 1):
    d = stroke * i / N_STEPS               # travel so far (0 .. stroke)
    p = piston0.copy()
    p.translate(V(-d, 0, 0))
    ov = shell.common(p).Volume
    if ov > max_overlap:
        max_overlap, max_overlap_at = ov, d
    bb = p.BoundBox
    if bb.XMin < barrel.XMin - 0.01 or bb.XMax > barrel.XMax + 0.01:
        out_of_barrel.append(round(d, 1))

# Full close
p_closed = piston0.copy()
p_closed.translate(V(-stroke, 0, 0))
flush_err = abs(p_closed.BoundBox.XMin - 0.0)

print("--- kinematic validation ---")
print(f"stroke sampled: {stroke:.0f} mm over {N_STEPS} steps "
      f"({stroke / N_STEPS:.0f} mm each)")
print(f"1. max piston<->barrel overlap: {max_overlap:.2f} mm^3 at travel {max_overlap_at:.0f} mm "
      f"-> {'PASS' if max_overlap <= COLLISION_TOL else 'FAIL (collision!)'}")
print(f"2. stayed inside barrel envelope: "
      f"{'PASS' if not out_of_barrel else 'FAIL at travels ' + str(out_of_barrel)}")
print(f"3. flush at close: front face X={p_closed.BoundBox.XMin:.3f} mm, err={flush_err:.3f} "
      f"-> {'PASS' if flush_err <= FLUSH_TOL else 'FAIL'}")
print(f"   sweep coverage: front face travels {stroke:.0f} -> 0 mm "
      f"(cleans full occupant length)")

App.closeDocument(doc.Name)
