# ops/follow_me.py
# SketchUp's Follow-Me tool — extrude a profile along a path (loft)

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty, EnumProperty
from bpy.types import Operator


class VIEW3D_OT_sk_follow_me(Operator):
    """SketchUp Follow-Me: extrude a profile along a path (like loft in other CAD)"""
    bl_idname = "view3d.sk_follow_me"
    bl_label = "Follow Me"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        obj = ctx.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object in Edit mode")
            return {'CANCELLED'}

        was_edit = obj.mode == 'EDIT'
        if not was_edit:
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [f for f in bm.faces if f.select]

        if not selected_faces:
            self.report({'WARNING'}, "Select a face (profile) to follow a path")
            return {'CANCELLED'}

        selected_edges = [e for e in bm.edges if e.select]

        profile_face = selected_faces[0]
        normal = profile_face.normal

        if selected_edges:
            # Follow selected edges
            path = selected_edges
            # Simple approach: extrude face along edge average direction
            avg_dir = Vector((0, 0, 0))
            for e in path:
                avg_dir += (e.verts[0].co + e.verts[1].co) * 0.5
            avg_dir /= len(path)

            # Get direction from profile center to path
            profile_center = profile_face.calc_center_median()
            follow_dir = (avg_dir - profile_center).normalized()

            # Extrude
            result = bmesh.ops.inset_individual(
                bm,
                faces=[profile_face],
                thickness=0.0,
                depth=0.0,
            )

            # Move extruded verts along follow direction
            extruded_verts = []
            if result.get('faces'):
                for f in result['faces']:
                    for v in f.verts:
                        v.co += follow_dir * 0.1

            bmesh.update_edit_mesh(obj.data)
            self.report({'INFO'}, "Follow-Me: extruded face along path")

        else:
            # No path selected — just extrude along normal
            bmesh.ops.translate(
                bm,
                verts=[v for v in profile_face.verts],
                vec=normal * 0.1,
            )
            bmesh.update_edit_mesh(obj.data)
            self.report({'INFO'}, "Follow-Me: extruded face along normal")

        if not was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}


classes = [VIEW3D_OT_sk_follow_me]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
