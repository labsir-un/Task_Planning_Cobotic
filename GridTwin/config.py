from __future__ import annotations

from pygame import Color

# Board setup
GRID_SIZE: int = 10
TILE_SIZE: int = 50
PADDING: int = 5

# UI
INFO_PANEL_HEIGHT: int = 180
FPS: int = 60

# Colors
BACKGROUND_COLOR: Color = Color("#ffffff")
GRID_COLOR: Color = Color("#555555")
HIGHLIGHT_COLOR: Color = Color("#ffd54f")
GOAL_COLOR: Color = Color("#ff0000")
TEXT_COLOR: Color = Color("#000000")
WIN_TEXT_COLOR: Color = Color("#777777")

# Agent
AGENT_STEP_INTERVAL: float = 1
