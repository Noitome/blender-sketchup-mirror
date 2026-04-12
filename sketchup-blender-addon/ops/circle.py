# ops/circle.py
# SketchUp Circle tool — click center, drag to set radius

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty, IntProperty
from bpy.types import Operator


class VIEW3D_OT_sk_circle(Operator):
    """Draw a circle by clicking center and dragging to set radius"""
    bl_idname = "view3d.sk_circle"
    bl_label = "Circle"
    bl_options = {'REGISTER', 'UNDO'}

    segments: IntProperty(
        name="Segments",
        default=32,
        min=3,
        max=256,
    )

    radius: FloatProperty(
        name="Radius",
        default=1.0,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    _center = None
    _edge_point = None
    _face_normal = None

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        self._center = None
        self._edge_point = None
        self._face_normal = None
        ctx.window_manager.modal_handler_set(self)
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if event.type == 'ESC':
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            pos = self._get_3d_pos(ctx, event)
            if not pos:
                return {'RUNNING_MODAL'}

            if self._center is None:
                self._center = pos
                self._face_normal = self._get_view_normal(ctx)
                ctx.area.tag_redraw()
            else:
                self._edge_point = pos
                self._create_circle(ctx)
                return {'FINISHED'}

        if event.type == 'MOUSEMOVE' and self._center:
            self._edge_point = self._get_3d_pos(ctx, event)
            if self._edge_point:
                self.radius = (self._edge_point - self._center).length
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def _get_3d_pos(self, ctx, event):
        """Get 3D position under cursor on ground plane"""
        region = ctx.region
        rv3d = region.data

        coord = (event.mouse_x, event.mouse_y)
        depsgraph = ctx.evaluated_depsgraph_get()

        try:
            ray_dir = rv3d.view_rotation @ Vector((0, 0, -1))
            ray_origin = rv3d.view_location

            plane_normal = self._face_normal if self._face_normal else Vector((0, 0, 1))
            plane_origin = self._center if self._center else Vector((0, 0, 0))

            denom = ray_dir.dot(plane_normal)
            if abs(denom) > 0.0001:
                t = (plane_origin - ray_origin).dot(plane_normal) / denom
                if t > 0:
                    return ray_origin + ray_dir * t
        except:
            pass

        return None

    def _get_view_normal(self, ctx):
        """Get the view's up direction as normal for the new face"""
        try:
            region = ctx.region
            rv3d = region.data
            return rv3d.view_rotation @ Vector((0, 0, 1))
        except:
            return Vector((0, 0, 1))

    def _create_circle(self, ctx):
        """Create a circle mesh"""
        if not self._center or not self._edge_point:
            return

        radius = (self._edge_point - self._center).length
        if radius < 0.001:
            return

        # Calculate tangent and bitangent in the plane of the circle
        normal = self._face_normal if self._face_normal else Vector((0, 0, 1))

        # Pick an arbitrary up vector not parallel to normal
        if abs(normal.z) < 0.9:
            ref = Vector((0, 0, 1))
        else:
            ref = Vector((1, 0, 0))

        tangent = normal.cross(ref).normalized()
        bitangent = normal.cross(tangent).normalized()

        # Generate vertices
        import math
        verts = []
        for i in range(self.segments):
            angle = 2 * math.pi * i / self.segments
            direction = tangent * math.cos(angle) + bitangent * math.sin(angle)
            v = self._center + direction * radius
            verts.append(v)

        # Create mesh
        mesh = bpy.data.meshes.new("Circle")
        obj = bpy.data.objects.new("Circle", mesh)
        ctx.collection.objects.link(obj)

        bm = bmesh.new()
        bm_verts = [bm.verts.new(v) for v in verts]
        bm.faces.new(bm_verts)
        bm.to_mesh(mesh)
        bm.free()

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        self.report({'INFO'}, f"Circle: radius {radius:.2f}m, {self.segments} segments")


classes = [VIEW3D_OT_sk_circle]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
