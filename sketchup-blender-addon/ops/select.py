# ops/select.py
# SketchUp Select tool

import bpy
from bpy.types import Operator


class VIEW3D_OT_sk_select(Operator):
    """SketchUp Select — left-click to select, shift+click to add/remove"""
    bl_idname = "view3d.sk_select"
    bl_label = "Select"
    bl_options = {'REGISTER'}

    def execute(self, ctx):
        wm = ctx.window_manager
        wm.sk_active_tool = 'select'

        # Just activate Blender's native select
        # The user clicks in the viewport normally
        return {'FINISHED'}

    def invoke(self, ctx, event):
        wm = ctx.window_manager
        wm.sk_active_tool = 'select'
        return {'FINISHED'}


classes = [VIEW3D_OT_sk_select]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
