from __future__ import annotations

# ROS topic names (shared across modules)
TOPIC_CIF_START = "cif/start"
TOPIC_CIF_MOVE = "cif/move"
TOPIC_CIF_MOVE_EVENT = "cif/move_event"

TOPIC_NLP_COMMAND = "nlp/command"
TOPIC_NLP_MESSAGE = "nlp/message"

# Allowed payload values
CIF_MOVE_COLORS = ("blue", "green")
CIF_MOVE_DIRECTIONS = ("up", "down", "left", "right")

NLP_USER_COMMANDS = ("start", "move")
