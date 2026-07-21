# HiveCell

Modular public sleeping infrastructure. Each cell is a recessed cavity in a large
wall that provides one clean, safe overnight sleeping space. When unavailable, the
cavity retracts into the wall until the public face is flush, moving the sleeping
surface into a hidden service area for automated cleaning.

Design priorities (in order): vandal resistance, hygiene, reliability, low
maintenance, low energy, low cost, simplicity, easy servicing, long lifetime.
Comfort is intentionally low priority.

## Mechanism

**True syringe (Option B):** a single piston moves inside a fixed tube (barrel).
Retracted, the piston is the floor/back of an open sleeping capsule. Advanced, its
own face becomes the flush public wall — no separate door. The sweep of the piston
performs cleaning and seals the cavity on the hidden service side.

## Software stack

| Tool     | Role                                    |
|----------|-----------------------------------------|
| FreeCAD  | Mechanical design (parametric, source of truth) |
| Godot    | Motion simulation & digital twin        |
| Blender  | Rendering & presentation (later only)   |
| Git      | Version control                         |

## Layout

- `cad/`     — FreeCAD models (parametric)
- `docs/`    — engineering notes, calculations
- `godot/`   — simulation / digital twin project
- `blender/` — rendering assets (later)
- `docs/DECISIONS.md` — engineering decision log (read this first)
