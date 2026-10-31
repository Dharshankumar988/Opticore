"""OptiCore Camera Streamer.

Delegates to opticore_cli.camera module to stream webcam or Pi camera frames
over WebSocket to the OptiCore Vision Server (/ws/video).
"""

from opticore_cli.camera import (
    convert_to_ws_url,
    main,
    run_camera_stream_sync,
    stream_camera,
)

if __name__ == "__main__":
    main()
