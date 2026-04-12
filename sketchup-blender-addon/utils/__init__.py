# utils/__init__.py
# Inference snapping and helper utilities

import bpy
import bmesh
from mathutils import Vector, GeometryUtils


def get_inference_snap(obj, point, threshold=0.5):
    """
    SketchUp-style inference snapping.
    Returns (snapped_point, snap_type) or (None, None)
    
    Snap types:
    - endpoint: vertex
    - midpoint: edge midpoint
    - center: face center
    - onedge: point on edge
    - onface: point on face
    """
    if not obj or obj.type != 'MESH':
        return None, None

    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.from_edit_mesh(obj.data) if obj.mode == 'EDIT' else None
    
    if not bm:
        return None, None

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    best_snap = None
    best_dist = threshold
    best_type = None

    # Endpoint snapping — vertices
    for v in bm.verts:
        d = (v.co - point).length
        if d < best_dist:
            best_dist = d
            best_snap = v.co.copy()
            best_type = "endpoint"

    # Midpoint snapping — edges
    for e in bm.edges:
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        d = (mid - point).length
        if d < best_dist:
            best_dist = d
            best_snap = mid
            best_type = "midpoint"

    # On-edge snapping — closest point on edge
    for e in bm.edges:
        p1 = e.verts[0].co
        p2 = e.verts[1].co
        edge_vec = p2 - p1
        edge_len = edge_vec.length
        if edge_len < 0.0001:
            continue
        t = max(0, min(1, (point - p1).dot(edge_vec) / (edge_len ** 2)))
        closest = p1 + t * edge_vec
        d = (closest - point).length
        if d < best_dist:
            best_dist = d
            best_snap = closest
            best_type = "onedge"

    return best_snap, best_type


def draw_inference_overlay():
    """
    Draw inference point indicator in viewport using bgl.
    Call this from a view3d draw handler.
    """
    # This would be called from a viewport draw handler
    # leaving placeholder for now — bgl overlay drawing is complex
    pass


classes = []


def register():
    pass


def unregister():
    pass
