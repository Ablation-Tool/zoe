# Zoe Pentomino

Zoe Pentomino is a timed spatial-practice laboratory built around the twelve free pentominoes: **F, I, L, P, T, U, V, W, X, Y, Z, and N**. Every piece contains five squares. The board is 6×10, so all twelve pieces tile exactly sixty cells when used once.

This is not draughts/checkers and not a claim about intelligence. Tetris uses seven tetrominoes; Zoe Pentomino uses twelve five-square pieces and does not clear rows. Full rows and holes are measured, while the objective remains an exact tiling.

## Play

```bash
zoe pentomino
zoe pentomino --seed my-practice-seed --seconds 300 --gravity 0.8
zoe pentomino --masked
```

The same game is available with `gem pentomino` and from the Zoe atlas.

- Arrow keys or the adjacent buttons move the active piece.
- **R** rotates; **F** reflects. Orientation preserves the visual center when possible.
- **Space** drops and places a piece that is fully inside the board.
- **Enter** places it at its current valid location.
- The five-row staging area above the board provides room to orient a piece before entering.
- Gravity advances on a GLib timer in the GTK main loop, not a worker thread.
- The agreed deadline is measured with `time.monotonic`; tests inject a deterministic clock.

**Practice** uses a seeded shuffled bag and shows the next piece. **Masked** generates secret seed material with `secrets.token_hex`, hides the next piece, and reveals the seed and complete order only when play ends. Masking is not a security boundary or proof of unpredictable human behavior.

## Measurements and replay

The session reports filled cells, full rows, holes below occupied cells, elapsed time, remaining time, and `playing`, `won`, `lost`, or `timed_out` status. A win requires all twelve pieces and sixty occupied cells. A piece with no legal board placement produces a loss; reaching the deadline produces a timeout.

Actions and effective clock/gravity changes form a bounded SHA-256 event chain. Completed sessions can be replayed from the revealed seed. Replay revalidates sequence numbers, event hashes, timestamps, action arguments, accepted outcomes, state hashes, and the final summary. Editing, reordering, or recomputing an outer hash without preserving the recorded execution is rejected.

```bash
zoe pentomino completed.json --output replay.svg
zoe pentomino --output practice.json
zoe pentomino --output board.gem
```

Active saves omit the seed and future bag order. Completed saves reveal them for replay. All saves and exports refuse to overwrite files. SVG, PNG, and GEM VDI are generated from the same board state as the native display.

## Controlled time-budget comparison

```bash
zoe pentomino --compare --output pentomino-budgets.json
zoe pentomino --compare 1,5,20,300 --seed zoe-time-study
```

The comparison keeps one seeded order and one exact-cover tiling strategy fixed. Each piece receives one synthetic second; the gravity interval is held at 3600 seconds to isolate the decision budget. With the included strategy, the 1- and 5-second runs time out before completing, while 20 and 300 seconds allow the same twelve-piece solution. These are deterministic strategy outcomes, not human reaction times, evidence that shorter deadlines are better, or a universal perfect middle ground.

The optional attempt-value lens is:

```text
attempt value = immediate reward + information gained + future skill
                + enjoyment - expected cost of failure
```

It helps discuss why another attempt may be worthwhile. It is not a biological equation, a measured confidence value, or an authorization for automatic action.

## Checks

```bash
PYTHONPATH=guiai-lab python -m unittest stress.pentomino_stress -v
```

The tests cover all pieces and transformations, collisions, gravity, deadlines, seeded and masked play, full tiling, replay and tampering, no-overwrite files, VDI, native controls, and the budget comparison.
