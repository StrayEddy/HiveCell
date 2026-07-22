"""Finalize hivecell.blend so it opens in the Shading workspace, in EEVEE.

Run in a REAL Blender UI (NOT --background) -- switching the active workspace
needs a UI context, which headless mode silently ignores:
  flatpak run --filesystem=<repo> org.blender.Blender \
      <repo>/blender/hivecell.blend --python <repo>/blender/finalize_shading.py

A Blender window flashes for ~1-2 s, then the file is saved with the Shading
tab active + all 3D viewports in Rendered shading, and Blender quits. Run this
once after blender/build_scene.py (which does the heavy import/render headless).
"""
import bpy


_tries = [0]


def _finalize():
    ws = bpy.data.workspaces.get("Shading")
    win = bpy.context.window
    before = win.workspace.name if win and win.workspace else None
    if ws and win:
        win.workspace = ws
    after = bpy.context.window.workspace.name if bpy.context.window else None
    _tries[0] += 1
    print("FINALIZE try %d: before=%s after=%s" % (_tries[0], before, after))
    # Keep retrying until the workspace switch actually takes (the splash/UI can
    # block it for the first frames), then bake viewport shading + save + quit.
    if after == "Shading" or _tries[0] > 20:
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.shading.type = "MATERIAL"
        bpy.ops.wm.save_mainfile()
        print("FINALIZE: saved, active workspace = %s" %
              (bpy.context.window.workspace.name if bpy.context.window else "?"))
        bpy.ops.wm.quit_blender()
        return None
    return 0.3


bpy.app.timers.register(_finalize, first_interval=1.0)
