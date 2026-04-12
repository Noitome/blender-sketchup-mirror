# ops/push_pull.py
# SketchUp's signature Push-Pull tool — click a face, drag to extrude it
# Works on selected faces or objects

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty, EnumProperty
from bpy.types import Operator


class VIEW3D_OT_sk_push_pull(Operator):
    """SketchUp Push-Pull: click a face and drag to extrude it"""
    bl_idname = "view3d.sk_push_pull"
    bl_label = "Push Pull"
    bl_options = {'REGISTER', 'UNDO'}

    offset: FloatProperty(
        name="Offset",
        default=0.0,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    # Internal state
    _bm = None
    _face = None
    _vert = None
    _normal = Vector((0, 0, 0))
    _start_mouse = None
    _original_verts = []
    _extruded = False
    _obj = None

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        # Check we're in object mode or edit mode
        if ctx.active_object is None:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        # Store context
        self._start_mouse = Vector((event.mouse_x, event.mouse_y))
        self._obj = ctx.active_object
        self._ctx = ctx

        # Enter modal to track drag
        ctx.window_manager.modal_handler_set(self)
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if event.type == 'ESC':
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # On first click — select the face under cursor
            self._select_face(ctx, event)
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self._face:
            # On release — finish extrusion
            return self._finish_extrusion(ctx)

        if event.type == 'MOUSEMOVE' and self._face:
            self._update_extrusion(ctx, event)

        return {'RUNNING_MODAL'}

    def _select_face(self, ctx, event):
        """Raycast to find the face under the mouse"""
        import bpy
        from mathutils import Vector

        region = ctx.region
        rv3d = region.data
        coord = (event.mouse_x, event.mouse_y)

        # Cast ray from 3D view
        depsgraph = ctx.evaluated_depsgraph_get()
        hit, normal, face_index, object, matrix = ctx.scene.ray_cast(
            depsgraph,
            region.view2d.region_to_view(coord[0], coord[1]),
            rv3d.view_matrix.inverse().col[2].xyz if hasattr(rv3d, 'view_matrix') else Vector((0, 0, -1)),
            direction=rv3d.view_rotation @ Vector((0, 0, -1)) if hasattr(rv3d, 'view_rotation') else Vector((0, 0, -1)),
        )

        if not hit:
            # Fallback: use selected face from active object
            obj = ctx.active_object
            if obj and obj.type == 'MESH':
                if obj.mode == 'EDIT':
                    bm = bmesh.from_edit_mesh(obj.data)
                    selected_faces = [f for f in bm.faces if f.select]
                    if selected_faces:
                        self._face = selected_faces[0]
                        self._normal = self._face.normal.copy()
                        self._original_verts = [v.co.copy() for v in self._face.verts]
                        self._obj = obj
                        ctx.area.tag_redraw()
                        return

            self.report({'WARNING'}, "No face found under cursor")
            return

        # We hit something — get the face normal
        self._normal = normal

        # Convert hit location to object space
        obj_matrix_inv = object.matrix_world.inverted()
        hit_local = obj_matrix_inv @ hit

        # Find the closest face in the object
        if object.type == 'MESH' and object.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(object.data)
            self._obj = object

            # Find face closest to hit point
            best_dist = float('inf')
            best_face = None
            for f in bm.faces:
                center = f.calc_center_median()
                d = (center - hit_local).length
                if d < best_dist:
                    best_dist = d
                    best_face = f

            if best_face:
                self._face = best_face
                self._normal = best_face.normal.copy()
                self._original_verts = [v.co.copy() for v in best_face.verts]
                bmesh.update_edit_mesh(object.data)

        ctx.area.tag_redraw()

    def _update_extrusion(self, ctx, event):
        """Update the extrusion distance as mouse moves"""
        if not self._face or not self._obj:
            return

        # Get the view direction for depth-aware distance
        region = ctx.region
        rv3d = region.data
        view_dir = rv3d.view_rotation @ Vector((0, 0, -1)) if hasattr(rv3d, 'view_rotation') else Vector((0, 0, -1))

        # Calculate mouse movement in screen space
        dx = event.mouse_x - self._start_mouse.x
        dy = event.mouse_y - self._start_mouse.y
        dist = (dx + dy) * 0.001  # Scale factor

        # Project onto face normal (signed — pull in or push out)
        offset_vec = self._normal * dist

        self.offset = dist

        # Apply to edit mesh
        obj = self._obj
        if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
            face_verts = list(self._face.verts)
            face_indices = {v.index for v in face_verts}

            for v in bm.verts:
                if v.index in face_indices:
                    orig_idx = face_verts.index(v)
                    orig = self._original_verts[orig_idx]
                    v.co = orig + offset_vec

            bmesh.update_edit_mesh(obj.data)

        ctx.area.tag_redraw()

    def _finish_extrusion(self, ctx):
        """Finalize the extrusion"""
        if self._obj:
            # Push the extruded geometry slightly apart to prevent z-fighting
            pass

        self._face = None
        self._obj = None
        self._original_verts = []

        return {'FINISHED'}


class VIEW3D_OT_sk_push_pull_simple(Operator):
    """
    Simple push-pull: select a face, run operator, drag to extrude.
    Use this if the modal click-to-select is too complex.
    """
    bl_idname = "view3d.sk_push_pull_simple"
    bl_label = "Push Pull (Simple)"
    bl_options = {'REGISTER', 'UNDO'}

    distance: FloatProperty(
        name="Distance",
        default=0.0,
        subtype='DISTANCE',
        unit='LENGTH',
    )

    def execute(self, ctx):
        obj = ctx.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Select a mesh object")
            return {'CANCELLED'}

        # Enter edit mode if not already there
        was_in_edit = obj.mode == 'EDIT'
        if not was_in_edit:
            bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        selected_faces = [f for f in bm.faces if f.select]

        if not selected_faces:
            self.report({'WARNING'}, "Select one or more faces first")
            return {'CANCELLED'}

        # For each selected face, extrude along its normal
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        selected_face_indices = [f.index for f in bm.faces if f.select]

        # Deselect all to start clean
        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for f in bm.faces:
            f.select = False

        bm.select_flush(False)

        # Re-select original faces
        for idx in selected_face_indices:
            bm.faces[idx].select = True

        # Duplicate and separate if we want new geometry
        # For now, just extrude in place
        result = bmesh.ops.inset_individual(
            bm,
            faces=[bm.faces[i] for i in selected_face_indices],
            thickness=0.0,
            depth=0.0,
        )

        # Now extrude along normal
        extruded_faces = []
        for idx in selected_face_indices:
            f = bm.faces[idx]
            normal = f.normal
            # Get face center
            center = f.calc_center_median()

            # Extrude by moving vertices along normal
            for v in f.verts:
                v.co += normal * self.distance

        bmesh.update_edit_mesh(obj.data)

        if not was_in_edit:
            bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}


classes = [
    VIEW3D_OT_sk_push_pull,
    VIEW3D_OT_sk_push_pull_simple,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add to toolbar in 3D view header
    bpy.types.VIEW3D_HT_header.append(draw_sk_toolbar)

    print("[SketchUp Nav] Registered push-pull operators")


def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_sk_toolbar)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[SketchUp Nav] Unregistered push-pull operators")


def draw_sk_toolbar(self, context):
    layout = self.layout
    wm = context.window_manager

    # SketchUp mode toggle
    layout.separator()
    layout.prop(wm, 'sk_mode', text="SK Mode", toggle=True)

    if wm.sk_mode:
        layout.separator()
        
        # Tool buttons
        props = layout.operator('view3d.sk_push_pull_simple', text='Push Pull', icon='SELECT_EXTEND')
        props = layout.operator('view3d.sk_follow_me', text='Follow Me', icon='IPO_EASE_IN_OUT')
        props = layout.operator('view3d.sk_move', text='Move', icon='TRANSFORM_MOVE')
        props = layout.operator('view3d.sk_rectangle', text='Rectangle', icon='SEQ_STRIP_META')
        props = layout.operator('view3d.sk_circle', text='Circle', icon='MESH_CIRCLE')
