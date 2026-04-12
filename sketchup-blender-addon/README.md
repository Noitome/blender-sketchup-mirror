# SketchUp 2026 Workflow for Blender 4.x

Mimics SketchUp 2026's navigation feel and core workflow inside Blender.

## Installation

1. Open Blender 4.x
2. Go to `Edit > Preferences > Add-ons`
3. Click **Install** → navigate to this folder
4. Enable **"SketchUp 2026 Workflow"**
5. The **SK** sidebar panel appears on the right of the 3D View

## Quick Start

**Enable:** `Shift + ;` or click **SK Mode** toggle in the SK panel

**Navigation (when SK Mode is ON):**
| Action | Control |
|--------|---------|
| Orbit | Left-drag |
| Pan | Shift + Left-drag |
| Zoom | Scroll wheel |
| Context menu | Right-click |

**Tools:**
| Tool | What it does |
|------|-------------|
| **Select** | Left-click to select |
| **Orbit / Pan / Zoom** | Navigation tools |
| **Rectangle** | Click two corners — draws flat rectangle on face |
| **Circle** | Click center, drag to set radius |
| **Line** | Click two points — draws edge |
| **Push Pull** | Select face, drag to extrude along normal |
| **Follow Me** | Loft a profile face along selected edges |
| **Offset** | Push edges/faces outward by a distance |
| **Move / Rotate / Scale** | Standard transforms |

## UI Layout

- **SK sidebar panel** — all tools organized by category (Select, Draw, Construct, Modify)
- **SK Options** — units (metric/imperial), inference snap toggle
- **Inference panel** — shows active snap type and last measurement
- **Status footer** — contextual help text at bottom of viewport

## What's Working

- [x] SK Mode toggle (Shift+;)
- [x] Left-drag orbit (raycast-based pivot)
- [x] Shift+drag pan
- [x] Scroll zoom
- [x] Right-click → SketchUp-style context menu
- [x] Active tool highlighting in sidebar
- [x] Status bar with tool tips
- [x] Rectangle, Circle, Line draw tools
- [x] Push-pull face extrude
- [x] Follow-me loft
- [x] Offset edges/faces
- [x] Move / Rotate / Scale delegates to Blender's transforms
- [x] Units switcher (metric/imperial)
- [x] Inference snap scaffolding (endpoint, midpoint, on-edge)

## What's Still Rough

- [ ] Orbit doesn't yet pivot around exact cursor hit point (uses Blender center)
- [ ] Inference overlay not drawn visually yet (snap type tracked but no colored lines)
- [ ] No live dimension readout during drag
- [ ] No keyboard shortcut parity (Tab=P, M=Move etc. — full remap)
- [ ] Scale/Rotate use Blender's native popups, not SK-style inline

## File Structure

```
sketchup-blender-addon/
├── __init__.py          # Entry point, bl_info
├── ops/
│   ├── __init__.py
│   ├── navigation.py    # Orbit, pan, zoom, context menu, SK mode toggle
│   ├── push_pull.py     # Push-pull extrude
│   ├── follow_me.py     # Follow-me loft
│   ├── move.py          # Move with inference
│   ├── rectangle.py     # Rectangle draw
│   ├── circle.py        # Circle draw
│   ├── line.py          # Line draw
│   ├── select.py        # Select tool
│   ├── offset.py        # Offset edges/faces
│   └── transforms.py    # Rotate, scale delegates
├── ui/
│   └── __init__.py      # SK sidebar panel, options, status footer
└── utils/
    └── __init__.py      # Inference snapping helpers
```
