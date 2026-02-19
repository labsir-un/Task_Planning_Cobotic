# ROS Topics
- `/planner/start`
- `/planner/in`
- `/planner/out`

# Inputs
- From `/planner/start`:
  - `start`
- From `/planner/in`:
  - `state <phase> blocks <color:id:x:y;...> goals <x:y;...>`
  - `done`
  - `replan`

# Outputs
- To `/planner/out`:
  - `planning`
  - `request_state`
  - `complete`
  - `user blue <id> <up|down|left|right>`
  - `user green <id> <up|down|left|right>`
  - `robot red <id> <up|down|left|right>`
  - `robot green <id> <up|down|left|right>`

# Testing
- Run planner:
  - `./venv/bin/python ./main.py`
- Start planner:
  - `ros2 topic pub /planner/start std_msgs/msg/String "{data: 'start'}" --once`
- Send state:
  - `ros2 topic pub /planner/in std_msgs/msg/String "{data: 'state playing blocks red:1:1:1;blue:1:2:2;green:1:3:3 goals 8:8;9:9'}" --once`
- Mark action done:
  - `ros2 topic pub /planner/in std_msgs/msg/String "{data: 'done'}" --once`
- Force replan:
  - `ros2 topic pub /planner/in std_msgs/msg/String "{data: 'replan'}" --once`
- Observe planner decision:
  - `ros2 topic echo /planner/out`
