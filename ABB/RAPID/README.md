# Modules

This folder contains two RAPID modules:

- `MotionPlanning.mod`
- `MotionPlanningSim.mod`

`MotionPlanning.mod` is the runtime module intended for real robot operation with TCP socket communication.  
`MotionPlanningSim.mod` is the simulation module for RobotStudio testing without sockets.

Both modules share the same core motion logic:

- Same 3-point grid calibration model
- Same movement sequence
- Same direction semantics (`L/R/U/D`)
- Same error fallback to init position

Current calibration points in code:

- `pCal20` -> grid `(2,0)`
- `pCal70` -> grid `(7,0)`
- `pCal56` -> grid `(5,5)`

Current init/wait joint position:

- `jWaitPos = [[0, -45, 45, 0, 90, 180], ...]`

# Inputs

TCP commands (real module) are received as strings.

Supported inputs:

1. Movement command: `XXYYD`
- `XX`: X index (2 digits, `00` to `09`)
- `YY`: Y index (2 digits, `00` to `09`)
- `D`: direction letter (`L`, `R`, `U`, `D`)

Example:
- `0203D`

2. Special command: `XXXXX`
- Moves robot to init position.

Validation rules:

- Length must be exactly 5 characters.
- X and Y must parse as numbers.
- X and Y must be in `0..9`.
- Direction must be one of `L/R/U/D`.

Any invalid input is treated as failure.

# Movement

For each valid movement command, robot executes:

1. Move above start cell (`approachHeightMm` over plane)
2. Move down to working plane
3. Move one cell in requested direction on plane
4. Move up from plane
5. Hold there

Direction semantics are currently inverted relative to the original internal mapping to match user perspective.

If any runtime motion error happens:

- Robot goes to init position (`MoveInitPosition`)
- Command is treated as failure

# Outputs

TCP outputs (`MotionPlanning.mod`):

- `"1"`: command executed successfully
- `"0"`: invalid payload, invalid movement (out of reachable area), or runtime error

For special command:

- Input `XXXXX` -> robot moves to init and returns `"1"`

# Setup

To run on real ABB controller:

1. Copy `MotionPlanning.mod` to the controller task (`T_ROB1`).
2. Ensure `tool0` and `wobj0` are available (normally from system module `BASE`).
3. Set socket network parameters in module:
- `ipController`
- `port`

4. Calibrate and update these constants (see calibration section below):
- `pCal20` (real position of grid cell `(2,0)`)
- `pCal70` (real position of grid cell `(7,0)`)
- `pCal56` (real position of grid cell `(5,5)`)
- `jWaitPos` (desired init/wait joint target)
- Optional: `approachHeightMm`

5. Review speed constants as needed:
- `vSafeJoint`
- `vSafeApproach`
- `vSafeWork`

6. Start `main`.

Notes:

- Module is self-contained in logic: copy and run after calibrating the constants above.

# Calibration
Un-comment the `! CalibrateGrid;` in the main function.
- `CalibrateGrid` moves repeatedly through calibrated points at working height with 3-second dwell.
- You will have to adjust the calibration points and re-run the module each time.
- Be careful! First try to adjust the vertical height of the points with no obstacles around (to avoid collisions).

# Test mode

`MotionPlanningSim.mod` is a no-socket test mode for RobotStudio simulation.

How it works:

- Uses same movement/calibration logic as real module.
- Runs local tests from `main` using `ExecuteCommand "XXYYD"`.
- No TCP dependency.

Current `main` flow:

1. Move to init
2. Wait 5 seconds
3. Execute 4 test commands:
- `0203D`
- `0504U`
- `0903L`
- `0005R`