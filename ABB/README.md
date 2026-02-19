# ROS Topics
- `/abb/start`
- `/abb/in`
- `/abb/out`

# Inputs
- From `/abb/start`:
  - `start`
- From `/abb/in`:
  - `move <x> <y> <up|down|left|right>`
  - `XXXXX`

# Outputs
- To `/abb/out`:
  - `ok`
  - `fail`

# Testing
- Run ABB bridge:
  - `./venv/bin/python ./main.py`
- Ask ABB bridge to connect:
  - `ros2 topic pub /abb/start std_msgs/msg/String "{data: 'start'}" --once`
- Send movement command:
  - `ros2 topic pub /abb/in std_msgs/msg/String "{data: 'move 2 3 right'}" --once`
- Send special space command:
  - `ros2 topic pub /abb/in std_msgs/msg/String "{data: 'XXXXX'}" --once`
- Observe result topic:
  - `ros2 topic echo /abb/out`
- Optional local TCP emulator for quick testing:
  - `nc -l 8000`
