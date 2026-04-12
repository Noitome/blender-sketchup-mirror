# SketchUp Blender Addon

Mimics SketchUp's navigation and core workflow inside Blender 4.x.

## Installation

1. In Blender, go to `Edit > Preferences > Add-ons`
2. Click `Install` and select this folder
3. Enable "SketchUp Workflow" in the add-ons list
4. Find the new **SK** panel in the 3D View sidebar (right side)

## How to Use

### Enabling SketchUp Mode
- Press `Shift+;` or click **SK Mode** toggle in the SK panel
- When SK Mode is ON, navigation changes to SketchUp-style
- When OFF, Blender behaves normally

### Navigation (SK Mode ON)
| Action | SketchUp-style |
|--------|---------------|
| Orbit | Left-drag |
| Pan | Shift + Left-drag |
| Zoom | Scroll wheel |

### Tools (SK Mode ON or OFF)
| Tool | What it does |
|------|-------------|
| **Rectangle** | Click two corners to draw a flat rectangle on a face |
| **Circle** | Click center, drag to set radius |
| **Push Pull** | Select a face, drag to extrude it (like SketchUp) |
| **Follow Me** | Loft/extrude a face along edges |
| **Move** | Move selected geometry with inference snapping |

### UI
- **SK** sidebar panel — all tools and options
- **SK Options** — unit system (metric/imperial), inference snap toggle
- Status bar shows current mode

## Roadmap

- [x] Left-drag orbit navigation
- [x] Shift+drag pan
- [x] Scroll zoom
- [x] Rectangle draw tool
- [x] Circle draw tool
- [x] Push-pull extrude
- [ ] Follow-me loft (basic)
- [ ] Move with inference snapping
- [ ] Endpoint/midpoint/face-center snapping overlay
- [ ] SketchUp-style dimension display during drag
- [ ] Material/color quick panel
- [ ] Component/group quick panel
- [ ] Keyboard shortcut map to match SketchUp exactly

## Files

```
sketchup-blender-addon/
├── __init__.py      # Entry point, bl_info
├── ops/
│   ├── navigation.py   # Orbit, pan, zoom operators
│   ├── push_pull.py    # Push-pull extrude
│   ├── follow_me.py    # Follow-me loft
│   ├── move.py         # Move with inference
│   ├── rectangle.py    # Rectangle draw
│   └── circle.py       # Circle draw
├── ui/
│   └── __init__.py     # SK sidebar panel, toolbar
└── utils/
    └── __init__.py     # Inference snapping helpers
```

## Building / Development

This is pure Python — no build step needed. Just install the folder as an addon.

To reload after editing without restarting Blender:
```python
bpy.ops.wm.addon_disable(module="sketchup_blender_addon")
bpy.ops.wm.addon_enable(module="sketchup_blender_addon")
```
