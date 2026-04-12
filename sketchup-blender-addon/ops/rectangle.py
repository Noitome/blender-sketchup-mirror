# ops/rectangle.py
# SketchUp Rectangle tool — click two corners to draw a flat rectangle on a face

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty, EnumProperty
from bpy.types import Operator


class VIEW3D_OT_sk_rectangle(Operator):
    """Draw a rectangle by clicking two opposite corners (SketchUp style)"""
    bl_idname = "view3d.sk_rectangle"
    bl_label = "Rectangle"
    bl_options = {'REGISTER', 'UNDO'}

    width: FloatProperty(name="Width", default=1.0, subtype='DISTANCE', unit='LENGTH')
    height: FloatProperty(name="Height", default=1.0, subtype='DISTANCE', unit='LENGTH')

    _corner1 = None
    _corner2 = None
    _face_normal = None
    _obj = None

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        self._corner1 = None
        self._corner2 = None
        self._obj = None
        ctx.window_manager.modal_handler_set(self)
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if event.type == 'ESC':
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            pos = self._get_3d_pos(ctx, event)
            if not pos:
                return {'RUNNING_MODAL'}

            if self._corner1 is None:
                # First click — set corner 1
                self._corner1 = pos
                self._face_normal = self._get_face_normal(ctx, event)
                ctx.area.tag_redraw()
            else:
                # Second click — set corner 2 and create rectangle
                self._corner2 = pos
                self._create_rectangle(ctx)
                return {'FINISHED'}

        if event.type == 'MOUSEMOVE' and self._corner1:
            self._corner2 = self._get_3d_pos(ctx, event)
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def _get_3d_pos(self, ctx, event):
        """Get 3D position under cursor"""
        region = ctx.region
        rv3d = region.data

        # Ray cast from 3D view
        coord = (event.mouse_x, event.mouse_y)
        depsgraph = ctx.evaluated_depsgraph_get()

        try:
            # Get ray direction from view
            ray_dir = rv3d.view_rotation @ Vector((0, 0, -1))
            ray_origin = rv3d.view_location

            # Find intersection with ground plane (z=0) or selected face
            plane_normal = self._face_normal if self._face_normal else Vector((0, 0, 1))
            plane_origin = self._corner1 if self._corner1 else Vector((0, 0, 0))

            # Ray-plane intersection
            denom = ray_dir.dot(plane_normal)
            if abs(denom) > 0.0001:
                t = (plane_origin - ray_origin).dot(plane_normal) / denom
                if t > 0:
                    return ray_origin + ray_dir * t
        except:
            pass

        return None

    def _get_face_normal(self, ctx, event):
        """Get normal of face under cursor"""
        obj = ctx.active_object
        if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            for f in bm.faces:
                if f.select:
                    return f.normal.copy()
        return Vector((0, 0, 1))

    def _create_rectangle(self, ctx):
        """Create a rectangle mesh from two corners"""
        if not self._corner1 or not self._corner2:
            return

        p1 = self._corner1
        p2 = self._corner2

        # Create rectangle in XY plane, then orient to face normal
        dx = (p2 - p1)
        w = dx.length
        dx_norm = dx.normalized()

        # Find perpendicular in plane of face
        normal = self._face_normal if self._face_normal else Vector((0, 0, 1))
        dy_norm = normal.cross(dx_norm).normalized()
        dy = dy_norm * (abs(dx.y) if abs(dx.y) > abs(dx.x) else abs(dx.x)) * 0.5

        # Actually calculate height from the other axis
        # corner1 = p1, corner2 = p2, so p2-p1 is diagonal
        # We want a rectangle — the other corner points are:
        p3 = p1 + dy
        p4 = p2 + dy

        # Swap if dy direction is wrong (make it a proper rectangle)
        mid = (p1 + p2) * 0.5
        test_p3 = mid + dx_norm * w * 0.5 - dy_norm * w * 0.3
        test_p4 = mid - dx_norm * w * 0.5 - dy_norm * w * 0.3

        # Just use the diagonal approach — create 4 corners from 2
        # Rectangle corners:
        # p1 = bottom-left, p2 = top-right (diagonal)
        # p3 = bottom-right, p4 = top-left

        p3 = Vector((p2.x, p1.y, p1.z))  # Assume axis-aligned for simplicity
        p4 = Vector((p1.x, p2.y, p2.z))

        # Create mesh
        mesh = bpy.data.meshes.new("Rectangle")
        obj = bpy.data.objects.new("Rectangle", mesh)
        ctx.collection.objects.link(obj)

        bm = bmesh.new()
        v1 = bm.verts.new(p1)
        v2 = bm.verts.new(p2)
        v3 = bm.verts.new(p3)
        v4 = bm.verts.new(p4)

        bm.faces.new([v1, v2, v3, v4])
        bm.to_mesh(mesh)
        bm.free()

        # Set active
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        self.report({'INFO'}, f"Rectangle: {w:.2f}m x {abs(p2.y - p1.y):.2f}m")


classes = [VIEW3D_OT_sk_rectangle]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
