# Cobot Final Experiment Project

This repository contains the final integration experiment project for the graduation of **Felipe Cruz Vasquez** from the **Universidad Nacional de Colombia**, in the **Master's degree in Automatización Industrial - Profundización**.

## Table of Contents
- [System Overview](#system-overview)
- [Prerequisites](#prerequisites)
- [Module Setup (venv + dependencies)](#module-setup-venv--dependencies)
- [Run](#run)
- [User Manual (Flow to Play)](#user-manual-flow-to-play)
- [ABB Robot](#abb-robot)
- [Notes](#notes)

## System Overview
The project integrates:
- `GridTwin`: digital twin + CIF-supervised grid simulation.
- `Planner`: PlanSys2/PDDL high-level planner.
- `NLP`: voice input/output interface for human interaction.
- `ABB`: ROS-to-TCP bridge for robot controller communication.
- `Orchestrator`: central ROS bridge coordinating all module interactions.

## Prerequisites
- ROS2 and PlanSys2 must be installed on the machine.
- ROS2 CLI/runtime must be available in your shell `PATH` (environment enabled globally on this machine setup).
- CIF simulator (`cifsim`) from Eclipse ESCET must be installed on the machine.
- In `GridTwin/supervisor.py`, `base_cmd` must point to your local `cifsim` binary path.
- Vosk speech model for NLP must exist at:
  - `NLP/model/vosk-model-small-en-us-0.15`

## Module Setup (venv + dependencies)
Create one `venv` inside each module folder and install dependencies:

### Orchestrator
- `cd Orchestrator`
- `python3 -m venv venv`
- `./venv/bin/pip install rclpy`

### ABB
- `cd ABB`
- `python3 -m venv venv`
- `./venv/bin/pip install rclpy`

### NLP
- `cd NLP`
- `python3 -m venv venv`
- `./venv/bin/pip install rclpy speechrecognition pyaudio pyttsx3 vosk`
- System dependency for `pyaudio`: `sudo apt-get install -y libportaudio2 portaudio19-dev`
- Download/extract Vosk model from `https://alphacephei.com/vosk/models` and place it at:
  - `NLP/model/vosk-model-small-en-us-0.15`

### Planner
- `cd Planner`
- `python3 -m venv venv`
- `./venv/bin/pip install rclpy`

### GridTwin
- `cd GridTwin`
- `python3 -m venv venv`
- `./venv/bin/pip install rclpy pygame`

## Run
1. Open a terminal at repo root.
2. Run `python3 Main.py`.
3. This opens independent terminals in this order:
   `Orchestrator`, `ABB`, `NLP`, `Planner`, `GridTwin`.
4. `GridTwin` also opens a Python `pygame` game window.

## User Manual (Flow to Play)
1. Launch the system with `python3 Main.py`.
2. In the `pygame` GridTwin window, build the scenario in setup mode:
   - Place blocks and goals using the GridTwin controls.
   - Setup controls:
     - `r`: red block brush
     - `g`: green block brush
     - `b`: blue block brush
     - `k`: black block brush
     - `x`: goal marker brush
     - `0`: eraser brush
     - Left click: apply selected brush on a cell
     - Right click: remove block/goal on a cell
3. Start the experiment by saying `start`.
4. When planner asks for a user move:
   - Move the indicated block physically.
   - Say `done` to confirm movement.
   - Optional: say `space` if you need robot repositioning room.
5. When planner asks for a robot move:
   - Say `go` to authorize robot execution.
6. If any module reports an error:
   - Fix the issue (and align physical grid with UI grid).
   - Say `fixed` to continue (this triggers replanning).
7. Goal condition:
   - When all red blocks reach goal cells, the system announces completion.
   - GridTwin shows the win state (`YOU WIN`) and final counters/time in the UI.

## ABB Robot
The ABB module (`ABB/main.py`) bridges ROS messages to TCP commands for the robot controller.

- Main configuration is in `Orchestrator/ros_constants.py`:
  - `ABB_TEST_MODE`
  - `ABB_HOST`
  - `ABB_PORT`
  - `ABB_TIMEOUT`

- Test mode (no robot hardware):
  - Set `ABB_TEST_MODE = True`.
  - ABB module skips TCP connection attempts.
  - Any command on `/abb/in` returns `/abb/out: ok` immediately.
  - Use this to validate end-to-end orchestration without the real robot.

- Real robot mode:
  - Set `ABB_TEST_MODE = False`.
  - Configure `ABB_HOST`/`ABB_PORT` to the real controller endpoint.
  - Ensure network reachability between this PC and the ABB controller.

- RAPID code:
  - Current RAPID files are in `ABB/RAPID/`.
  - `ABB/RAPID/MainModule.mod` is currently a partial/base implementation.
  - Final RAPID motion logic and full controller-side behavior are pending and can be completed later.

## Notes
- `Planner/main.py` launches PlanSys2 in a separate terminal automatically.
- `GridTwin` launches an additional separate terminal for the CIF supervisor process (`cifsim`) so you can monitor supervisory output.
