# ui/__init__.py
# SketchUp-style UI — minimal toolbar, clean panels

import bpy
from bpy.types import Panel


class VIEW3D_PT_sk_toolbar(Panel):
    """SketchUp-style vertical toolbar"""
    bl_label = "SketchUp Tools"
    bl_idname = "VIEW3D_PT_sk_toolbar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "SK"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        # Mode toggle
        layout.prop(wm, 'sk_mode', text="SK Mode", toggle=True)

        if wm.sk_mode:
            layout.separator()
            
            # Navigation (always available)
            col = layout.column(align=True)
            col.label(text="Navigate", icon='VIEW_PAN')
            op = col.operator('view3d.sk_pan', text='Pan', icon='VIEW_PAN')
            op = col.operator('view3d.sk_orbit', text='Orbit', icon='VIEW_ROTATE')
            op = col.operator('view3d.sk_zoom', text='Zoom', icon='VIEW_ZOOM')

            layout.separator()
            
            # Drawing tools
            col = layout.column(align=True)
            col.label(text="Draw", icon='STICKY_UVS_DISABLE')
            col.operator('view3d.sk_rectangle', text='Rectangle', icon='SEQ_STRIP_META')
            col.operator('view3d.sk_circle', text='Circle', icon='MESH_CIRCLE')

            layout.separator()

            # Modeling tools
            col = layout.column(align=True)
            col.label(text="Model", icon='SCULPTMODE_HLT')
            col.operator('view3d.sk_push_pull_simple', text='Push Pull', icon='SELECT_EXTEND')
            col.operator('view3d.sk_follow_me', text='Follow Me', icon='IPO_EASE_IN_OUT')
            col.operator('view3d.sk_move', text='Move', icon='TRANSFORM_MOVE')


class VIEW3D_PT_sk_options(Panel):
    """SketchUp-style options panel"""
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

        if not wm.sk_mode:
            layout.label(text="Enable SK Mode to use")
            return

        layout.prop(context.scene, 'sk_measurement_units', text="Units")
        layout.prop(context.scene, 'sk_inference_enabled', text="Inference Snap")


class VIEW3D_PT_sk_status(Panel):
    """Status bar info for SketchUp mode"""
    bl_label = ""
    bl_idname = "VIEW3D_PT_sk_status"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'FOOTER'
    bl_options = {'HIDE'}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        if wm.sk_mode:
            row = layout.row()
            row.label(text="[SketchUp Mode] LMB: Select | Shift+LMB: Pan | Scroll: Zoom | Tab: Push-Pull | M: Move")
        else:
            row = layout.row()
            row.label(text="Standard Blender Navigation")


# Register scene properties
def sk_measurement_units_get(self):
    return getattr(self, '_sk_measurement_units', 'METRIC')

def sk_measurement_units_set(self, value):
    self['_sk_measurement_units'] = value

bpy.types.Scene.sk_measurement_units = bpy.props.EnumProperty(
    name="Units",
    items=[
        ('METRIC', 'Metric (m, cm)', 'Use metric units'),
        ('IMPERIAL', 'Imperial (ft, in)', 'Use imperial units'),
    ],
    default='METRIC',
    get=sk_measurement_units_get,
    set=sk_measurement_units_set,
)

bpy.types.Scene.sk_inference_enabled = bpy.props.BoolProperty(
    name="Inference Snap",
    description="Enable SketchUp-style inference snapping",
    default=True,
)


classes = [
    VIEW3D_PT_sk_toolbar,
    VIEW3D_PT_sk_options,
    VIEW3D_PT_sk_status,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    print("[SketchUp UI] Registered UI panels")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    print("[SketchUp UI] Unregistered UI panels")
