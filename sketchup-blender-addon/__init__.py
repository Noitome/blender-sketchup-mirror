# __init__.py
# SketchUp 2026 Workflow Addon for Blender 4.x
# Left-drag orbit, shift-drag pan, right-click menu, push-pull, follow-me

bl_info = {
    "name": "SketchUp 2026 Workflow",
    "author": "Horizon",
    "version": (0, 2, 0),
    "blender": (5, 0, 0),
    "category": "3D View",
    "description": "SketchUp 2026-style navigation and tools: left-drag orbit, push-pull, follow-me, inference snap, context menu",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
from . import ops, ui, utils


def register():
    ops.register()
    ui.register()
    utils.register()
    print("[SK 2026] SketchUp 2026 Workflow loaded — Shift+; to enable SK Mode")


def unregister():
    utils.unregister()
    ui.unregister()
    ops.unregister()
    print("[SK 2026] SketchUp 2026 Workflow unloaded")
