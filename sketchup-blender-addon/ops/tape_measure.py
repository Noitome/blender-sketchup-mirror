# ops/tape_measure.py
# SketchUp Tape Measure tool — click two points, draw dashed line, show distance

import bpy
import bmesh
from mathutils import Vector
from bpy.types import Operator


class VIEW3D_OT_sk_tape_measure(Operator):
    """Click two points to measure the distance between them (SketchUp style)"""
    bl_idname = "view3d.sk_tape_measure"
    bl_label = "Tape Measure"
    bl_options = {'REGISTER', 'UNDO'}

    _p1 = None
    _p2 = None
    _face_normal = None
    _preview_obj = None
    _label_obj = None

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        wm.sk_active_tool = 'tape_measure'

        self._p1 = None
        self._p2 = None
        self._face_normal = None
        self._preview_obj = None
        self._label_obj = None

        ctx.window_manager.modal_handler_set(self)
        ctx.window.cursor_modal_set('CROSSHAIRS')
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if event.type == 'ESC':
            self._cleanup(ctx)
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
                self._finalize(ctx)
                ctx.window.cursor_modal_restore()
                return {'FINISHED'}

        if event.type == 'MOUSEMOVE' and self._p1:
            self._p2 = self._get_3d_pos(ctx, event)
            self._update_preview(ctx)
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

    def _update_preview(self, ctx):
        if not self._p1 or not self._p2:
            return

        self._cleanup_preview(ctx)

        dist = (self._p2 - self._p1).length
        if dist < 0.001:
            return

        mesh = bpy.data.meshes.new("TapeMeasurePreview")
        obj = bpy.data.objects.new("TapeMeasurePreview", mesh)
        ctx.collection.objects.link(obj)

        obj.display_type = 'WIRE'
        obj.color = (1.0, 0.8, 0.0, 1.0)

        bm = bmesh.new()
        v1 = bm.verts.new(self._p1)
        v2 = bm.verts.new(self._p2)
        edge = bm.edges.new([v1, v2])
        # Dash effect via limited edge loop segments baked into geometry
        bm.to_mesh(mesh)
        bm.free()

        # Store dashed look via cycles visibility hack — simple dashed via material
        mat = bpy.data.materials.new("TapeMeasureDashed")
        mat.use_nodes = True
        mat_nodes = mat.node_tree.nodes
        mat_links = mat.node_tree.links
        mat_nodes.clear()

        output = mat_nodes.new('ShaderNodeOutputMaterial')
        emission = mat_nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (1.0, 0.85, 0.0, 1.0)
        emission.inputs['Strength'].default_value = 2.0
        mat_links.new(emission.outputs['Emission'], output.inputs['Surface'])
        output.location = (300, 0)
        emission.location = (0, 0)

        obj.data.materials.append(mat)

        self._preview_obj = obj
        self._draw_label(ctx, dist, midpoint=True, temporary=True)

    def _finalize(self, ctx):
        if not self._p1 or not self._p2:
            return

        self._cleanup_preview(ctx)

        dist = (self._p2 - self._p1).length
        if dist < 0.001:
            return

        # Build dashed dashed-line mesh using segmented edges
        mesh = bpy.data.meshes.new("TapeMeasure")
        obj = bpy.data.objects.new("TapeMeasure", mesh)
        ctx.collection.objects.link(obj)

        obj.display_type = 'WIRE'
        obj.color = (1.0, 0.8, 0.0, 1.0)

        # Dashed look: create short segments along the line
        direction = (self._p2 - self._p1).normalized()
        dash_len = 0.05  # length of each visible dash (meters)
        gap_len = 0.03   # length of each gap
        total = dist
        t = 0.0
        dash = True

        bm = bmesh.new()
        verts = []
        while t < total:
            seg_len = dash_len if dash else gap_len
            seg_vec = direction * min(seg_len, total - t)
            p_start = self._p1 + direction * t
            p_end = p_start + seg_vec
            v1 = bm.verts.new(p_start)
            v2 = bm.verts.new(p_end)
            bm.edges.new([v1, v2])
            t += seg_len
            dash = not dash

        bm.to_mesh(mesh)
        bm.free()

        # Material
        mat = bpy.data.materials.new("TapeMeasureDashed")
        mat.use_nodes = True
        mat_nodes = mat.node_tree.nodes
        mat_links = mat.node_tree.links
        mat_nodes.clear()

        output = mat_nodes.new('ShaderNodeOutputMaterial')
        emission = mat_nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (1.0, 0.85, 0.0, 1.0)
        emission.inputs['Strength'].default_value = 2.0
        mat_links.new(emission.outputs['Emission'], output.inputs['Surface'])

        obj.data.materials.append(mat)

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Draw permanent label at midpoint
        self._draw_label(ctx, dist, midpoint=True, temporary=False)

        # Store last measurement
        try:
            bpy.types.Scene.sk_last_distance = dist
        except Exception:
            pass

        self.report({'INFO'}, f"Tape Measure: {dist:.4f}m")

    def _draw_label(self, ctx, dist, midpoint=True, temporary=False):
        p1 = self._p1
        p2 = self._p2
        if not p1 or not p2:
            return

        mid = (p1 + p2) * 0.5
        label_text = f"{dist:.4f} m"

        # Create empty as label anchor
        empty = bpy.data.objects.new(
            "TapeMeasureLabel" if not temporary else "TapeMeasureLabelPreview",
            None
        )
        empty.empty_display_type = 'PLAIN_TEXT'
        empty.empty_display_size = 0.3
        empty.location = mid
        empty.show_in_front = True
        empty.data = label_text  # not a real approach for empty text; use curve instead

        # Use a curve object for the label text
        curve_data = bpy.data.curves.new('TapeMeasureLabelCurve', type='FONT')
        curve_data.body = label_text
        curve_data.size = 0.2
        curve_data.align_x = 'CENTER'
        curve_data.align_y = 'CENTER'
        curve_data.space_character = 1.2

        curve_obj = bpy.data.objects.new(
            "TapeMeasureLabel" if not temporary else "TapeMeasureLabelPreview",
            curve_data
        )
        curve_obj.location = mid
        curve_obj.show_in_front = True
        # Orient label to face camera
        try:
            region = ctx.region
            rv3d = region.data
            curve_obj.rotation_euler = rv3d.view_rotation.to_euler()
        except Exception:
            pass

        ctx.collection.objects.link(curve_obj)

        if temporary:
            self._label_obj = curve_obj
        else:
            # Select it
            curve_obj.select_set(True)
            bpy.context.view_layer.objects.active = curve_obj

    def _cleanup_preview(self, ctx):
        if self._preview_obj:
            try:
                ctx.collection.objects.unlink(self._preview_obj)
                bpy.data.objects.remove(self._preview_obj, do_unlink=True)
            except Exception:
                pass
            self._preview_obj = None
        if self._label_obj:
            try:
                ctx.collection.objects.unlink(self._label_obj)
                bpy.data.objects.remove(self._label_obj, do_unlink=True)
            except Exception:
                pass
            self._label_obj = None

    def _cleanup(self, ctx):
        self._cleanup_preview(ctx)


classes = [VIEW3D_OT_sk_tape_measure]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Initialise last-distance property on scene
    bpy.types.Scene.sk_last_distance = bpy.props.FloatProperty(
        name="SK Last Distance",
        description="Last measurement taken with the Tape Measure tool",
        default=0.0,
        subtype='DISTANCE',
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    try:
        del bpy.types.Scene.sk_last_distance
    except Exception:
        pass
