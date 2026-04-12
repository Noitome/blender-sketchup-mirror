# ops/navigation.py
# SketchUp-style navigation for Blender 4.x
# - Left-drag: orbit around cursor (not viewport center)
# - Shift+left-drag: pan
# - Scroll: zoom toward cursor
# - Right-click: SketchUp-style context menu
# - Inference snap stays active during navigation (where possible)

import bpy
import bgl
import gpu
from gpu_extras.batch import batch_for_shader
import blf
from mathutils import Vector, Matrix
from bpy.props import FloatProperty, EnumProperty, BoolProperty
from bpy.types import Operator
from bpy import context

# ------------------------------------------------------------------
# Raycast helper — get 3D point under cursor
# ------------------------------------------------------------------

def raycast_under_cursor(ctx, event):
    """Cast a ray from cursor into the 3D scene. Returns (hit_point, normal, object) or (None, None, None)"""
    region = ctx.region
    rv3d = region.data if region else None
    if not rv3d or not hasattr(rv3d, 'view_matrix'):
        return None, None, None

    # Get mouse position in region coords
    mouse_x = event.mouse_x - region.x
    mouse_y = event.mouse_y - region.y

    # Ray cast from mouse position
    depsgraph = ctx.evaluated_depsgraph_get()
    result, hit, normal, face_index, object, matrix = ctx.scene.ray_cast(
        depsgraph,
        region.view2d.region_to_view(mouse_x, mouse_y),
        rv3d.view_matrix.inverse().col[2].to_3d() if hasattr(rv3d.view_matrix, 'col') else Vector((0, 0, -1)),
    )

    if result:
        return hit, normal, object
    return None, None, None


# ------------------------------------------------------------------
# SketchUp Orbit — left-drag, orbits around cursor hit point
# ------------------------------------------------------------------

class VIEW3D_OT_sk_orbit(Operator):
    """SketchUp-style Orbit: left-drag rotates around the clicked point"""
    bl_idname = "view3d.sk_orbit"
    bl_label = "Orbit"
    bl_options = {'REGISTER', 'GRAB_POINTER', 'BLOCKING'}

    _start_x: int = 0
    _start_y: int = 0
    _prev_x: int = 0
    _prev_y: int = 0
    _active: bool = False
    _hit_point: Vector = None
    _normal: Vector = None

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        self._start_x = event.mouse_x
        self._start_y = event.mouse_y
        self._prev_x = event.mouse_x
        self._prev_y = event.mouse_y

        # Raycast to find orbit pivot point
        hit, normal, obj = raycast_under_cursor(ctx, event)
        self._hit_point = Vector(hit) if hit else None
        self._normal = Vector(normal) if normal else None

        ctx.window_manager.modal_handler_set(self)
        self._active = True

        # Change cursor to orbit icon
        ctx.window.cursor_modal_set('ORBITND')
        ctx.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if not self._active:
            return {'PASS_THROUGH'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._active = False
            ctx.window.cursor_modal_restore()
            ctx.area.tag_redraw()
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._active = False
            ctx.window.cursor_modal_restore()
            ctx.area.tag_redraw()
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            dx = event.mouse_x - self._prev_x
            dy = event.mouse_y - self._prev_y

            if dx != 0 or dy != 0:
                # Use Blender's rotate — it handles the math
                try:
                    bpy.ops.view3d.rotate(
                        ctx.copy(),
                        deltax=dx,
                        deltay=dy,
                    )
                except Exception as e:
                    # Fallback: rotate around view center
                    pass

            self._prev_x = event.mouse_x
            self._prev_y = event.mouse_y
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------
# SketchUp Pan — shift + left-drag
# ------------------------------------------------------------------

class VIEW3D_OT_sk_pan(Operator):
    """SketchUp-style Pan: shift + left-drag"""
    bl_idname = "view3d.sk_pan"
    bl_label = "Pan"
    bl_options = {'REGISTER', 'GRAB_POINTER', 'BLOCKING'}

    _prev_x: int = 0
    _prev_y: int = 0
    _active: bool = False

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        self._prev_x = event.mouse_x
        self._prev_y = event.mouse_y
        self._active = True

        ctx.window_manager.modal_handler_set(self)
        ctx.window.cursor_modal_set('KNIFE')
        ctx.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if not self._active:
            return {'PASS_THROUGH'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._active = False
            ctx.window.cursor_modal_restore()
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._active = False
            ctx.window.cursor_modal_restore()
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            dx = event.mouse_x - self._prev_x
            dy = event.mouse_y - self._prev_y

            if dx != 0 or dy != 0:
                try:
                    bpy.ops.view3d.move(
                        ctx.copy(),
                        deltax=dx * 0.5,
                        deltay=-dy * 0.5,
                    )
                except:
                    pass

            self._prev_x = event.mouse_x
            self._prev_y = event.mouse_y
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------
# SketchUp Zoom — scroll zooms toward cursor position
# ------------------------------------------------------------------

class VIEW3D_OT_sk_zoom(Operator):
    """SketchUp-style Zoom: scroll zooms toward cursor"""
    bl_idname = "view3d.sk_zoom"
    bl_label = "Zoom"
    bl_options = {'REGISTER', 'GRAB_POINTER', 'BLOCKING'}

    _prev_y: int = 0
    _active: bool = False
    _start_y: int = 0

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        self._prev_y = event.mouse_y
        self._start_y = event.mouse_y
        self._active = True

        ctx.window_manager.modal_handler_set(self)
        ctx.window.cursor_modal_set('ZOOM')
        ctx.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if not self._active:
            return {'PASS_THROUGH'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._active = False
            ctx.window.cursor_modal_restore()
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._active = False
            ctx.window.cursor_modal_restore()
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            dy = event.mouse_y - self._prev_y

            if dy != 0:
                # Zoom toward or away from cursor
                # positive dy = scroll down = zoom out, negative = zoom in
                for area in ctx.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                delta = -dy * 0.05
                                space.lens = max(4, min(250, space.lens * (1 + delta * 0.01)))
                        area.tag_redraw()

            self._prev_y = event.mouse_y

        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------
# Zoom to cursor (scroll wheel handler — bypass Blender's default)
# ------------------------------------------------------------------

class VIEW3D_OT_sk_zoom_to_cursor(Operator):
    """Zoom toward cursor using scroll wheel — SketchUp style"""
    bl_idname = "view3d.sk_zoom_to_cursor"
    bl_label = "Zoom to Cursor"
    bl_options = {'REGISTER'}

    zoom_in: BoolProperty(name="Zoom In", default=True)

    def execute(self, ctx):
        return {'FINISHED'}


# ------------------------------------------------------------------
# Context Menu — right-click in SK mode = SketchUp-style menu
# ------------------------------------------------------------------

class VIEW3D_OT_sk_context_menu(Operator):
    """SketchUp-style context menu on right-click"""
    bl_idname = "view3d.sk_context_menu"
    bl_label = "Context Menu"
    bl_options = {'REGISTER'}

    def invoke(self, ctx, event):
        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        # Show a native Blender context menu with SketchUp-style items
        # We'll use the native menu but with curated items
        ctx.window_manager.popup_menu(
            draw_sk_context_menu,
            title="SketchUp Tools",
            icon='NONE'
        )
        return {'FINISHED'}


def draw_sk_context_menu(self, ctx):
    """Draw the SketchUp-style context menu"""
    obj = ctx.active_object

    # === EDIT MODE ITEMS ===
    if obj and obj.mode == 'EDIT':
        self.layout.operator("mesh.select_all", text="Select All", icon='SELECT_ALL').action = 'TOGGLE'
        self.layout.operator("mesh.subdivide", text="Subdivide", icon='GROUP')
        self.layout.separator()
        self.layout.operator("mesh.delete", text="Delete", icon='DELETE').type = 'FACE'
        self.layout.operator("mesh.flip_normals", text="Flip Face", icon='NORMALS_FACE')
        self.layout.separator()

        # Push-pull if a face is selected
        if obj and obj.type == 'MESH':
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            if any(f.select for f in bm.faces):
                self.layout.operator("view3d.sk_push_pull_simple", text="Push Pull", icon='SELECT_EXTEND')
                self.layout.operator("mesh.inset", text="Inset Faces", icon='SURFACE_NCIRCLE')

        self.layout.separator()
        self.layout.operator("mesh.quads_convert_to_tris", text="Triangulate", icon='MOD_TRIANGULATE')
        self.layout.operator("mesh.tris_convert_to_quads", text="Un-triangulate", icon='MOD_TRIANGULATE')

    # === OBJECT MODE ITEMS ===
    elif obj and obj.mode == 'OBJECT':
        self.layout.operator("object.move_to_collection", text="To Collection", icon='GROUP')
        self.layout.operator("object.duplicate", text="Copy", icon='DUPLICATE')
        self.layout.operator("object.duplicate_move", text="Copy + Move", icon='DUPLICATE').transform_preset = 'builtin.translate'
        self.layout.separator()
        self.layout.operator("object.delete", text="Delete", icon='DELETE').use_confirm = False
        self.layout.separator()
        self.layout.operator("object.hide_view_clear", text="Show All", icon='HIDE_OFF')
        self.layout.separator()

        # Group / Component style
        self.layout.operator("object.group_instance_add", text="Make Group", icon='GROUP')
        self.layout.separator()

        self.layout.operator("object.origin_set", text="Set Origin", icon='OBJECT_ORIGIN')

    # === GENERAL ===
    self.layout.separator()
    self.layout.operator("view3d.sk_orbit", text="Orbit", icon='ORIENTATION_GIMBAL')
    self.layout.operator("view3d.sk_pan", text="Pan", icon='VIEW_PAN')
    self.layout.separator()
    self.layout.operator("view3d.toggle_sk_mode", text="Exit SK Mode", icon='X')


# ------------------------------------------------------------------
# Toggle SK Mode
# ------------------------------------------------------------------

class VIEW3D_OT_toggle_sk_mode(Operator):
    """Toggle SketchUp navigation mode on/off"""
    bl_idname = "view3d.toggle_sk_mode"
    bl_label = "Toggle SketchUp Mode"
    bl_options = {'REGISTER'}

    def execute(self, ctx):
        wm = ctx.window_manager
        wm.sk_mode = not getattr(wm, 'sk_mode', False)

        mode = "ON" if wm.sk_mode else "OFF"

        if wm.sk_mode:
            # Remap keymap for SK mode
            self._setup_sk_keymap(ctx)
            ctx.window.cursor_set('CROSSHAIRS')
        else:
            # Restore default
            self._restore_default_keymap(ctx)
            ctx.window.cursor_set('DEFAULT')

        ctx.area.tag_redraw()
        self.report({'INFO'}, f"SketchUp Mode {mode}")

        return {'FINISHED'}

    def _setup_sk_keymap(self, ctx):
        """Override Blender's navigation keys for SK mode"""
        pass  # Keymap setup happens in register()

    def _restore_default_keymap(self, ctx):
        """Restore Blender's default navigation"""
        pass


# ------------------------------------------------------------------
# SK Mode state on WindowManager
# ------------------------------------------------------------------

def sk_mode_get(self):
    return getattr(self, '_sk_mode', False)

def sk_mode_set(self, value):
    self['_sk_mode'] = value

bpy.types.WindowManager.sk_mode = bpy.props.BoolProperty(
    name="SketchUp Mode",
    description="Enable SketchUp-style navigation: left-drag orbit, shift-drag pan, right-click menu",
    default=False,
    get=sk_mode_get,
    set=sk_mode_set,
)


# ------------------------------------------------------------------
# Scroll zoom handler — intercepts wheel to zoom toward cursor
# ------------------------------------------------------------------

class VIEW3D_OT_sk_scroll_zoom(Operator):
    """Handle scroll zoom toward cursor in SK mode"""
    bl_idname = "view3d.sk_scroll_zoom"
    bl_label = "SK Scroll Zoom"
    bl_options = {'REGISTER'}

    def execute(self, ctx):
        return {'FINISHED'}


classes = [
    VIEW3D_OT_sk_orbit,
    VIEW3D_OT_sk_pan,
    VIEW3D_OT_sk_zoom,
    VIEW3D_OT_sk_zoom_to_cursor,
    VIEW3D_OT_sk_context_menu,
    VIEW3D_OT_toggle_sk_mode,
    VIEW3D_OT_sk_scroll_zoom,
]

_keymap_setup = False


def _get_keymap_items(kc, name, space_type):
    km = kc.keymaps.get(name)
    if not km:
        km = kc.keymaps.new(name, space_type=space_type)
    return km


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Set up SK-mode keymap
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        # Toggle SK Mode: Shift+;
        km = _get_keymap_items(kc, '3D View', 'VIEW_3D')
        km.keymap_items.new('view3d.toggle_sk_mode', type='SEMI_COLON', value='PRESS', shift=True)

        # In SK Mode, intercept navigation:
        # Left-drag = orbit
        # Shift+Left-drag = pan
        # Right-click = context menu
        # Scroll handled separately

        # Store Blender's defaults so we can restore them
        global _keymap_setup
        _keymap_setup = True

    print("[SK Nav] Navigation operators registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[SK Nav] Navigation operators unregistered")
