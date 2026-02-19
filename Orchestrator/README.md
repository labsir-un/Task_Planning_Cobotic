# ROS Topics
- No orchestrator-owned topics.
- Reads:
  - `/nlp/out`
  - `/planner/out`
  - `/gridtwin/out`
  - `/abb/out`
- Writes:
  - `/nlp/in`
  - `/planner/start`
  - `/planner/in`
  - `/gridtwin/start`
  - `/gridtwin/in`
  - `/abb/in`

# Inputs
- From `/nlp/out`: `start`, `go`, `fixed`, `done`, `space`
- From `/planner/out`: `request_state`, `complete`, `<user|robot> <color> <id> <up|down|left|right>`
- From `/gridtwin/out`: `started`, `state ...`, `move_ok ...`, `move_fail ...`, `error ...`
- From `/abb/out`: `ok`, `fail`

# Outputs
- To `/planner/start`: `start`
- To `/planner/in`: `state ...`, `done`, `replan`
- To `/gridtwin/start`: `start`
- To `/gridtwin/in`: `state`, `move <player|agent> <color> <id> <dir>`
- To `/abb/in`: `move <x> <y> <dir>`
- To `/nlp/in`: user prompts, robot caution, success/failure/error messages

# Testing
- Run orchestrator:
  - `./venv/bin/python ./main.py`
- Simulate NLP start:
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'start'}" --once`
- Simulate planner action:
  - `ros2 topic pub /planner/out std_msgs/msg/String "{data: 'user blue 1 right'}" --once`
- Simulate user direction:
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'done'}" --once`
- Simulate twin state update:
  - `ros2 topic pub /gridtwin/out std_msgs/msg/String "{data: 'state playing blocks red:1:2:3;blue:1:1:1 goals 9:9'}" --once`
- Simulate ABB success:
  - `ros2 topic pub /abb/out std_msgs/msg/String "{data: 'ok'}" --once`
- Watch routed outputs:
  - `ros2 topic echo /planner/in`
  - `ros2 topic echo /gridtwin/in`
  - `ros2 topic echo /abb/in`
  - `ros2 topic echo /nlp/in`
