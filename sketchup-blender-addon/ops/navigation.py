# ops/navigation.py
# SketchUp-style navigation: left-drag orbits, right-drag pans, scroll zooms
# Overrides Blender's default navigation in the 3D viewport

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
# SketchUp-style Orbit — left-mouse drag in 3D view
# ------------------------------------------------------------------

class VIEW3D_OT_sk_orbit(Operator):
    """SketchUp-style Orbit: left-drag in 3D view"""
    bl_idname = "view3d.sk_orbit"
    bl_label = "Orbit (SketchUp)"
    bl_options = {'REGISTER', 'GRAB_CURSOR', 'BLOCKING'}

    # Store initial state
    _prev_x = 0
    _prev_y = 0
    _active = False

    def invoke(self, ctx, event):
        # Only activate in 3D View
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        # Require left mouse
        if event.type != 'LEFTMOUSE':
            return {'PASS_THROUGH'}

        # If we're not in SketchUp mode, pass through
        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        ctx.window_manager.modal_handler_set(self)
        self._prev_x = event.mouse_prev_x
        self._prev_y = event.mouse_prev_y
        self._active = True

        # Capture cursor
        ctx.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if not self._active:
            return {'PASS_THROUGH'}

        # Right-click or Escape cancels
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._active = False
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._active = False
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            dx = event.mouse_x - self._prev_x
            dy = event.mouse_y - self._prev_y

            if dx != 0:
                bpy.ops.view3d.rotate({'INVOKE_DEFAULT': None}, 
                    use_vertical=True, 
                    use_horizontal=True,
                    mouse_x=event.mouse_x, 
                    mouse_y=event.mouse_y,
                    deltax=dx, 
                    deltay=dy)
            
            self._prev_x = event.mouse_x
            self._prev_y = event.mouse_y
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------
# SketchUp-style Pan — shift + left-drag OR middle-drag
# ------------------------------------------------------------------

class VIEW3D_OT_sk_pan(Operator):
    """SketchUp-style Pan"""
    bl_idname = "view3d.sk_pan"
    bl_label = "Pan (SketchUp)"
    bl_options = {'REGISTER', 'GRAB_CURSOR', 'BLOCKING'}

    _prev_x = 0
    _prev_y = 0
    _active = False

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        ctx.window_manager.modal_handler_set(self)
        self._prev_x = event.mouse_prev_x
        self._prev_y = event.mouse_prev_y
        self._active = True
        ctx.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if not self._active:
            return {'PASS_THROUGH'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._active = False
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._active = False
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            dx = event.mouse_x - self._prev_x
            dy = event.mouse_y - self._prev_y

            bpy.ops.view3d.move({'INVOKE_DEFAULT': None},
                deltax=dx * 0.5,
                deltay=-dy * 0.5)

            self._prev_x = event.mouse_x
            self._prev_y = event.mouse_y
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------
# Zoom — scroll wheel (already works like SketchUp)
# ------------------------------------------------------------------

class VIEW3D_OT_sk_zoom(Operator):
    """SketchUp-style Zoom — scroll wheel or Ctrl+drag"""
    bl_idname = "view3d.sk_zoom"
    bl_label = "Zoom (SketchUp)"
    bl_options = {'REGISTER', 'GRAB_CURSOR', 'BLOCKING'}

    _prev_x = 0
    _prev_y = 0
    _active = False

    def invoke(self, ctx, event):
        if ctx.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        wm = ctx.window_manager
        if not wm.sk_mode:
            return {'PASS_THROUGH'}

        ctx.window_manager.modal_handler_set(self)
        self._prev_x = event.mouse_x
        self._prev_y = event.mouse_y
        self._active = True
        return {'RUNNING_MODAL'}

    def modal(self, ctx, event):
        if not self._active:
            return {'PASS_THROUGH'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._active = False
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._active = False
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            dy = event.mouse_y - self._prev_y
            zoom_factor = 1.0 + dy * 0.005

            # Clamp to reasonable zoom range
            for area in ctx.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.lens = max(4, min(250, space.lens * zoom_factor))
                    area.tag_redraw()

            self._prev_y = event.mouse_y
            ctx.area.tag_redraw()

        return {'RUNNING_MODAL'}


# ------------------------------------------------------------------
# Enable/disable SketchUp mode
# ------------------------------------------------------------------

class VIEW3D_OT_toggle_sk_mode(Operator):
    """Toggle SketchUp navigation mode"""
    bl_idname = "view3d.toggle_sk_mode"
    bl_label = "Toggle SketchUp Mode"
    bl_options = {'REGISTER'}

    def execute(self, ctx):
        wm = ctx.window_manager
        wm.sk_mode = not getattr(wm, 'sk_mode', False)
        
        mode = "ON" if wm.sk_mode else "OFF"
        self.report({'INFO'}, f"SketchUp Mode {mode}")

        # Update status bar
        if ctx.area.type == 'VIEW_3D':
            ctx.area.tag_redraw()

        return {'FINISHED'}


# ------------------------------------------------------------------
# Window manager property to track mode
# ------------------------------------------------------------------

def sk_mode_get(self):
    return getattr(self, '_sk_mode', False)

def sk_mode_set(self, value):
    self['_sk_mode'] = value

# Register the property on WindowManager
bpy.types.WindowManager.sk_mode = bpy.props.BoolProperty(
    name="SketchUp Mode",
    description="Enable SketchUp-style navigation and tools",
    default=False,
    get=sk_mode_get,
    set=sk_mode_set,
)


classes = [
    VIEW3D_OT_sk_orbit,
    VIEW3D_OT_sk_pan,
    VIEW3D_OT_sk_zoom,
    VIEW3D_OT_toggle_sk_mode,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Set up keymap
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        # SketchUp mode toggle
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('view3d.toggle_sk_mode', type='SEMI_COLON', value='PRESS', shift=True)

    print("[SketchUp Nav] Registered navigation operators")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # Clean up keymap
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.get('3D View')
        if km:
            for kmi in list(km.keymap_items):
                if kmi.idname in ['view3d.toggle_sk_mode']:
                    km.keymap_items.remove(kmi)

    print("[SketchUp Nav] Unregistered navigation operators")
