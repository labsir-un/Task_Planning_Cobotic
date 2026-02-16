# RAPID skeleton for ABB bridge

Minimal RAPID task to accept the current TCP payload `XXYYD` (two-digit x, two-digit y, direction initial). The rest of the motion logic is TODO.

## Expected payload
- String length 5: `x1 x2 y1 y2 d`, e.g., `0001R` for x=0, y=1, dir=Right.
- Directions encoded as: `U` up, `D` down, `L` left, `R` right.

## Behavior (current skeleton)
- Listens on port 8000.
- On each client message:
  - Parses x, y, dir from the 5-char string.
  - Logs them to the event log.
  - TODO: map grid (x,y) to world coordinates and perform motion.
  - Sends back `"1"` on parsing success, `"0"` on error.

## Files
- `MainModule.mod` — skeleton module with socket handling and minimal parsing. Motion parts are TODO.

## Notes
- Replace TODO sections with your motion, tool, and safety logic.
- Keep reply contract: `"1"` success, `"0"` failure, so the Python bridge works.
