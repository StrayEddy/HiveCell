---
name: hivecell-design-change
description: Use when proposing or making a mechanism, geometry, sensor, or safety-function change to HiveCell — a new part, a parameter change in the FreeCAD model, a rework of an existing ADR's decision, or anything touching cad/, scripts/build_model.py, or a Design/Requirement row in docs/SAFETY.md or docs/TRACEABILITY.md.
---

# hivecell-design-change

## Overview
HiveCell treats every engineering decision as append-only history: an ADR in
`docs/DECISIONS.md`, then the parametric CAD (`scripts/build_model.py`, the
source of truth per ADR-0002), then the Godot digital twin kept in sync, and —
when a safety function is touched — the safety documents updated to match.
This skill is the ordered recipe those changes follow.

## When to use
Any time a change alters: the mechanism or a part's geometry/parameters, the
motion/actuation approach, a sensor suite or its placement, or any decision
that would need explaining to a future contributor. Not needed for pure
rendering/cinematic/site content changes with no design decision behind them.

## Procedure
1. **Write or amend the ADR first**, in `docs/DECISIONS.md` (append-only,
   newest at the bottom). Use the next sequential `ADR-NNNN` (4-digit, check
   the last one with `grep -o 'ADR-[0-9]\{4\}' docs/DECISIONS.md | sort -u | tail -1`).
   Follow the existing entry shape: `## ADR-NNNN — <short title>`, then
   **Date**, **Status** (Accepted / Proposed / Accepted, amends ADR-xxxx),
   **Context** (if amending prior work), **Decision**, **Why**, **Rejected
   alternatives**, **Accepted costs / constraints** or **Still open**, and
   **Follow-ups** (list what CAD/twin/docs work the ADR still requires —
   this becomes your checklist for steps 2-4).
2. **Update the parametric CAD.** Edit `scripts/build_model.py` (and any
   supporting script under `scripts/`, e.g. `actuator_sizing.py`,
   `seal_drag.py`, `pin_relief.py` if the decision changes forces/geometry
   those compute). Regenerate with:
   `flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/build_model.py`.
   Never hand-edit `cad/HiveCell.FCStd` in the GUI — it is a generated
   artifact and edits are overwritten on regenerate (ADR-0002). Commit this
   as its own `cad: ADR-NNNN — <what changed>` commit.
3. **Sync the Godot digital twin.** Re-export meshes with
   `flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/export_godot.py`
   (add any new part name to the `PARTS` list in that script first), then
   open/import in the Godot project under `godot/` so import metadata is
   generated, and commit that as its own follow-up commit, e.g.
   `godot: import metadata for <Part> mesh`. If the change affects simulated
   behavior (not just a static mesh), update the relevant twin script
   (`godot/safety_interlock.gd`, `godot/physics_demo.gd`,
   `godot/soft_profile.gd`, `godot/occupancy_fusion.gd`, etc.) in a `twin:`
   commit.
4. **If a safety function (SF1-SF5) or hazard (H1-H8) is affected**, update
   `docs/SAFETY.md` (hazard register / safety function / FMEA / open items)
   and `docs/TRACEABILITY.md` (the SR requirement row, §3 traceability
   matrix, and §6 gap register if a gap opens or closes). Cite the ADR number
   in both. Use a `safety:` commit prefix.
5. **Run the self-test before pushing**: `./scripts/run_selftest.sh` (see the
   `hivecell-safety-review` skill for the full pre-merge checklist — required
   whenever step 4 applied, and good practice otherwise).
6. Cross-reference: `docs/README.md`'s project-layout section and any diagram
   under `docs/` (e.g. cell-anatomy diagrams) that illustrates the changed
   part should be updated in the same change set so they don't go stale.

## Common mistakes
- Editing `cad/HiveCell.FCStd` by hand in the FreeCAD GUI instead of
  `scripts/build_model.py` — silently discarded on the next regenerate.
- Skipping the ADR and going straight to CAD/twin changes — the decision log
  is append-only and is expected to explain *why*, not just *what*.
- Forgetting the Godot re-sync commit — the repo's history shows this as its
  own commit (`godot: import metadata for <Part> mesh`) separate from the CAD
  commit; don't fold it silently into the CAD commit or skip it.
- Touching a safety function's geometry/logic without updating
  `docs/SAFETY.md` / `docs/TRACEABILITY.md` — this breaks the traceability
  chain and the §3 hazard-coverage check in `TRACEABILITY.md`.
- Renumbering or reusing an ADR number — IDs in `DECISIONS.md` and SR IDs in
  `TRACEABILITY.md` are stable and never renumbered.
