# ops/line.py
# SketchUp Line tool — click two points to draw a line on a face

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty
from bpy.types import Operator


class VIEW3D_OT_sk_line(Operator):
    """Draw a line by clicking two points (SketchUp style)"""
    bl_idname = "view3d.sk_line"
    bl_label = "Line"
    bl_options = {'REGISTER', 'UNDO'}

    _p1 = None
    _p2 = None
    _face_normal = None

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        wm.sk_active_tool = 'line'

        self._p1 = None
        self._p2 = None
        ctx.window_manager.modal_handler_set(self)
        ctx.window.cursor_modal_set('CROSSHAIRS')
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if event.type == 'ESC':
            ctx.window.cursor_modal_restore()
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            p = self._get_3d_pos(ctx, event)
            if not p:
                return {'RUNNING_MODAL'}

            if self._p1 is None:
                self._p1 = p
                self._face_normal = self._get_view_normal(ctx)
                ctx.area.tag_redraw()
            else:
                self._p2 = p
                self._create_line(ctx)
                ctx.window.cursor_modal_restore()
                return {'FINISHED'}

        if event.type == 'MOUSEMOVE' and self._p1:
            self._p2 = self._get_3d_pos(ctx, event)
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def _get_3d_pos(self, ctx, event):
        region = ctx.region
        rv3d = region.data
        try:
            ray_dir = rv3d.view_rotation @ Vector((0, 0, -1))
            ray_origin = rv3d.view_location
            plane_normal = self._face_normal or Vector((0, 0, 1))
            plane_origin = self._p1 or Vector((0, 0, 0))
            denom = ray_dir.dot(plane_normal)
            if abs(denom) > 0.0001:
                t = (plane_origin - ray_origin).dot(plane_normal) / denom
                if t > 0:
                    return ray_origin + ray_dir * t
        except:
            pass
        return None

    def _get_view_normal(self, ctx):
        try:
            region = ctx.region
            rv3d = region.data
            return rv3d.view_rotation @ Vector((0, 0, 1))
        except:
            return Vector((0, 0, 1))

    def _create_line(self, ctx):
        if not self._p1 or not self._p2:
            return

        import math
        dist = (self._p2 - self._p1).length
        if dist < 0.001:
            return

        # Create edge/curve object
        mesh = bpy.data.meshes.new("Line")
        obj = bpy.data.objects.new("Line", mesh)
        ctx.collection.objects.link(obj)

        bm = bmesh.new()
        v1 = bm.verts.new(self._p1)
        v2 = bm.verts.new(self._p2)
        bm.edges.new([v1, v2])
        bm.to_mesh(mesh)
        bm.free()

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        self.report({'INFO'}, f"Line: {dist:.3f}m")


classes = [VIEW3D_OT_sk_line]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
