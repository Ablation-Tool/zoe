# Zoe Artline

Zoe Artline is an original GTK3 vector workbench inspired by the creative goals and interaction ideas in the supplied Artline 2.0 manuals. It is not an Artline emulator, a recreation of the proprietary program, or a legacy file-format compatibility layer. Digital Research and Computer Associates are not affiliated with this implementation.

## Open and export

```bash
zoe artline
zoe artline --empty
zoe artline drawing.json
zoe artline --output drawing.svg
zoe artline drawing.json --output drawing.gem
```

The same editor is available with `gem artline` and through the Zoe atlas module selector. SVG, PNG, and GEM VDI exports work without a display. Output paths must be new and their parent directories must already exist.

## Tools

- **Selector:** drag to move; Shift-drag scales around the selection center; Alt-drag rotates. Right-click duplicates the complete group or ungrouped selection.
- **Quill:** click anchor points and double-click to finish a smooth path.
- **Sketch:** drag a freehand smooth path. Two-point strokes remain open; longer strokes may be closed using the fill control.
- **Rectangle, rounded rectangle, ellipse, line, and text:** create editable vector elements.
- **Clone, Rotate 90°, Flip, Front, Back, Group, Ungroup, Undo, and Redo:** operate on the current selection.
- **Style controls:** stroke, fill, hollow, and line width can apply to new or selected elements.
- **Grid and zoom:** show a configurable grid, align selection coordinates, and zoom from 0.1× to 16×.
- **Layers:** create, select, hide, lock, and remove empty layers. Hidden and locked content survives save/load and merge.

Text uses the platform sans-serif font. Rotation converts rectangles, rounded rectangles, and ellipses to paths so the transformed geometry remains editable and exportable. The canvas is fixed at 1000×700 scene units; elements must remain inside it.

## Keyboard

| Input | Action |
|:---|:---|
| Ctrl-Z / Ctrl-Y | Undo / redo |
| Ctrl-D | Duplicate selection |
| Ctrl-G / Ctrl-Shift-G | Group / ungroup |
| Ctrl-S / Ctrl-O / Ctrl-E | Save / open / export |
| Delete | Delete selection |
| `+` / `-` / `1` | Zoom in / out / fit |
| `g` | Toggle grid |
| Escape | Cancel a draft or clear selection |

## Document and evidence model

JSON documents contain bounded elements, up to 64 layers, counters, and up to 4096 SHA-256-linked events. Loading validates dimensions, colors, object types, unique IDs, counters, event sequence, and hashes. Merge is transactional: invalid imported content restores the previous document instead of leaving a partial merge.

The event chain supplies **tamper evidence, not cryptographic authentication**. Undo/redo history is session-local rather than serialized. Saving and exporting do not overwrite existing files. SVG and PNG pass spatial verification; GEM export also exercises VDI recovery and constraint verification. VDI verification does not promise an identical Scene digest.

The supplied manuals informed feature selection, not source copying. No proprietary code, clip art, fonts, manual pages, or historical cover images are included.

## Checks

```bash
PYTHONPATH=guiai-lab python -m unittest stress.artline_stress -v
```

Native checks additionally require GTK3, Cairo, and an X11 display. They exercise actual drawing, pointer motion/release, selection, buttons, layers, open/save, and export workflows.
