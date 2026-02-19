# ROS Topics
- `/gridtwin/start`
- `/gridtwin/in`
- `/gridtwin/out`

# Inputs
- From `/gridtwin/start`:
  - `start`
- From `/gridtwin/in`:
  - `state`
  - `move player <blue|green> <id> <up|down|left|right>`
  - `move agent <red|green> <id> <up|down|left|right>`
  - `suggest <red|green> <id>`

# Outputs
- To `/gridtwin/out`:
  - `started`
  - `state <phase> blocks <color:id:x:y;...> goals <x:y;...>`
  - `step <color> <id> <up|down|left|right> <x> <y>`
  - `move_ok <player|agent> <color> <id> <up|down|left|right> <x> <y>`
  - `move_fail ...`
  - `error ...`

# Testing
- Run GridTwin UI:
  - `./venv/bin/python ./main.py`
- Start play mode:
  - `ros2 topic pub /gridtwin/start std_msgs/msg/String "{data: 'start'}" --once`
- Ask full state:
  - `ros2 topic pub /gridtwin/in std_msgs/msg/String "{data: 'state'}" --once`
- Request user move:
  - `ros2 topic pub /gridtwin/in std_msgs/msg/String "{data: 'move player blue 1 right'}" --once`
- Request robot move:
  - `ros2 topic pub /gridtwin/in std_msgs/msg/String "{data: 'move agent red 1 up'}" --once`
- Request robot step suggestion:
  - `ros2 topic pub /gridtwin/in std_msgs/msg/String "{data: 'suggest red 1'}" --once`
- Observe outputs:
  - `ros2 topic echo /gridtwin/out`
