# ops/transforms.py
# SketchUp-style Rotate and Scale tools

import bpy
from bpy.props import FloatProperty
from bpy.types import Operator


class VIEW3D_OT_sk_rotate(Operator):
    """SketchUp Rotate — invoke Blender's rotate"""
    bl_idname = "view3d.sk_rotate"
    bl_label = "Rotate"
    bl_options = {'REGISTER', 'UNDO'}

    angle: FloatProperty(
        name="Angle",
        default=0.0,
        subtype='ANGLE',
        unit='ROTATION',
    )

    def execute(self, ctx):
        wm = ctx.window_manager
        wm.sk_active_tool = 'rotate'
        return {'FINISHED'}

    def invoke(self, ctx, event):
        wm = ctx.window_manager
        wm.sk_active_tool = 'rotate'

        if ctx.selected_objects:
            # Delegate to Blender's rotate
            bpy.ops.transform.rotate('INVOKE_DEFAULT')
        else:
            self.report({'WARNING'}, "Select geometry first")
            return {'CANCELLED'}
        return {'FINISHED'}


class VIEW3D_OT_sk_scale(Operator):
    """SketchUp Scale — invoke Blender's scale"""
    bl_idname = "view3d.sk_scale"
    bl_label = "Scale"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        wm = ctx.window_manager
        wm.sk_active_tool = 'scale'
        return {'FINISHED'}

    def invoke(self, ctx, event):
        wm = ctx.window_manager
        wm.sk_active_tool = 'scale'

        if ctx.selected_objects:
            bpy.ops.transform.resize('INVOKE_DEFAULT')
        else:
            self.report({'WARNING'}, "Select geometry first")
            return {'CANCELLED'}
        return {'FINISHED'}


classes = [
    VIEW3D_OT_sk_rotate,
    VIEW3D_OT_sk_scale,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
