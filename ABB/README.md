# ABB Bridge

ROS 2 node that forwards `abb/command` to the ABB controller over TCP and publishes execution results on `abb/result`.

## Topics
- Subscribes: `abb/command` (std_msgs/String, JSON `{ "color": str, "id": int, "dir": "up|down|left|right" }`)
- Publishes: `abb/result` (std_msgs/String, JSON `{ "ok": bool }`)

## TCP payload
- Sends the raw JSON string received on `abb/command` to the ABB controller via TCP.
- Expects a single-byte/small reply: `"1"` for success, anything else for failure.
- Logs every send/receive.

## Run
```
./venv/bin/python ABB/main.py
```
Ensure ROS 2 environment is sourced and the ABB controller socket server is reachable.

## Test
- Publish a sample ROS command to the bridge (it will format to `XXYYD` before TCP):
  ```bash
  ros2 topic pub /abb/command std_msgs/msg/String "{data: '{\"x\":0,\"y\":1,\"color\":\"red\",\"id\":1,\"dir\":\"right\"}'}" --once
  ```
