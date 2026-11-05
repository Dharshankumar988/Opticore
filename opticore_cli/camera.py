"""OptiCore Camera Streamer Module.

Captures frames from a local or remote webcam, Raspberry Pi camera, or video file,
and streams compressed JPEG frames over WebSocket to the OptiCore Vision Server (/ws/video).
Provides CameraStreamManager for clean background ON/OFF lifecycle management.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple, Union

# Prevent Qt from attempting to connect to an X11/Wayland display and aborting on headless systems
if sys.platform != "win32" and "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


OBSTACLE_GROUP = {"pole", "tree", "bench", "chair", "waste_container", "obstacle"}


def synthesize_detection_alert(d: dict) -> dict:
    raw_name = str(d.get("name", "")).strip().lower()
    pos = str(d.get("position", "ahead")).strip().lower()
    side = "on your left" if pos == "left" else "on your right" if pos == "right" else "ahead"
    approaching = bool(d.get("approaching", False))
    approach_dir = d.get("approach_direction")

    if raw_name in OBSTACLE_GROUP:
        display_name = "obstacle"
        class_p = 6
        prio = "P3"
        msg = f"There is an obstacle {side}."
    elif raw_name in {"car", "truck", "bus"}:
        display_name = raw_name
        class_p = 1
        prio = "P1" if approaching else "P2"
        if approaching and approach_dir:
            msg = f"A {raw_name} is approaching {approach_dir}."
        else:
            msg = f"There is a {raw_name} {side}."
    elif raw_name in {"motorcycle", "bicycle"}:
        display_name = raw_name
        class_p = 2
        prio = "P1" if approaching else "P2"
        if approaching and approach_dir:
            msg = f"A {raw_name} is approaching {approach_dir}."
        else:
            msg = f"There is a {raw_name} {side}."
    elif raw_name in {"pothole", "crack", "manhole"}:
        display_name = raw_name
        class_p = 2
        prio = "P2"
        msg = f"There is a {raw_name} {side}."
    elif raw_name == "animal":
        display_name = "animal"
        class_p = 3
        prio = "P2" if approaching else "P3"
        if approaching and approach_dir:
            msg = f"An animal is approaching {approach_dir}."
        else:
            msg = f"There is an animal {side}."
    elif raw_name == "person":
        display_name = "person"
        class_p = 3
        prio = "P2" if approaching else "P3"
        if approaching and approach_dir:
            msg = f"A person is approaching {approach_dir}."
        else:
            msg = f"There is a person {side}."
    elif raw_name == "stairs":
        display_name = "stairs"
        class_p = 4
        prio = "P3"
        msg = f"There are stairs {side}."
    elif raw_name == "door":
        display_name = "door"
        class_p = 4
        prio = "P3"
        msg = f"There is a door {side}."
    elif raw_name in {"traffic_light", "traffic_sign"}:
        display_name = raw_name.replace("_", " ")
        class_p = 5
        prio = "P3"
        msg = f"There is a {display_name} {side}."
    else:
        display_name = raw_name.replace("_", " ")
        class_p = 6
        prio = "P4"
        article = "an" if display_name[:1] in "aeiou" else "a"
        msg = f"There is {article} {display_name} {side}."

    return {
        "timestamp": time.time(),
        "track_id": d.get("id"),
        "name": display_name,
        "confidence": d.get("confidence", 0.0),
        "class_priority": d.get("class_priority", class_p),
        "position": pos,
        "approaching": approaching,
        "approach_direction": approach_dir,
        "priority": d.get("priority", prio),
        "risk_score": d.get("risk_score", 70 if class_p <= 2 else 40),
        "message": msg,
    }


class SuppressStderr:
    """Temporarily suppresses OS-level stderr (fd 2) to silence C++ OpenCV logs."""

    def __enter__(self):
        try:
            self.null_fd = os.open(os.devnull, os.O_RDWR)
            self.save_stderr = os.dup(2)
            os.dup2(self.null_fd, 2)
        except Exception:
            self.save_stderr = None

    def __exit__(self, *args):
        if getattr(self, "save_stderr", None) is not None:
            try:
                os.dup2(self.save_stderr, 2)
                os.close(self.save_stderr)
                os.close(self.null_fd)
            except Exception:
                pass


def detect_cameras(max_probe: int = 4) -> List[Dict[str, str]]:
    """Probes system for available video capture devices cross-platform.
    Returns list of dicts with keys: 'index', 'resolution', 'label'.
    """
    found_cameras = []

    # 1. Probe for Raspberry Pi Camera Module (CSI Ribbon Cable) via Picamera2
    try:
        from picamera2 import Picamera2
        with SuppressStderr():
            picam2 = Picamera2()
            cinfo = getattr(picam2, "camera_info", [])
            model = cinfo[0].get("Model", "Pi Camera Module") if cinfo else "Pi Camera (CSI)"
            found_cameras.append({
                "index": "0",
                "resolution": "2592x1944" if "5647" in model else "1920x1080",
                "label": f"Raspberry Pi Camera [{model}] (Picamera2)",
            })
            picam2.close()
    except Exception:
        pass

    if cv2 is None:
        return found_cameras

    has_picam_0 = any(c["index"] == "0" for c in found_cameras)
    start_idx = 1 if has_picam_0 else 0

    with SuppressStderr():
        for idx in range(start_idx, max_probe):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, _ = cap.read()
                if not ret:
                    time.sleep(0.05)
                    ret, _ = cap.read()
                if ret:
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    label = f"Camera {idx}"

                    # Linux device name check
                    sys_name_path = f"/sys/class/video4linux/video{idx}/name"
                    if os.path.exists(sys_name_path):
                        try:
                            with open(sys_name_path, "r", encoding="utf-8") as f:
                                dev_name = f.read().strip()
                                if dev_name:
                                    label += f" ({dev_name})"
                        except Exception:
                            pass
                    else:
                        if idx == 0:
                            label += " (Default / Integrated)"
                        elif idx == 1:
                            label += " (External / USB)"
                        else:
                            label += " (Auxiliary)"

                    found_cameras.append({
                        "index": str(idx),
                        "resolution": f"{w}x{h}",
                        "label": label,
                    })
                cap.release()

    return found_cameras


def open_camera_capture(camera_source: Union[int, str], width: int = 640):
    """Opens a video capture instance with automatic Picamera2 support on Raspberry Pi."""
    # 1. Automatic Picamera2 support for CSI camera modules on Raspberry Pi
    if str(camera_source).strip().lower() in {"0", "picam", "csi", "pi"}:
        try:
            from picamera2 import Picamera2

            class PiCamera2Wrapper:
                def __init__(self, w: int):
                    self.picam2 = Picamera2()
                    h = int(w * 0.75)
                    cfg = self.picam2.create_video_configuration(main={"size": (w, h), "format": "RGB888"})
                    self.picam2.configure(cfg)
                    self.picam2.start()

                def isOpened(self) -> bool:
                    return self.picam2 is not None

                def read(self):
                    try:
                        arr = self.picam2.capture_array()
                        if arr is not None:
                            # Picamera2 native array is RGB; reverse channels so Red is Red, Blue is Blue, and skin is natural
                            arr = arr[:, :, ::-1]
                        return True, arr
                    except Exception:
                        return False, None

                def release(self):
                    try:
                        self.picam2.stop()
                        self.picam2.close()
                    except Exception:
                        pass

            wrapper = PiCamera2Wrapper(width)
            for _ in range(8):
                ok, tframe = wrapper.read()
                if ok and tframe is not None:
                    return wrapper, "picamera2"
                time.sleep(0.1)
        except Exception:
            pass

    # 2. Standard OpenCV VideoCapture
    if cv2 is None:
        return None, "none"

    try:
        source: Union[int, str] = int(camera_source)
    except ValueError:
        source = str(camera_source)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened() and isinstance(source, int) and hasattr(cv2, "CAP_V4L2"):
        cap = cv2.VideoCapture(source, cv2.CAP_V4L2)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(width * 0.75))
        # Warmup sensor buffers (crucial for ov5647 / libcamerify on Raspberry Pi)
        for _ in range(15):
            ret, _ = cap.read()
            if ret:
                break
            time.sleep(0.1)
        return cap, "opencv"

    return cap, "failed"


class CameraStreamManager:
    """Manages background camera streaming lifecycle with simple ON/OFF toggling."""

    def __init__(self, config_manager: ConfigManager, voice_engine: Optional[object] = None):
        self.config_manager = config_manager
        self.voice_engine = voice_engine
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started_event = threading.Event()
        self._is_active = False
        self._last_error = ""
        self.frames_sent = 0
        self.fps_estimate = 0.0
        self.latency_ms = 0.0
        self.active_source = "0"

    @property
    def is_active(self) -> bool:
        return self._is_active and self._thread is not None and self._thread.is_alive()

    def start(self, server_url: str = "") -> Tuple[bool, str]:
        """Starts streaming the camera in the background."""
        if self.is_active:
            return True, "Camera stream is already active."

        cfg = self.config_manager.config
        url = server_url or cfg.server_url
        if not url:
            return False, "Server URL is not configured. Connect to server first."

        self._stop_event.clear()
        self._started_event.clear()
        self._last_error = ""
        self.frames_sent = 0
        self.active_source = str(cfg.camera_source)

        def _worker():
            self._is_active = True
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self._run_stream(
                        server_url=url,
                        camera_source=cfg.camera_source,
                        width=cfg.camera_width,
                        target_fps=cfg.camera_fps,
                        quality=cfg.camera_quality,
                        show_window=cfg.camera_show_preview,
                    )
                )
            except Exception as e:
                self._last_error = str(e)
            finally:
                self._is_active = False
                loop.close()

        self._thread = threading.Thread(target=_worker, name="OptiCore-CameraStreamer", daemon=True)
        self._thread.start()

        # Wait briefly for worker to initialize or report immediate failure
        self._started_event.wait(timeout=1.5)
        if self._last_error:
            self._is_active = False
            return False, self._last_error

        return True, f"Camera Device {self.active_source} is now streaming to {url}."

    def stop(self) -> Tuple[bool, str]:
        """Stops the active background camera stream."""
        if not self.is_active:
            return True, "Camera stream is not active."

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)

        self._is_active = False
        return True, "Camera stream stopped."

    def toggle(self, server_url: str = "") -> Tuple[bool, str]:
        """Toggles camera stream ON or OFF."""
        if self.is_active:
            return self.stop()
        else:
            return self.start(server_url)

    def get_status_dict(self) -> dict:
        return {
            "active": self.is_active,
            "source": self.active_source,
            "frames_sent": self.frames_sent,
            "fps": round(self.fps_estimate, 1),
            "latency_ms": round(self.latency_ms, 1),
            "last_error": self._last_error,
        }

    async def _run_stream(self, server_url, camera_source, width, target_fps, quality, show_window):
        if cv2 is None or websockets is None:
            self._last_error = "OpenCV or websockets not installed."
            self._started_event.set()
            return

        is_linux = sys.platform.startswith("linux")
        has_display = True if not is_linux else bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if show_window and not has_display:
            show_window = False

        ws_url = convert_to_ws_url(server_url)
        cap, _ = open_camera_capture(camera_source, width)
        if cap is None or not cap.isOpened():
            self._last_error = f"Could not open camera device '{camera_source}'."
            self._started_event.set()
            return

        frame_interval = 1.0 / max(1.0, target_fps)

        try:
            async with websockets.connect(
                ws_url,
                max_size=8 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                self._started_event.set()
                start_time = time.time()
                consecutive_fails = 0
                max_consecutive_fails = 15

                while cap.isOpened() and not self._stop_event.is_set():
                    loop_start = time.perf_counter()
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        consecutive_fails += 1
                        if consecutive_fails < max_consecutive_fails:
                            await asyncio.sleep(0.1)
                            continue
                        break
                    consecutive_fails = 0

                    h, w = frame.shape[:2]
                    if w > width:
                        new_h = int(h * width / w)
                        frame = cv2.resize(frame, (width, new_h), interpolation=cv2.INTER_AREA)

                    ok, encimg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    if not ok:
                        continue

                    await ws.send(encimg.tobytes())
                    self.frames_sent += 1

                    raw_resp = await ws.recv()
                    data = {}
                    try:
                        data = json.loads(raw_resp)
                        if data.get("type") == "error":
                            if data.get("code") == "producer_busy":
                                self._last_error = (
                                    "Another camera stream is active on the server. "
                                    "Please close any browser tab streaming to the server first."
                                )
                            else:
                                self._last_error = data.get("message", "Server rejected stream.")
                            break
                        self.latency_ms = data.get("inference_ms", 0.0)

                        # Enqueue alerts directly to voice engine if active
                        if self.voice_engine and getattr(self.voice_engine, "enabled", False):
                            from opticore_cli.models import DetectionEvent
                            alerts_to_speak = list(data.get("alerts", []))
                            if not alerts_to_speak and data.get("detections"):
                                sorted_dets = sorted(
                                    data.get("detections", []),
                                    key=lambda x: (
                                        1 if str(x.get("name")).lower() in {"car", "truck", "bus"} else
                                        2 if str(x.get("name")).lower() in {"motorcycle", "bicycle", "pothole", "crack", "manhole"} else
                                        3 if str(x.get("name")).lower() in {"person", "animal"} else
                                        4 if str(x.get("name")).lower() in {"door", "stairs"} else
                                        5 if str(x.get("name")).lower() in {"traffic_light", "traffic_sign"} else 6,
                                        -float(x.get("confidence", 0.0))
                                    )
                                )
                                if sorted_dets:
                                    alerts_to_speak.append(synthesize_detection_alert(sorted_dets[0]))

                            # Enqueue top alert to prevent overlapping/stuttering speech
                            for alert_dict in alerts_to_speak[:1]:
                                try:
                                    event = DetectionEvent.from_dict(alert_dict)
                                    self.voice_engine.enqueue_event(event)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    elapsed = time.time() - start_time
                    self.fps_estimate = self.frames_sent / max(0.1, elapsed)

                    # Optional local GUI window
                    if show_window and "image" in data and data["image"]:
                        try:
                            img_bytes = base64.b64decode(data["image"])
                            annotated = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if annotated is not None:
                                cv2.imshow("OptiCore Live Stream (Server Annotated)", annotated)
                                if cv2.waitKey(1) & 0xFF == ord("q"):
                                    break
                        except Exception:
                            pass

                    elapsed_frame = time.perf_counter() - loop_start
                    sleep_time = frame_interval - elapsed_frame
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

        except websockets.exceptions.InvalidStatusCode as e:
            self._last_error = f"Connection refused by server (HTTP {e.status_code})."
            self._started_event.set()
        except Exception as e:
            self._last_error = f"Camera streaming error: {e}"
            self._started_event.set()
        finally:
            cap.release()
            if show_window and cv2 is not None:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
            self._is_active = False


async def stream_camera(
    server_url: str,
    camera_source: Union[int, str] = "0",
    width: int = 640,
    target_fps: float = 15.0,
    quality: int = 65,
    show_window: bool = False,
    stop_event: Optional[threading.Event] = None,
    voice_engine: Optional[object] = None,
    swap_rb: bool = False,
) -> int:
    """Capture frames and stream over WebSocket to OptiCore server (foreground CLI mode)."""
    if cv2 is None or websockets is None:
        print("[ERROR] Missing required packages for camera streaming.")
        print("Please install them: pip install opencv-python websockets")
        return 1

    is_linux = sys.platform.startswith("linux")
    has_display = True if not is_linux else bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if show_window and not has_display:
        show_window = False

    ws_url = convert_to_ws_url(server_url)

    print(f"[*] Opening camera source: {camera_source}...")
    cap, backend = open_camera_capture(camera_source, width)
    if cap is None or not cap.isOpened():
        print(f"[ERROR] Could not open camera source: {camera_source}")
        print("Tip: If using a USB webcam, check index (0, 1).")
        print("Tip: On Raspberry Pi Bookworm with a CSI ribbon camera, run with: libcamerify python stream_camera.py")
        return 1

    if backend == "picamera2":
        print("[+] Native Raspberry Pi Camera (Picamera2) initialized successfully!")

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
            consecutive_fails = 0
            max_consecutive_fails = 15

            while cap.isOpened() and (stop_event is None or not stop_event.is_set()):
                loop_start = time.perf_counter()

                ret, frame = cap.read()
                if not ret or frame is None:
                    consecutive_fails += 1
                    if consecutive_fails < max_consecutive_fails:
                        await asyncio.sleep(0.1)
                        continue
                    print("\n[!] Camera feed ended or frame could not be read.")
                    break

                consecutive_fails = 0

                if swap_rb and frame is not None:
                    frame = frame[:, :, ::-1]

                h, w = frame.shape[:2]
                if w > width:
                    new_h = int(h * width / w)
                    frame = cv2.resize(frame, (width, new_h), interpolation=cv2.INTER_AREA)

                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                ok, encimg = cv2.imencode(".jpg", frame, encode_param)
                if not ok:
                    continue

                await ws.send(encimg.tobytes())
                frames_sent += 1

                raw_response = await ws.recv()
                try:
                    data = json.loads(raw_response)
                except Exception:
                    data = {}

                if data.get("type") == "error":
                    print(f"\n[SERVER ERROR] {data.get('code')}: {data.get('message')}")
                    break

                inference_ms = data.get("inference_ms", 0.0)
                detections = data.get("detections", [])
                alerts = data.get("alerts", [])

                # Enqueue alerts to voice engine if active
                if voice_engine and getattr(voice_engine, "enabled", False):
                    from opticore_cli.models import DetectionEvent
                    alerts_to_speak = list(alerts)
                    if not alerts_to_speak and detections:
                        sorted_dets = sorted(
                            detections,
                            key=lambda x: (
                                1 if str(x.get("name")).lower() in {"car", "truck", "bus"} else
                                2 if str(x.get("name")).lower() in {"motorcycle", "bicycle", "pothole", "crack", "manhole"} else
                                3 if str(x.get("name")).lower() in {"person", "animal"} else
                                4 if str(x.get("name")).lower() in {"door", "stairs"} else
                                5 if str(x.get("name")).lower() in {"traffic_light", "traffic_sign"} else 6,
                                -float(x.get("confidence", 0.0))
                            )
                        )
                        if sorted_dets:
                            alerts_to_speak.append(synthesize_detection_alert(sorted_dets[0]))

                    # Enqueue top alert to prevent overlapping speech
                    for a_dict in alerts_to_speak[:1]:
                        try:
                            ev = DetectionEvent.from_dict(a_dict)
                            voice_engine.enqueue_event(ev)
                        except Exception:
                            pass

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
    voice_engine: Optional[object] = None,
    swap_rb: bool = False,
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
                voice_engine=voice_engine,
                swap_rb=swap_rb,
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
        dest="show",
        action="store_true",
        default=config.camera_show_preview,
        help="Display local preview window with server-annotated detections.",
    )
    parser.add_argument(
        "--no-show",
        dest="show",
        action="store_false",
        help="Disable GUI preview window (required for headless / SSH mode).",
    )
    parser.add_argument(
        "--voice",
        dest="voice",
        action="store_true",
        default=True,
        help="Enable local voice alerts for detected objects (default: enabled).",
    )
    parser.add_argument(
        "--no-voice",
        dest="voice",
        action="store_false",
        help="Disable voice alerts explicitly.",
    )
    parser.add_argument(
        "--swap-rb",
        dest="swap_rb",
        action="store_true",
        default=False,
        help="Invert red and blue color channels.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Detect and list all available video input devices.",
    )

    args = parser.parse_args(argv)

    if args.list:
        print("[*] Probing system for connected camera devices...")
        cams = detect_cameras(max_probe=6)
        if not cams:
            print("No camera devices detected.")
        else:
            print(f"Found {len(cams)} camera device(s):")
            for c in cams:
                print(f"  - Device [{c['index']}]: {c['label']} (Max Resolution: {c['resolution']})")
        sys.exit(0)

    if not args.server:
        print("[ERROR] No server URL provided.")
        print("Specify with --server https://xxxx.ngrok-free.app or configure via 'opticore-cli connect <url>'")
        sys.exit(1)

    voice_engine = None
    if getattr(args, "voice", True):
        try:
            from opticore_cli.voice import VoiceAlertEngine
            voice_engine = VoiceAlertEngine(
                enabled=True,
                verbosity=config.voice_verbosity,
                rate=config.voice_rate,
                volume=config.voice_volume,
                cooldown=config.voice_cooldown,
            )
            print(f"[*] Voice alert engine initialized (active, backend: {voice_engine._backend}).")
            voice_engine.speak_text("OptiCore vision active", force=True)
        except Exception as e:
            print(f"[!] Warning: Could not initialize voice engine: {e}")

    try:
        code = run_camera_stream_sync(
            server_url=args.server,
            camera_source=args.camera,
            width=args.width,
            target_fps=args.fps,
            quality=args.quality,
            show_window=args.show,
            voice_engine=voice_engine,
            swap_rb=args.swap_rb,
        )
    finally:
        if voice_engine:
            voice_engine.shutdown()
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
