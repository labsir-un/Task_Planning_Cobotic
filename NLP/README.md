# ROS Topics
- `/nlp/in`
- `/nlp/out`

# Inputs
- From microphone:
  - `start`
  - `go`
  - `fixed`
  - `done`
  - `space`
  - Recognizer is constrained to this fixed command list (closed vocabulary).
- From `/nlp/in`:
  - Any plain text string to speak

# Outputs
- To `/nlp/out`:
  - `start`
  - `go`
  - `fixed`
  - `done`
  - `space`

# Testing
- Run NLP node:
  - `./venv/bin/python ./main.py`
- Simulate spoken output token:
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'start'}" --once`
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'go'}" --once`
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'fixed'}" --once`
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'done'}" --once`
  - `ros2 topic pub /nlp/out std_msgs/msg/String "{data: 'space'}" --once`
- Simulate message to speak:
  - `ros2 topic pub /nlp/in std_msgs/msg/String "{data: 'Robot will move red block number 1. Say go when ready.'}" --once`
- Observe NLP outputs:
  - `ros2 topic echo /nlp/out`
