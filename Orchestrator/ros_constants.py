from __future__ import annotations

# ROS topic names (shared across modules)
TOPIC_NLP_START = "/nlp/start"
TOPIC_NLP_IN = "/nlp/in"
TOPIC_NLP_OUT = "/nlp/out"

TOPIC_PLANNER_START = "/planner/start"
TOPIC_PLANNER_IN = "/planner/in"
TOPIC_PLANNER_OUT = "/planner/out"

TOPIC_GRIDTWIN_START = "/gridtwin/start"
TOPIC_GRIDTWIN_IN = "/gridtwin/in"
TOPIC_GRIDTWIN_OUT = "/gridtwin/out"

TOPIC_ABB_START = "/abb/start"
TOPIC_ABB_IN = "/abb/in"
TOPIC_ABB_OUT = "/abb/out"

# ABB bridge config
ABB_HOST = "192.168.125.1"
ABB_PORT = 8000
ABB_TIMEOUT = 60.0
ABB_TEST_MODE = True

# Allowed payload values
DIRECTIONS = ("up", "down", "left", "right")
PLAYER_COLORS = ("blue", "green")
ROBOT_COLORS = ("red", "green")
