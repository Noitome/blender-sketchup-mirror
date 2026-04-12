# ui/__init__.py
# SketchUp 2026-style UI — minimal, clean, functional

import bpy
from bpy.types import Panel, Menu


# ------------------------------------------------------------------
# Active tool tracking
# ------------------------------------------------------------------

def sk_active_tool_get(self):
    return getattr(self, '_sk_active_tool', 'select')

def sk_active_tool_set(self, value):
    self['_sk_active_tool'] = value

bpy.types.WindowManager.sk_active_tool = bpy.props.StringProperty(
    name="SK Active Tool",
    default="select",
    get=sk_active_tool_get,
    set=sk_active_tool_set,
)


# ------------------------------------------------------------------
# SK Mode Toolbar — left sidebar, matches SketchUp 2026 aesthetic
# ------------------------------------------------------------------

class VIEW3D_PT_sk_toolbar(Panel):
    """The main SketchUp Tools panel — left sidebar, SK category"""
    bl_label = "SK Tools"
    bl_idname = "VIEW3D_PT_sk_toolbar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SK"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # --- SK Mode toggle at top ---
        row = layout.row(align=True)
        row.prop(wm, 'sk_mode', text="SK Mode", toggle=True, icon='OVERLAY')

        if not wm.sk_mode:
            # Disabled state hint
            box = layout.box()
            box.label(text="Press Shift+; or click", icon='INFO')
            box.label(text="to enable SK Mode")
            return

        layout.separator()

        # --- Tool sections, SketchUp 2026 style ---
        self._draw_select_tools(layout, wm)
        layout.separator()
        self._draw_draw_tools(layout, wm)
        layout.separator()
        self._draw_construct_tools(layout, wm)
        layout.separator()
        self._draw_modify_tools(layout, wm)

    def _draw_select_tools(self, layout, wm):
        """Select tools section"""
        col = layout.column(align=True)
        col.label(text="Select", icon='RESTRICT_SELECT_OFF')

        # Select
        op = col.operator('view3d.sk_select', text='Select',
                          icon='RESTRICT_SELECT_OFF',
                          depress=(wm.sk_active_tool == 'select'))
        op = col.operator('view3d.sk_orbit', text='Orbit',
                          icon='ORBIT_GIMBAL',
                          depress=(wm.sk_active_tool == 'orbit'))
        op = col.operator('view3d.sk_pan', text='Pan',
                          icon='VIEW_PAN',
                          depress=(wm.sk_active_tool == 'pan'))
        op = col.operator('view3d.sk_zoom', text='Zoom',
                          icon='VIEW_ZOOM',
                          depress=(wm.sk_active_tool == 'zoom'))

    def _draw_draw_tools(self, layout, wm):
        """Draw tools section"""
        col = layout.column(align=True)
        col.label(text="Draw", icon='STICKY_UVS_DISABLE')

        op = col.operator('view3d.sk_rectangle', text='Rectangle',
                          icon='SEQ_STRIP_META',
                          depress=(wm.sk_active_tool == 'rectangle'))
        op = col.operator('view3d.sk_circle', text='Circle',
                          icon='MESH_CIRCLE',
                          depress=(wm.sk_active_tool == 'circle'))
        op = col.operator('view3d.sk_line', text='Line',
                          icon='CURVE_PATH',
                          depress=(wm.sk_active_tool == 'line'))

    def _draw_construct_tools(self, layout, wm):
        """Construct tools section"""
        col = layout.column(align=True)
        col.label(text="Construct", icon='MOD_BUILD')

        op = col.operator('view3d.sk_push_pull_simple', text='Push Pull',
                          icon='SELECT_EXTEND',
                          depress=(wm.sk_active_tool == 'pushpull'))
        op = col.operator('view3d.sk_follow_me', text='Follow Me',
                          icon='IPO_EASE_IN_OUT',
                          depress=(wm.sk_active_tool == 'followme'))
        op = col.operator('view3d.sk_offset', text='Offset',
                          icon='MOD_OFFSET',
                          depress=(wm.sk_active_tool == 'offset'))

    def _draw_modify_tools(self, layout, wm):
        """Modify tools section"""
        col = layout.column(align=True)
        col.label(text="Modify", icon='MODIFIER')

        op = col.operator('view3d.sk_move', text='Move',
                          icon='TRANSFORM_MOVE',
                          depress=(wm.sk_active_tool == 'move'))
        op = col.operator('view3d.sk_rotate', text='Rotate',
                          icon='TRANSFORM_ROTATE',
                          depress=(wm.sk_active_tool == 'rotate'))
        op = col.operator('view3d.sk_scale', text='Scale',
                          icon='TRANSFORM_SCALE',
                          depress=(wm.sk_active_tool == 'scale'))


# ------------------------------------------------------------------
# SK Options Panel
# ------------------------------------------------------------------

class VIEW3D_PT_sk_options(Panel):
    """SK Mode options — units, snap, inference"""
    bl_label = "SK Options"
    bl_idname = "VIEW3D_PT_sk_options"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SK"
    bl_parent_id = "VIEW3D_PT_sk_toolbar"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        scene = context.scene

        if not wm.sk_mode:
            layout.label(text="Enable SK Mode to access options", icon='INFO')
            return

        # Units
        layout.prop(scene, 'sk_units', text="Units")

        # Inference snap
        layout.prop(scene, 'sk_inference_enabled', text="Inference Snap")
        layout.prop(scene, 'sk_inference_display', text="Show Inference Guides")

        layout.separator()

        # Camera / View
        box = layout.box()
        box.label(text="View", icon='VIEW3D')
        row = box.row()
        row.operator('view3d.view_all', text='Fit All', icon='VIEW_ALL')
        row.operator('view3d.view_center_cursor', text='Center', icon='VIEW_CENTER')

        row = box.row()
        row.operator('view3d.camera_to_view', text='To Camera', icon='CAMERA_DATA')
        row.operator('view3d.view_persportho', text='Persp/Ortho', icon='VIEW_PERSP')

        layout.separator()

        # Exit SK Mode
        layout.operator('view3d.toggle_sk_mode', text='Exit SK Mode', icon='X')


# ------------------------------------------------------------------
# SK Inference Status Panel — shows active snap type
# ------------------------------------------------------------------

class VIEW3D_PT_sk_inference(Panel):
    """Shows current inference snap status"""
    bl_label = "Inference"
    bl_idname = "VIEW3D_PT_sk_inference"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SK"
    bl_parent_id = "VIEW3D_PT_sk_options"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if not context.window_manager.sk_mode:
            return

        # Inference type display
        row = layout.row()
        row.label(text=f"Snap: {scene.sk_inference_type}", icon='SNAP_INCREMENT')

        row = layout.row()
        row.label(text=f"Last: {scene.sk_last_distance}", icon='DRIVER_DISTANCE')


# ------------------------------------------------------------------
# SK Status Footer — bottom of viewport, context-sensitive help
# ------------------------------------------------------------------

class VIEW3D_PT_sk_status(Panel):
    """SketchUp-style status bar at bottom of viewport"""
    bl_label = ""
    bl_idname = "VIEW3D_PT_sk_status"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'FOOTER'
    bl_options = {'HIDE'}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        scene = context.scene

        if wm.sk_mode:
            # Show SK mode status line
            row = layout.row(align=True)
            row.separator()
            row.label(text=f"[SK]  {scene.sk_status_text}", icon='INFO')

            # Show measurement if available
            if scene.sk_last_distance:
                row.separator(factor=2)
                row.label(text=f"{scene.sk_last_distance}", icon='DRIVER_DISTANCE')
        else:
            row = layout.row()
            row.separator()
            row.label(text="SK Mode: OFF  |  Shift+; to enable", icon='X')

    def draw_header(self, context):
        pass


# ------------------------------------------------------------------
# Scene properties for SK mode state
# ------------------------------------------------------------------

def sk_units_get(self):
    return getattr(self, '_sk_units', 'METRIC')

def sk_units_set(self, value):
    self['_sk_units'] = value

bpy.types.Scene.sk_units = bpy.props.EnumProperty(
    name="Units",
    items=[
        ('METRIC', 'Metric', 'Use metric units (m, cm)'),
        ('IMPERIAL', 'Imperial', 'Use imperial units (ft, in)'),
    ],
    default='METRIC',
    get=sk_units_get,
    set=sk_units_set,
)

bpy.types.Scene.sk_inference_enabled = bpy.props.BoolProperty(
    name="Inference Snap",
    description="Enable SketchUp-style inference snapping",
    default=True,
)

bpy.types.Scene.sk_inference_display = bpy.props.BoolProperty(
    name="Show Inference Guides",
    description="Draw inference lines and points in the viewport",
    default=True,
)

bpy.types.Scene.sk_inference_type = bpy.props.StringProperty(
    name="Inference Type",
    default="none",
)

bpy.types.Scene.sk_last_distance = bpy.props.StringProperty(
    name="Last Distance",
    default="",
)

bpy.types.Scene.sk_status_text = bpy.props.StringProperty(
    name="Status Text",
    default="Left-drag to orbit  |  Shift+drag to pan  |  Scroll to zoom  |  Right-click for menu",
)


classes = [
    VIEW3D_PT_sk_toolbar,
    VIEW3D_PT_sk_options,
    VIEW3D_PT_sk_inference,
    VIEW3D_PT_sk_status,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    print("[SK UI] UI panels registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[SK UI] UI panels unregistered")
