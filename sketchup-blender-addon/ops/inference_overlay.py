# SPDX-License-Identifier: MIT
"""
SketchUp-style inference snapping overlay for Blender 3D Viewport.

Operators:
    VIEW3D_OT_sk_enable_inference  - Enables inference snapping + overlay
    VIEW3D_OT_sk_disable_inference - Disables inference snapping + overlay
"""

import bpy
import bgl
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
        # Previous snap for drawing the connector line
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
        """Copy current snap into previous so we can draw a line between them."""
        if self.snap_type:
            self._prev_snap_point = self.snap_point.copy()
            self._prev_snap_type = self.snap_type

    def get_prev(self):
        """Return the previous snap point or None."""
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
# Inference helper
# ---------------------------------------------------------------------------

def update_inference_state(x, y, context):
    """
    Cast a ray from screen coordinates (x, y) and perform inference snapping.

    Checks:
      - Vertex snap  : within 15 px screen radius
      - Edge midpoint snap : within 15 px screen radius
      - Face intersection  : fall-back ray hit on face
      - Edge ray intersection : fall-back ray hit on edge

    Results are written to ``inference_state``.
    All logic stays in 3D world space; only the pixel-radius threshold
    is converted to a world-space distance at the hit depth.
    """
    region = context.region
    rv3d   = context.space_data.region_3d if context.space_data else None
    if not region or not rv3d:
        inference_state.set_snap("", Vector((0, 0, 0)))
        return

    # -- 1. Primary raycast from cursor --------------------------------------
    result = context.scene.ray_cast(
        context.evaluated_depsgraph_get(),
        (x, y),
    )

    def ray_3d(origin, direction, max_dist=1e6):
        """Project a screen-space ray into 3D space and return hit info."""
        # Build a 3D ray in world space from the view ray direction
        # direction is already in world space from the view
        mvw = rv3d.view_matrix
        # Forward direction from view matrix
        forward = -Vector((mvw[2][0], mvw[2][1], mvw[2][2]))
        # Offset origin to camera/eye position
        if rv3d.is_perspective:
            eye = rv3d.view_location
            # Scale forward by a large amount to simulate a ray
            ray_dir = direction.normalized()
            hit, location, normal, face_idx, object, matrix = context.scene.ray_cast(
                context.evaluated_depsgraph_get(),
                eye,
                ray_dir,
            )
            if hit:
                return hit, location, normal, face_idx, object
        else:
            # Orthographic: shoot along the view normal through cursor point
            view_dir = forward.normalized()
            # Get 3D point under cursor in ortho mode
            loc_3d = region_3d_to_location(region, rv3d, x, y, origin + view_dir)
            if loc_3d is not None:
                hit, location, normal, face_idx, object = context.scene.ray_cast(
                    context.evaluated_depsgraph_get(),
                    loc_3d,
                    view_dir,
                )
                if hit:
                    return hit, location, normal, face_idx, object
        return False, None, None, -1, None

    def region_3d_to_location(region, rv3d, sx, sy, depth_pos):
        """Map screen (sx, sy) + a depth position to 3D world location."""
        try:
            return mathutils.region_3d_to_location_3d(region, rv3d, sx, sy, depth_pos)
        except Exception:
            # Blender 3.x fallback using coordinate directly
            try:
                import mathutils.geometry as geom
                persp = rv3d.is_perspective
                if persp:
                    v1 = Vector(region_3d_to_location(region, rv3d, sx, sy, depth_pos))
                    v2 = Vector(region_3d_to_location(region, rv3d, sx, sy, depth_pos + Vector((0,0,1000))))
                    direction = (v2 - v1).normalized()
                    return v1 + direction * 10.0
                else:
                    return depth_pos
            except Exception:
                return depth_pos

    hit, hit_loc, hit_nor, hit_face, hit_obj = ray_3d(
        context.region_data.view_location if hasattr(context, 'region_data') else Vector((0,0,0)),
        Vector((0,0,0)),
    )

    # -- 2. Gather candidate geometry around the hit -------------------------
    candidates = []  # (priority, snap_type, world_point, world_normal)
    SNAP_VERT = 1
    SNAP_MID  = 2
    SNAP_EDGE = 3
    SNAP_FACE = 4

    # Helper: project a 3D point to screen coords
    def to_screen_3d(world_pt):
        try:
            screen = mathutils.region_3d_to_location_2d(region, rv3d, world_pt)
            if screen is not None:
                return Vector((screen.x, screen.y))
        except Exception:
            pass
        # Fallback: manual projection via view_matrix + perspective division
        try:
            co = Vector(world_pt)
            mvp = rv3d.perspective_matrix @ rv3d.view_matrix
            clip = mvp @ co.to_4d()
            if abs(clip.z) > 1e-6:
                ndc = (clip.x / clip.w, clip.y / clip.w)
                # Convert from NDC [-1,1] to screen [0,1] then to pixels
                pw = region.width
                ph = region.height
                return Vector((
                    (ndc[0] + 1.0) * 0.5 * pw,
                    (ndc[1] + 1.0) * 0.5 * ph,
                ))
        except Exception:
            pass
        return None

    def to_screen(world_pt):
        """Return screen (px_x, px_y) or None."""
        s = to_screen_3d(world_pt)
        if s is not None:
            return s
        return None

    def screen_dist_2d(a, b):
        """Squared pixel distance between two screen-space vectors."""
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    # -- 3. Scan objects in visible layers ----------------------------------
    depsgraph = context.evaluated_depsgraph_get()
    snap_radius_sq = (15 ** 2)  # 15 px threshold

    cursor_screen = Vector((x, y))
    hit_depth = 200.0  # default fallback

    if hit:
        candidates.append((SNAP_FACE, "onface", hit_loc.copy(), hit_nor.copy()))
        try:
            hit_depth = (hit_loc - context.region_data.view_location if hasattr(context, 'region_data') else Vector((0,0,0))).length
        except Exception:
            hit_depth = 20.0

    # World-space equivalent radius: approximate at the scene scale
    world_radius = 0.05 * max(hit_depth, 1.0)

    for obj in depsgraph.objects:
        if obj.type not in ('MESH', 'CURVE', 'SURFACE'):
            continue
        if not (obj.visible_get() if hasattr(obj, 'visible_get') else obj.visible):
            continue
        try:
            eval_obj = obj.evaluated_get(depsgraph)
        except Exception:
            eval_obj = obj
        mesh = eval_obj.to_mesh()
        if mesh is None:
            continue
        matrix = eval_obj.matrix_world

        # -- Vertices --------------------------------------------------------
        for v in mesh.vertices:
            wp = matrix @ v.co
            sp = to_screen(wp)
            if sp is None:
                continue
            d2 = screen_dist_2d(sp, cursor_screen)
            if d2 <= snap_radius_sq:
                candidates.append((SNAP_VERT, "endpoint", wp, None))

        # -- Edge midpoints ---------------------------------------------------
        for poly in mesh.polygons:
            for lidx in range(poly.loop_start, poly.loop_start + poly.loop_total):
                l = mesh.loops[lidx]
                next_l = mesh.loops[poly.loop_start]
                v_curr = matrix @ mesh.vertices[l.vertex_index].co
                v_next = matrix @ mesh.vertices[next_l.vertex_index].co
                midpoint = (v_curr + v_next) * 0.5
                sp = to_screen(midpoint)
                if sp is None:
                    continue
                d2 = screen_dist_2d(sp, cursor_screen)
                if d2 <= snap_radius_sq:
                    candidates.append((SNAP_MID, "midpoint", midpoint, None))

        # -- Edge rays (if we haven't hit anything yet) --------------------
        if not hit:
            for edge in mesh.edges:
                v0 = matrix @ edge.vertices[0]
                v1 = matrix @ edge.vertices[1]
                # Simple closest-point-on-segment test with view ray
                try:
                    view_dir = -Vector((rv3d.view_matrix[2][0], rv3d.view_matrix[2][1], rv3d.view_matrix[2][2]))
                    origin = rv3d.view_location
                except Exception:
                    continue
                seg = v1 - v0
                seg_len = seg.length
                if seg_len < 1e-6:
                    continue
                seg_n = seg / seg_len
                t = max(0.0, min(1.0, (origin - v0).dot(seg_n) / seg_len))
                closest = v0 + t * seg
                sp = to_screen(closest)
                if sp is None:
                    continue
                d2 = screen_dist_2d(sp, cursor_screen)
                if d2 <= snap_radius_sq:
                    candidates.append((SNAP_EDGE, "onedge", closest, None))

    # -- 4. Pick best candidate (lowest priority number wins) ---------------
    if not candidates:
        inference_state.set_snap("", Vector((0, 0, 0)))
        return

    # Sort by priority then by distance to cursor
    def candidate_key(item):
        pri, stype, wpt, wnor = item
        sp = to_screen(wpt)
        dist = screen_dist_2d(sp, cursor_screen) if sp else float('inf')
        return (pri, dist)

    candidates.sort(key=candidate_key)
    best = candidates[0]
    inference_state.set_snap(best[1], best[2], best[3])

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

_shader_2d = None

def get_shader_2d():
    """Return a cached gpu shader for 2D overlay drawing."""
    global _shader_2d
    if _shader_2d is None:
        _shader_2d = gpu.types.GPUShader(
            (
                # Vertex shader
                "#version 330\n"
                "in vec2 position;\n"
                "uniform mat4 mvp;\n"
                "void main() {\n"
                "  gl_Position = mvp * vec4(position, 0.0, 1.0);\n"
                "}\n"
            ),
            (
                # Fragment shader
                "#version 330\n"
                "uniform vec4 color;\n"
                "out vec4 fragColor;\n"
                "void main() {\n"
                "  fragColor = color;\n"
                "}\n"
            ),
        )
    return _shader_2d


def project_to_screen(region, rv3d, world_pt):
    """
    Project a 3D world-space point to 2D screen coordinates (pixels).
    Returns (px_x, px_y) or None on failure.
    """
    try:
        # Blender 4.x primary API
        s2d = mathutils.region_3d_to_location_2d(region, rv3d, world_pt)
        if s2d is not None:
            return Vector((s2d.x * region.width, s2d.y * region.height))
    except Exception:
        pass

    # Fallback: manual NDC projection
    try:
        mvp = rv3d.perspective_matrix @ rv3d.view_matrix
        co = Vector(world_pt)
        clip = mvp @ co.to_4d()
        if abs(clip.w) < 1e-9:
            return None
        ndc_x = clip.x / clip.w
        ndc_y = clip.y / clip.w
        px = (ndc_x + 1.0) * 0.5 * region.width
        py = (ndc_y + 1.0) * 0.5 * region.height
        return Vector((px, py))
    except Exception:
        return None


def draw_point_2d(sx, sy, color, size=6.0):
    """Draw a 2D filled square at screen position (sx, sy)."""
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glPointSize(size)
    bgl.glEnable(bgl.GL_PROGRAM_POINT_SIZE)

    shader = get_shader_2d()
    shader.bind()
    mvp = gpu.matrix.get_projection_matrix()
    shader.uniform_from_world("mvp", mvp)
    shader.uniform_float("color", color)

    batch = batch_for_shader(
        shader,
        "POINTS",
        {"position": [(sx, sy)]},
    )
    batch.draw(shader)


def draw_line_2d(x0, y0, x1, y1, color):
    """Draw a 2D line segment."""
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

    shader = get_shader_2d()
    shader.bind()
    mvp = gpu.matrix.get_projection_matrix()
    shader.uniform_from_world("mvp", mvp)
    shader.uniform_float("color", color)

    batch = batch_for_shader(
        shader,
        "LINES",
        {"position": [(x0, y0), (x1, y1)]},
    )
    batch.draw(shader)


def draw_cross_2d(sx, sy, color, size=4.0):
    """Draw a small cross at screen position (sx, sy)."""
    s = size
    draw_line_2d(sx - s, sy, sx + s, sy, color)
    draw_line_2d(sx, sy - s, sx, sy + s, color)


# ---------------------------------------------------------------------------
# Inference overlay draw callback
# ---------------------------------------------------------------------------

_draw_handler_handle = None

COLOR_ENDPOINT = (0.0, 1.0, 0.0, 1.0)   # green
COLOR_MIDPOINT = (0.0, 0.5, 1.0, 1.0)    # blue
COLOR_ONEDGE   = (1.0, 0.5, 0.0, 1.0)    # orange
COLOR_ONFACE   = (1.0, 0.0, 1.0, 1.0)   # magenta
COLOR_LINE     = (1.0, 1.0, 1.0, 0.7)   # white semi-transparent

SNAP_COLORS = {
    "endpoint": COLOR_ENDPOINT,
    "midpoint": COLOR_MIDPOINT,
    "onedge":   COLOR_ONEDGE,
    "onface":   COLOR_ONFACE,
}


def draw_inference_overlay():
    """
    Draw callback registered with SpaceView3D.draw_handler_add.

    - Draws a colored marker at the current snap point (based on snap_type).
    - Draws a white dashed line from the previous snap to the current snap
      when both exist.
    All coordinates are kept in 3D world space; only the final output is
    projected to screen space for drawing.
    """
    global inference_state

    if not inference_state.active:
        return

    # Need current context to access region/rv3d
    context = bpy.context
    region  = context.region
    rv3d    = context.space_data.region_3d if context.space_data else None
    if region is None or rv3d is None:
        return

    snap_type  = inference_state.snap_type
    snap_point = inference_state.snap_point

    if not snap_type:
        return

    # -- Current snap marker ------------------------------------------------
    color = SNAP_COLORS.get(snap_type, (1.0, 1.0, 1.0, 1.0))
    screen_snap = project_to_screen(region, rv3d, snap_point)
    if screen_snap is not None:
        # Draw a small cross for precision
        draw_cross_2d(screen_snap.x, screen_snap.y, color, size=5.0)
        # Draw a point so it is visible at all zoom levels
        draw_point_2d(screen_snap.x, screen_snap.y, color, size=8.0)

    # -- Connector line between previous and current snap --------------------
    prev_point = inference_state.get_prev()
    if prev_point is not None:
        screen_prev = project_to_screen(region, rv3d, prev_point)
        if screen_snap is not None and screen_prev is not None:
            # Draw a dashed-style line by drawing multiple segments
            draw_dashed_line(screen_prev.x, screen_prev.y,
                             screen_snap.x, screen_snap.y,
                             COLOR_LINE, dash_length=6.0, gap_length=4.0)


def draw_dashed_line(x0, y0, x1, y1, color, dash_length=6.0, gap_length=4.0):
    """Draw a dashed 2D line between two screen-space points."""
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
        seg_len = dash_length if drawing else gap_length
        next_pos = min(pos + seg_len, total)
        if drawing:
            t0 = pos / total
            t1 = next_pos / total
            draw_line_2d(
                x0 + ux * (t0 * total), y0 + uy * (t0 * total),
                x0 + ux * (t1 * total), y0 + uy * (t1 * total),
                color,
            )
        pos = next_pos
        drawing = not drawing


# ---------------------------------------------------------------------------
# Modal mousemove handler
# ---------------------------------------------------------------------------

def inference_modal_handler(args):
    """Called on every mousemove event when inference is active."""
    # Args come from the original invoke; we re-fetch the event directly
    evt = bpy.context.window_manager.event_timer_freeze()
    # We rely on the VIEW3D_OT_sk_enable_inference operator's modal loop
    # to call update_inference_state each frame.


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class VIEW3D_OT_sk_enable_inference(bpy.types.Operator):
    """Start SketchUp-style inference snapping and overlay."""

    bl_idname = "view3d.sk_enable_inference"
    bl_label  = "Enable Inference Snapping"
    bl_options = {'REGISTER', 'UNDO'}

    _handle = None
    _timer  = None

    def modal(self, context, event):
        if not inference_state.active:
            return {'FINISHED'}

        if event.type == 'INVAL' and event.value == 'PRESS':
            # ESCAPE to quit
            bpy.types.VIEW3D_OT_sk_disable_inference.run(context)
            return {'FINISHED'}

        if event.type == 'MOUSEMOVE':
            # Update inference state from current mouse position
            inference_modal_mousemove(event, context)

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if inference_state.active:
            self.report({'INFO'}, "Inference snapping is already active.")
            return {'CANCELLED'}

        # Enable the state
        inference_state.active = True
        inference_state.clear()

        # Store handle on the operator class so disable can find it
        VIEW3D_OT_sk_enable_inference._handle = None

        # Add the draw handler
        handle = SpaceView3D.draw_handler_add(
            draw_inference_overlay, (), 'WINDOW', 'POST_VIEW'
        )
        VIEW3D_OT_sk_enable_inference._handle = handle

        # Start a timer to drive inference updates each frame
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.05, window=context.window)

        # Attach modal handler
        wm.modal_handler_add(self)

        # Do an initial inference at the cursor position
        inference_modal_mousemove(event, context)

        return {'RUNNING_MODAL'}

    @classmethod
    def run(cls, context):
        """Programmatic enable without full invoke (used by disable operator)."""
        bpy.ops.view3d.sk_enable_inference('INVOKE_DEFAULT')

    @classmethod
    def cleanup(cls, context):
        """Remove handler and timer."""
        if cls._handle is not None:
            try:
                SpaceView3D.draw_handler_remove(cls._handle, 'WINDOW')
            except Exception:
                pass
            cls._handle = None
        if cls._timer is not None:
            try:
                context.window_manager.event_timer_remove(cls._timer)
            except Exception:
                pass
            cls._timer = None


class VIEW3D_OT_sk_disable_inference(bpy.types.Operator):
    """Stop SketchUp-style inference snapping and overlay."""

    bl_idname = "view3d.sk_disable_inference"
    bl_label  = "Disable Inference Snapping"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        VIEW3D_OT_sk_enable_inference.cleanup(context)
        inference_state.clear()
        return {'FINISHED'}

    @classmethod
    def run(cls, context):
        """Programmatic disable."""
        bpy.ops.view3d.sk_disable_inference('INVOKE_DEFAULT')


# ---------------------------------------------------------------------------
# Module-level reference to SpaceView3D (set in register)
# ---------------------------------------------------------------------------

SpaceView3D = None


# ---------------------------------------------------------------------------
# Inference modal mousemove helper (shared logic)
# ---------------------------------------------------------------------------

_prev_snap_point = None  # module-level for tracking previous frame


def inference_modal_mousemove(event, context):
    """Called on every MOUSEMOVE while inference is active."""
    global _prev_snap_point

    if not inference_state.active:
        return

    x, y = event.mouse_x, event.mouse_y

    # Advance previous snap before updating
    if inference_state.snap_type:
        _prev_snap_point = inference_state.snap_point.copy()
    else:
        _prev_snap_point = None

    # Update inference based on current cursor position
    update_inference_state(x, y, context)

    # If we snapped, record previous for the next frame
    if inference_state.snap_type:
        inference_state._prev_snap_point = _prev_snap_point
        _prev_snap_point = inference_state.snap_point.copy()


# ---------------------------------------------------------------------------
# Register / Unregister
# ---------------------------------------------------------------------------

classes = (
    VIEW3D_OT_sk_enable_inference,
    VIEW3D_OT_sk_disable_inference,
)


def register():
    global SpaceView3D
    SpaceView3D = bpy.types.SpaceView3D

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    global SpaceView3D

    # Clean up any live inference session first
    try:
        VIEW3D_OT_sk_enable_inference.cleanup(bpy.context)
    except Exception:
        pass

    inference_state.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    SpaceView3D = None


if __name__ == "__main__":
    register()
