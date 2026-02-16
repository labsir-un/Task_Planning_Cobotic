# Custom Sokoban + CIF Supervisor

## Overview
- Grid-based Sokoban variant (10x10). Player can design a level (place blocks and goals), then press Enter to play. Objective: get all red blocks onto goal tiles.
- Blocks: Black (wall, static), Red (agent-controlled toward goals), Blue (player-only), Green (shared: player and agent can move).
- Architecture: Python/pygame UI for board design and play; CIF models (`goals.cif`, `block.cif`, `sokoban.cif`) generated from the designed board; a supervisor (`cifsim`) runs in a separate terminal and gates all moves; an agent plans moves for reds (and nudges greens) under supervision.

## Files
- `main.py` — pygame UI, board editor, gameplay loop, HUD, and wiring to supervisor and agent.
- `board.py` — grid state, block placement/removal/movement rules, goal tracking.
- `block.py` — block dataclass (color).
- `game_types.py` — enums and Direction helpers.
- `config.py` — tuning constants (sizes, colors, agent speed).
- `agent.py` — agent planner: assigns goals to reds, finds paths avoiding blacks, nudges greens blocking reds.
- `buildCif.py` — exports the current board to `goals.cif` and `sokoban.cif`, keeps instance naming consistent with CIF.
- `supervisor.py` — runs `cifsim` in a terminal, parses enabled transitions, and only lets allowed moves through.
- `main.py` — pygame UI; also bridges ROS 2: publishes move events on `cif/move_event`, accepts `cif/move` commands, and publishes `cif/state`/`cif/event`.
- `block.cif` — CIF block templates (red/green/blue/black plants).
- `goals.cif` — generated goals set + `inGoal` helper.
- `sokoban.cif` — generated instance declarations and collision requirement.
- `README.md` — this file.

## Setup
- Create a virtual environment: `python3 -m venv venv`
- Install dependencies: `./venv/bin/pip install pygame`
- Install the CIF simulator from Eclipse ESCET and note the `cifsim` binary path (e.g., `~/EclipseEscet/eclipse-escet-v9.0/bin/cifsim`).
- Set the relative path inside `base_cmd` of the supervisor.py file

## Run & Play
- Start the UI: `./venv/bin/python ./main.py`
- Design (setup state) in the UI:
  - Brushes: `r` red, `g` green, `b` blue, `k` black, `x` goal, `0` eraser.
  - Left-click to place, right-click to erase blocks/goals.
- Gameplay is driven via ROS 2 (no in-UI moves/start):
  - Start with `cif/start` (String, any payload) to kick off supervision using the current board.
  - Request moves via `cif/move` (String JSON): `{"color":"blue|green","id":int,"dir":"up|down|left|right"}`. Color+id refer to the instance labels shown in the UI.
  - Each successful move (player or agent) is also published on `cif/move_event`.

## Test
- Start node with UI: `./venv/bin/python ./main.py`
- Start play: `ros2 topic pub /cif/start std_msgs/msg/String "{data: ''}" --once`
- Request a move:\
  `ros2 topic pub /cif/move std_msgs/msg/String "{data: '{\"color\":\"blue\",\"id\":1,\"dir\":\"right\"}'}" --once`
- Observe streams:\
  `ros2 topic echo /cif/move_event`

## How It Works
- CIF generation: `buildCif.py` enumerates blocks by color and bottom-left coordinates, writes `goals.cif` and `sokoban.cif` to mirror the designed board, and returns the instance map.
- Supervision: `supervisor.py` starts `cifsim` with the generated model, reads the “Possible transitions” list each step, and only allows moves present in that list (sending the numbered selection back to `cifsim`). Output is tailed in a separate terminal/log.
- Agent: assigns unique goals to reds (avoiding blacks), steps along clear paths; if blocked only by greens, it nudges one blocking green one tile off the red’s path. Moves are attempted through the supervisor before updating the board.
- Rendering: `main.py` draws the grid, blocks with instance numbers, goals, selection highlights, and counters; `board.py` enforces move legality (bounds, collisions, color rules).
