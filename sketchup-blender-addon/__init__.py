# SPDX-License-Identifier: MIT
# SketchUp Navigation & Workflow Addon for Blender 4.x
# Mimics SketchUp's interface and interaction model

bl_info = {
    "name": "SketchUp Workflow",
    "author": "Horizon",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "3D View",
    "description": "SketchUp-style navigation and workflow: left-drag orbit, push-pull, follow-me, inference snapping",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
from . import ops, ui, utils

modules = [ops, ui, utils]


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
