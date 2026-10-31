"""OptiCore Camera Streamer Module.

Captures frames from a local or remote webcam, Raspberry Pi camera, or video file,
and streams compressed JPEG frames over WebSocket to the OptiCore Vision Server (/ws/video).
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from typing import Optional, Union

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    import websockets
except ImportError:
    websockets = None

from opticore_cli.config import ConfigManager


def convert_to_ws_url(server_url: str) -> str:
    """Convert an HTTP(S) URL into a WebSocket (ws:// or wss://) /ws/video URL."""
    clean = server_url.strip().rstrip("/")
    if clean.startswith("https://"):
        clean = "wss://" + clean[8:]
    elif clean.startswith("http://"):
        clean = "ws://" + clean[7:]
    elif not clean.startswith("ws://") and not clean.startswith("wss://"):
        clean = "wss://" + clean

    if not clean.endswith("/ws/video"):
        clean += "/ws/video"
    return clean


async def stream_camera(
    server_url: str,
    camera_source: Union[int, str] = "0",
    width: int = 640,
    target_fps: float = 15.0,
    quality: int = 65,
    show_window: bool = False,
) -> int:
    """Capture frames and stream over WebSocket to OptiCore server."""
    if cv2 is None or websockets is None:
        print("[ERROR] Missing required packages for camera streaming.")
        print("Please install them: pip install opencv-python websockets")
        return 1

    ws_url = convert_to_ws_url(server_url)

    # Determine camera source: integer index or file/stream URL
    try:
        source: Union[int, str] = int(camera_source)
    except ValueError:
        source = str(camera_source)

    print(f"[*] Opening camera source: {source}...")
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Could not open camera source: {source}")
        print("Tip: If using a USB webcam, check index (0, 1). On Raspberry Pi, verify camera permissions.")
        return 1

    # Request desired capture resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(width * 0.75))

    frame_interval = 1.0 / max(1.0, target_fps)
    print(f"[*] Connecting to OptiCore Vision WebSocket: {ws_url}")
    print(f"[*] Streaming at max {target_fps} FPS (width: {width}px, quality: {quality}%)...")
    print("[*] Press Ctrl+C in this terminal to stop streaming.\n")

    frames_sent = 0
    start_time = time.time()

    try:
        async with websockets.connect(
            ws_url,
            max_size=8 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            print("[+] Connected to OptiCore server! Live camera feed is active.")

            while cap.isOpened():
                loop_start = time.perf_counter()

                ret, frame = cap.read()
                if not ret:
                    print("\n[!] Camera feed ended or frame could not be read.")
                    break

                # Resize if wider than requested width
                h, w = frame.shape[:2]
                if w > width:
                    new_h = int(h * width / w)
                    frame = cv2.resize(frame, (width, new_h), interpolation=cv2.INTER_AREA)

                # Encode frame to JPEG binary buffer
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                ok, encimg = cv2.imencode(".jpg", frame, encode_param)
                if not ok:
                    continue

                payload = encimg.tobytes()

                # Send binary JPEG payload to server
                await ws.send(payload)
                frames_sent += 1

                # Receive response JSON containing detections and annotated image
                raw_response = await ws.recv()
                try:
                    data = json.loads(raw_response)
                except Exception:
                    data = {}

                # Check if server returned busy error
                if data.get("type") == "error":
                    print(f"\n[SERVER ERROR] {data.get('code')}: {data.get('message')}")
                    break

                inference_ms = data.get("inference_ms", 0.0)
                detections = data.get("detections", [])
                alerts = data.get("alerts", [])

                # Format terminal status line
                det_summary = ", ".join(f"{d.get('name')} ({d.get('confidence', 0)*100:.0f}%)" for d in detections[:3])
                if len(detections) > 3:
                    det_summary += f" +{len(detections)-3} more"
                if not det_summary:
                    det_summary = "None"

                alert_badge = f" [!] {alerts[0].get('message')}" if alerts else ""

                elapsed = time.time() - start_time
                fps = frames_sent / max(0.1, elapsed)

                sys.stdout.write(
                    f"\r[STREAMING] FPS: {fps:.1f} | Latency: {inference_ms:.1f}ms | Detections: {det_summary}{alert_badge}   "
                )
                sys.stdout.flush()

                # Optional local GUI preview window
                if show_window and "image" in data and data["image"]:
                    try:
                        img_bytes = base64.b64decode(data["image"])
                        annotated = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if annotated is not None:
                            cv2.imshow("OptiCore Live Stream (Server Annotated)", annotated)
                            if cv2.waitKey(1) & 0xFF == ord("q"):
                                print("\nQuitting preview window.")
                                break
                    except Exception:
                        pass

                # Maintain target FPS
                elapsed_frame = time.perf_counter() - loop_start
                sleep_time = frame_interval - elapsed_frame
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\n[!] WebSocket closed by server: {e}")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n[!] Connection refused: HTTP {e.status_code}")
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("\n[*] Stopping stream (interrupted by user)...")
    finally:
        cap.release()
        if show_window and cv2 is not None:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        print(f"\n[+] Stream finished. Total frames sent: {frames_sent}")

    return 0


def run_camera_stream_sync(
    server_url: str,
    camera_source: Union[int, str] = "0",
    width: int = 640,
    target_fps: float = 15.0,
    quality: int = 65,
    show_window: bool = False,
) -> int:
    """Synchronous wrapper to run stream_camera inside an asyncio loop."""
    try:
        return asyncio.run(
            stream_camera(
                server_url=server_url,
                camera_source=camera_source,
                width=width,
                target_fps=target_fps,
                quality=quality,
                show_window=show_window,
            )
        )
    except KeyboardInterrupt:
        print("\nCamera stream stopped.")
        return 0


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Stream local/remote camera to OptiCore Vision Server (/ws/video)."
    )
    config = ConfigManager().load()

    parser.add_argument(
        "--server",
        default=config.server_url,
        help="OptiCore server base URL (e.g. https://xxxx.ngrok-free.app). Defaults to saved config.",
    )
    parser.add_argument(
        "--camera",
        default=config.camera_source,
        help="Camera device index (e.g. 0, 1) or video file / RTSP path (default: 0).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=config.camera_width,
        help="Capture frame width (default: 640).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=config.camera_fps,
        help="Target frames per second to stream (default: 15.0).",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=config.camera_quality,
        help="JPEG compression quality 1-100 (default: 65).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        default=config.camera_show_preview,
        help="Display local preview window with server-annotated detections.",
    )

    args = parser.parse_args(argv)

    if not args.server:
        print("[ERROR] No server URL provided.")
        print("Specify with --server https://xxxx.ngrok-free.app or configure via 'opticore-cli connect <url>'")
        sys.exit(1)

    code = run_camera_stream_sync(
        server_url=args.server,
        camera_source=args.camera,
        width=args.width,
        target_fps=args.fps,
        quality=args.quality,
        show_window=args.show,
    )
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
