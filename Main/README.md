# Orchestrator (ROS Bridge)

Runs the NLP and GridTwin modules and bridges their ROS traffic.

## Files
- `main.py` — starts `NLP/main.py` and `GridTwin/main.py` in detached processes, then runs a ROS 2 node:
  - Subscribes: `cif/move_event`, `nlp/command`
  - Publishes: `cif/start`, `cif/move`, `nlp/message`
- `ros_constants.py` — shared ROS topic names and allowed values.
- `README.md` — this file.

## Behavior
- Launches NLP and GridTwin mains (no terminal attachment).
- For NLP:
  - Command `start` → publishes to `cif/start`.
  - Command `move <blue|green> <id> <dir>` → publishes to `cif/move` as `{"color":..., "id":..., "dir":...}`.
- For GridTwin move events:
  - If an agent moves a red block, publishes an NLP message: `"Robot will move red block number X <dir>, please wait..."`.

## Run
- `./venv/bin/python ./main.py`
- Opens separate terminals for NLP and GridTwin mains (falls back to background launch if `gnome-terminal` is unavailable).
- Uses venvs per module (prefers `venv/bin/python` in repo root for NLP, `GridTwin/venv/bin/python` for GridTwin); falls back to current interpreter if missing.
- Requires ROS 2 environment and dependencies already installed in the venvs.
