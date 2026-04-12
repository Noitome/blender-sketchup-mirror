# ops/offset.py
# SketchUp Offset tool — offset edges/faces by a distance

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty
from bpy.types import Operator


class VIEW3D_OT_sk_offset(Operator):
    """Offset selected edges or faces by a distance"""
    bl_idname = "view3d.sk_offset"
    bl_label = "Offset"
    bl_options = {'REGISTER', 'UNDO'}

    distance: FloatProperty(
        name="Offset Distance",
        default=0.1,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    def execute(self, ctx):
        obj = ctx.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object")
            return {'CANCELLED'}

        was_edit = obj.mode == 'EDIT'
        if not was_edit:
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        selected_edges = [e for e in bm.edges if e.select]
        selected_faces = [f for f in bm.faces if f.select]

        if selected_edges:
            # Offset edges — push them outward along their average normal
            for e in selected_edges:
                n1 = e.verts[0].normal
                n2 = e.verts[1].normal
                avg_n = (n1 + n2).normalized()
                e.verts[0].co += avg_n * self.distance
                e.verts[1].co += avg_n * self.distance
            bmesh.update_edit_mesh(obj.data)
            self.report({'INFO'}, f"Offset {len(selected_edges)} edge(s) by {self.distance:.3f}m")

        elif selected_faces:
            # Offset faces — push along normal
            for f in selected_faces:
                normal = f.normal
                for v in f.verts:
                    v.co += normal * self.distance
            bmesh.update_edit_mesh(obj.data)
            self.report({'INFO'}, f"Offset {len(selected_faces)} face(s) by {self.distance:.3f}m")

        else:
            self.report({'WARNING'}, "Select edges or faces to offset")
            return {'CANCELLED'}

        if not was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}

    def invoke(self, ctx, event):
        wm = ctx.window_manager
        wm.sk_active_tool = 'offset'
        return ctx.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, ctx):
        self.layout.prop(self, 'distance')


classes = [VIEW3D_OT_sk_offset]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
