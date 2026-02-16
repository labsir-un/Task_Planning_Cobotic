from __future__ import annotations

# ROS topic names (shared across modules)
TOPIC_CIF_START = "cif/start"
TOPIC_CIF_MOVE = "cif/move"
TOPIC_CIF_MOVE_EVENT = "cif/move_event"

# ABB bridge topics
TOPIC_ABB_COMMAND = "abb/command"
TOPIC_ABB_RESULT = "abb/result"
ABB_HOST = "127.0.0.1"
ABB_PORT = 8000
ABB_TIMEOUT = 60.0

TOPIC_NLP_COMMAND = "nlp/command"
TOPIC_NLP_MESSAGE = "nlp/message"

# Allowed payload values
CIF_MOVE_COLORS = ("blue", "green")
CIF_MOVE_DIRECTIONS = ("up", "down", "left", "right")

NLP_USER_COMMANDS = ("start", "move")
