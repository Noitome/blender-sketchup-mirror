# SPDX-License-Identifier: MIT
# ops/inference_overlay.py
# SketchUp-style inference snapping overlay for Blender 5.x
# Uses gpu module only — bgl is removed in Blender 5.0

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import math
import mathutils
from mathutils import Vector

# ---------------------------------------------------------------------------
# Global inference state
# ---------------------------------------------------------------------------

class InferenceState:
    """Holds the current inference snap state across frames."""

    def __init__(self):
        self.active = False
        self.snap_type = ""          # "", "endpoint", "midpoint", "onedge", "onface"
        self.snap_point = Vector((0.0, 0.0, 0.0))
        self.snap_normal = Vector((0.0, 0.0, 1.0))
        self._prev_snap_point = None
        self._prev_snap_type = ""

    def set_snap(self, snap_type, snap_point, snap_normal=None):
        self.snap_type = snap_type
        self.snap_point = snap_point.copy()
        if snap_normal is not None:
            self.snap_normal = snap_normal.copy()
        else:
            self.snap_normal = Vector((0.0, 0.0, 1.0))

    def advance_previous(self):
        if self.snap_type:
            self._prev_snap_point = self.snap_point.copy()
            self._prev_snap_type = self.snap_type

    def get_prev(self):
        return self._prev_snap_point

    def clear(self):
        self.active = False
        self.snap_type = ""
        self.snap_point = Vector((0.0, 0.0, 0.0))
        self.snap_normal = Vector((0.0, 0.0, 1.0))
        self._prev_snap_point = None
        self._prev_snap_type = ""


inference_state = InferenceState()

# ---------------------------------------------------------------------------
# Shader — built once, reused
# ---------------------------------------------------------------------------

_shader = None


def get_shader():
    """Return cached gpu shader for point/line drawing."""
    global _shader
    if _shader is not None:
        return _shader

    _shader = gpu.types.GPUShader(
        # Vertex shader — 2D positions in clip space
        "vec2 positions[1];\n"
        "uniform mat4 mvp;\n"
        "void main() {\n"
        "  gl_Position = mvp * vec4(positions[0], 0.0, 1.0);\n"
        "}\n",
        # Fragment shader — flat color output
        "uniform vec4 color_out;\n"
        "void main() {\n"
        "  gl_FragColor = color_out;\n"
        "}\n",
    )
    return _shader


# ---------------------------------------------------------------------------
# Drawing helpers — Blender 5 gpu API only
# ---------------------------------------------------------------------------

def draw_point_2d(sx, sy, color, size=8.0):
    """Draw a filled point at screen position (sx, sy) in pixels."""
    shader = get_shader()
    shader.bind()

    # Set projection to screen-space 2D (clip space -1..1)
    w, h = bpy.context.region.width, bpy.context.region.height
    # Build 2D ortho projection matrix: map [-w/2, w/2]x[-h/2, h/2] to clip space
    proj = (
        2.0 / w, 0.0, 0.0, 0.0,
        0.0, -2.0 / h, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        -1.0, 1.0, 0.0, 1.0,
    )
    shader.uniform_vector_float("mvp", (proj,), len(proj))
    shader.uniform_vector_float("color_out", color, 4)

    # GPU state — Blender 5 gpu module
    gpu.state.blend_set('ALPHA')
    gpu.state.point_size_set(size)

    # Vertices in screen pixel space shifted to clip space
    cx = sx - w * 0.5
    cy = sy - h * 0.5
    batch = batch_for_shader(
        shader,
        'POINTS',
        {"positions": [(cx, cy)]},
    )
    batch.draw()


def draw_line_2d(x0, y0, x1, y1, color, width=2.0):
    """Draw a 2D line segment in screen pixels."""
    shader = get_shader()
    shader.bind()

    w, h = bpy.context.region.width, bpy.context.region.height
    proj = (
        2.0 / w, 0.0, 0.0, 0.0,
        0.0, -2.0 / h, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        -1.0, 1.0, 0.0, 1.0,
    )
    shader.uniform_vector_float("mvp", (proj,), len(proj))
    shader.uniform_vector_float("color_out", color, 4)

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(width)

    cx0, cy0 = x0 - w * 0.5, y0 - h * 0.5
    cx1, cy1 = x1 - w * 0.5, y1 - h * 0.5
    batch = batch_for_shader(
        shader,
        'LINES',
        {"positions": [(cx0, cy0), (cx1, cy1)]},
    )
    batch.draw()


def draw_cross_2d(sx, sy, color, size=5.0):
    """Draw a small cross at screen position (sx, sy)."""
    draw_line_2d(sx - size, sy, sx + size, sy, color)
    draw_line_2d(sx, sy - size, sx, sy + size, color)


def draw_dashed_line(x0, y0, x1, y1, color, dash=6.0, gap=4.0):
    """Draw a dashed 2D line."""
    dx = x1 - x0
    dy = y1 - y0
    total = math.sqrt(dx * dx + dy * dy)
    if total < 1e-6:
        return

    ux = dx / total
    uy = dy / total
    pos = 0.0
    drawing = True
    while pos < total:
        seg_len = dash if drawing else gap
        next_pos = min(pos + seg_len, total)
        if drawing:
            t0, t1 = pos / total, next_pos / total
            draw_line_2d(
                x0 + ux * (t0 * total), y0 + uy * (t0 * total),
                x0 + ux * (t1 * total), y0 + uy * (t1 * total),
                color,
            )
        pos = next_pos
        drawing = not drawing


# ---------------------------------------------------------------------------
# Screen projection
# ---------------------------------------------------------------------------

def project_to_screen(region, rv3d, world_pt):
    """Project 3D world point to screen (px_x, px_y) or None."""
    try:
        # Blender 5.x API
        s2d = mathutils.region_3d_to_location_2d(region, rv3d, world_pt)
        if s2d is not None:
            return Vector((s2d.x * region.width, s2d.y * region.height))
    except Exception:
        pass

    # Manual NDC projection via view_matrix
    try:
        mvp = rv3d.perspective_matrix @ rv3d.view_matrix
        co = Vector(world_pt)
        clip = mvp @ co.to_4d()
        if abs(clip.w) < 1e-9:
            return None
        ndc_x, ndc_y = clip.x / clip.w, clip.y / clip.w
        px = (ndc_x + 1.0) * 0.5 * region.width
        py = (ndc_y + 1.0) * 0.5 * region.height
        return Vector((px, py))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Inference update
# ---------------------------------------------------------------------------

SNAP_VERT = 1
SNAP_MID = 2
SNAP_EDGE = 3
SNAP_FACE = 4


def update_inference_state(x, y, ctx):
    """Raycast from screen coords, find nearest snap point, update state."""
    region = ctx.region
    rv3d = ctx.space_data.region_3d if ctx.space_data else None
    if not region or not rv3d:
        inference_state.set_snap("", Vector((0, 0, 0)))
        return

    depsgraph = ctx.evaluated_depsgraph_get()

    # Primary raycast to find face hit depth
    try:
        # Blender 5.x — ray_cast takes (depsgraph, origin, direction)
        hit, loc, nor, idx, obj = ctx.scene.ray_cast(
            depsgraph,
            region.view2d.region_to_view(x, y),
            rv3d.view_rotation @ Vector((0, 0, -1)),
        )
    except Exception:
        hit = False

    candidates = []
    hit_depth = 200.0
    cursor_screen = Vector((x, y))
    snap_radius_sq = 15 ** 2

    if hit:
        candidates.append((SNAP_FACE, "onface", loc.copy(), nor.copy() if nor else Vector((0, 0, 1))))
        try:
            hit_depth = (loc - rv3d.view_location).length
        except Exception:
            hit_depth = 20.0

    world_radius = 0.05 * max(hit_depth, 1.0)

    # Gather geometry
    for obj in depsgraph.objects:
        if obj.type not in ('MESH', 'CURVE', 'SURFACE'):
            continue
        try:
            visible = obj.visible_get() if hasattr(obj, 'visible_get') else obj.visible
        except Exception:
            visible = True
        if not visible:
            continue

        try:
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
        except Exception:
            continue
        if mesh is None:
            continue

        matrix = eval_obj.matrix_world

        for v in mesh.vertices:
            wp = matrix @ v.co
            sp = project_to_screen(region, rv3d, wp)
            if sp is None:
                continue
            d2 = ((sp.x - cursor_screen.x) ** 2 + (sp.y - cursor_screen.y) ** 2)
            if d2 <= snap_radius_sq:
                candidates.append((SNAP_VERT, "endpoint", wp, None))

        for poly in mesh.polygons:
            for lidx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                l = mesh.loops[lidx]
                next_l_idx = poly.loop_start
                v_curr = matrix @ mesh.vertices[l.vertex_index].co
                v_next = matrix @ mesh.vertices[mesh.loops[next_l_idx].vertex_index].co
                midpoint = (v_curr + v_next) * 0.5
                sp = project_to_screen(region, rv3d, midpoint)
                if sp is None:
                    continue
                d2 = ((sp.x - cursor_screen.x) ** 2 + (sp.y - cursor_screen.y) ** 2)
                if d2 <= snap_radius_sq:
                    candidates.append((SNAP_MID, "midpoint", midpoint, None))

    if not candidates:
        inference_state.set_snap("", Vector((0, 0, 0)))
        return

    def candidate_key(item):
        pri, stype, wpt, wnor = item
        sp = project_to_screen(region, rv3d, wpt)
        dist = ((sp.x - cursor_screen.x) ** 2 + (sp.y - cursor_screen.y) ** 2) if sp else float('inf')
        return (pri, dist)

    candidates.sort(key=candidate_key)
    best = candidates[0]
    inference_state.set_snap(best[1], best[2], best[3])


# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------

COLOR_ENDPOINT = (0.0, 1.0, 0.0, 1.0)   # green
COLOR_MIDPOINT = (0.0, 0.5, 1.0, 1.0)   # blue
COLOR_ONEDGE = (1.0, 0.5, 0.0, 1.0)    # orange
COLOR_ONFACE = (1.0, 0.0, 1.0, 1.0)    # magenta
COLOR_LINE = (1.0, 1.0, 1.0, 0.7)       # white semi-transparent

SNAP_COLORS = {
    "endpoint": COLOR_ENDPOINT,
    "midpoint": COLOR_MIDPOINT,
    "onedge": COLOR_ONEDGE,
    "onface": COLOR_ONFACE,
}

_prev_snap_point = None


def draw_inference_overlay():
    """Draw callback — shows colored snap marker and connector line."""
    global _prev_snap_point

    if not inference_state.active:
        return

    ctx = bpy.context
    region = ctx.region
    rv3d = ctx.space_data.region_3d if ctx.space_data else None
    if region is None or rv3d is None:
        return

    snap_type = inference_state.snap_type
    snap_point = inference_state.snap_point

    if not snap_type:
        return

    color = SNAP_COLORS.get(snap_type, (1.0, 1.0, 1.0, 1.0))
    screen_snap = project_to_screen(region, rv3d, snap_point)

    if screen_snap is not None:
        draw_cross_2d(screen_snap.x, screen_snap.y, color, size=5.0)
        draw_point_2d(screen_snap.x, screen_snap.y, color, size=8.0)

    prev_point = inference_state.get_prev()
    if prev_point is not None and screen_snap is not None:
        screen_prev = project_to_screen(region, rv3d, prev_point)
        if screen_prev is not None:
            draw_dashed_line(
                screen_prev.x, screen_prev.y,
                screen_snap.x, screen_snap.y,
                COLOR_LINE,
            )


# ---------------------------------------------------------------------------
# Modal mousemove handler
# ---------------------------------------------------------------------------

_prev_x = 0
_prev_y = 0


def inference_modal_mousemove(event, ctx):
    global _prev_snap_point, _prev_x, _prev_y

    if not inference_state.active:
        return

    x, y = event.mouse_x, event.mouse_y

    if inference_state.snap_type:
        _prev_snap_point = inference_state.snap_point.copy()

    update_inference_state(x, y, ctx)

    if inference_state.snap_type:
        inference_state._prev_snap_point = _prev_snap_point
        _prev_snap_point = inference_state.snap_point.copy()

    _prev_x, _prev_y = x, y


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

_draw_handle = None
_timer_handle = None


class VIEW3D_OT_sk_enable_inference(bpy.types.Operator):
    """Start SketchUp-style inference snapping and overlay."""

    bl_idname = "view3d.sk_enable_inference"
    bl_label = "Enable Inference Snapping"
    bl_options = {'REGISTER'}

    _handle = None
    _timer = None

    def modal(self, ctx, event):
        if not inference_state.active:
            return {'FINISHED'}

        if event.type == 'ESC':
            bpy.ops.view3d.sk_disable_inference()
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            inference_modal_mousemove(event, ctx)

        return {'PASS_THROUGH'}

    def invoke(self, ctx, event):
        global _draw_handle, _timer_handle

        if inference_state.active:
            return {'CANCELLED'}

        inference_state.active = True
        inference_state.clear()

        # Add draw handler — Blender 5.x API
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_inference_overlay, (), 'WINDOW', 'POST_VIEW'
        )

        # Start frame timer
        _timer_handle = ctx.window_manager.event_timer_add(
            0.05, window=ctx.window
        )

        ctx.window_manager.modal_handler_add(self)
        inference_modal_mousemove(event, ctx)

        return {'RUNNING_MODAL'}


class VIEW3D_OT_sk_disable_inference(bpy.types.Operator):
    """Stop SketchUp-style inference snapping and overlay."""

    bl_idname = "view3d.sk_disable_inference"
    bl_label = "Disable Inference Snapping"
    bl_options = {'REGISTER'}

    def invoke(self, ctx, event):
        global _draw_handle, _timer_handle

        if _draw_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
            except Exception:
                pass
            _draw_handle = None

        if _timer_handle is not None:
            try:
                ctx.window_manager.event_timer_remove(_timer_handle)
            except Exception:
                pass
            _timer_handle = None

        inference_state.clear()
        return {'FINISHED'}


classes = (
    VIEW3D_OT_sk_enable_inference,
    VIEW3D_OT_sk_disable_inference,
)


def draw_handler_add():
    """Called from navigation.py register() to pre-start the handler."""
    global _draw_handle
    if _draw_handle is None:
        try:
            _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_inference_overlay, (), 'WINDOW', 'POST_VIEW'
            )
        except Exception:
            pass


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    global _draw_handle, _timer_handle

    try:
        if _draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
            _draw_handle = None
    except Exception:
        pass

    try:
        if _timer_handle is not None:
            bpy.context.window_manager.event_timer_remove(_timer_handle)
            _timer_handle = None
    except Exception:
        pass

    inference_state.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
