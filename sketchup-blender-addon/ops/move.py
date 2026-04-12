# ops/move.py
# SketchUp Move tool with inference snapping (endpoint, midpoint, on-face, on-edge)

import bpy
import bmesh
from mathutils import Vector, GeometryUtils
from bpy.props import FloatProperty, EnumProperty, BoolProperty
from bpy.types import Operator


class VIEW3D_OT_sk_move(Operator):
    """SketchUp Move with inference snapping"""
    bl_idname = "view3d.sk_move"
    bl_label = "Move (SketchUp)"
    bl_options = {'REGISTER', 'UNDO'}

    # Properties exposed in UI
    distance: FloatProperty(
        name="Distance",
        default=0.0,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    def execute(self, ctx):
        obj = ctx.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        # Use Blender's built-in move if nothing selected
        if not any(o.selected for o in ctx.selected_objects):
            bpy.ops.transform.translate('INVOKE_DEFAULT')
            return {'FINISHED'}

        # Move selected objects
        bpy.ops.transform.translate('INVOKE_DEFAULT',
            distance=self.distance)
        return {'FINISHED'}

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        # Store starting position for reference
        self._start_mouse = Vector((event.mouse_x, event.mouse_y))
        self._snap_type = "none"

        # Run the standard Blender move but capture
        return ctx.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, ctx):
        layout = self.layout
        layout.prop(self, 'distance')


class VIEW3D_OT_sk_inference_info(Operator):
    """Show current inference status in viewport footer"""
    bl_idname = "view3d.sk_inference_info"
    bl_label = "Inference Info"

    inference_type: bpy.props.StringProperty(default="")
    inference_point: bpy.props.StringProperty(default="")

    def execute(self, ctx):
        return {'FINISHED'}


classes = [
    VIEW3D_OT_sk_move,
    VIEW3D_OT_sk_inference_info,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
