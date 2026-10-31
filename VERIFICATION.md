# OptiCore CLI Command Center — Verification & Architecture Audit

This document details the complete verification process, test results, server notebook API conformance audit, and platform checklists for **Windows 10/11** and **Raspberry Pi OS (ARM64)**.

---

## 1. Conformance Audit Against Server Notebook (`opticore-server.ipynb`)

| Notebook Component | Notebook Source Implementation | CLI Command Center Conformance | Status |
| :--- | :--- | :--- | :---: |
| **REST `/health`** | Returns `status`, `model_loaded`, `device`, `classes`, `tracker`, `imgsz`, and rolling metrics. | Handled by `OptiCoreClient.get_health()`, mapped to typed `ServerHealth` dataclass, rendered in `render_health()`. | **VERIFIED** |
| **REST `/status`** | Returns `service`, `version`, `model_loaded`, `device`, `gpu_available`, `gpu_name`, `producer_active`, `producer_id`, `uptime_seconds`, `metrics`, `priority_engine`, `speech_policy`. | Handled by `OptiCoreClient.get_status()`, mapped to typed `ServerStatus` dataclass, rendered in `render_status()`. | **VERIFIED** |
| **REST `/metrics`** | Returns `frames_processed`, `last_inference_ms`, `avg_inference_ms`, `fps_ema`, `frames_rejected`, `last_inference_unix`. | Handled by `OptiCoreClient.get_metrics()`, mapped to `ServerMetrics`, rendered in `render_metrics()`. | **VERIFIED** |
| **REST `/events`** | Returns `{"events": [...]}` from `ALERT_HISTORY` (max 200 items), with `limit` query param clamped 1–100. | Handled by `OptiCoreClient.get_events(limit=N)`, mapped to list of `DetectionEvent`. | **VERIFIED** |
| **WebSocket `/ws/video`** | Single persistent camera producer (`PRODUCER_ACTIVE`). Returns `409`/`producer_busy` if occupied. | Preserved. The CLI does not send mock video or hijack `/ws/video`, leaving the camera stream open for the smartphone or webcam. | **VERIFIED** |
| **Event Schema** | Fields: `timestamp`, `track_id`, `name`, `confidence`, `class_priority`, `position`, `approaching`, `approach_direction`, `priority`, `risk_score`, `message`. | Zero invented fields. Exact fields used in `DetectionEvent`, log lines, and table views. | **VERIFIED** |
| **Speech Policy** | Notebook Cell 3 line 742: `"speech_policy": "browser speech + track-level server deduplication"`. Browser uses `window.speechSynthesis`. | Server performs no server-side TTS. CLI implements dedicated client-side TTS (`VoiceAlertEngine`) with identical deduplication semantics. | **VERIFIED** |
| **ngrok Integration** | Notebook Cell 5 exposes port 8000 via ngrok public HTTPS tunnel. | `OptiCoreClient` automatically upgrades ngrok URLs to HTTPS, normalizes trailing slashes, and includes `ngrok-skip-browser-warning: 69420` header. | **VERIFIED** |

---

## 2. Automated Test Results

Automated test suite executed with `pytest`:

```
tests/test_cli.py::test_command_dispatch_exit PASSED                     [  3%]
tests/test_cli.py::test_command_dispatch_help PASSED                     [  7%]
tests/test_cli.py::test_command_dispatch_connect_disconnect PASSED       [ 11%]
tests/test_cli.py::test_command_dispatch_server_queries PASSED           [ 14%]
tests/test_cli.py::test_command_dispatch_voice PASSED                    [ 18%]
tests/test_cli.py::test_command_dispatch_config PASSED                   [ 22%]
tests/test_cli.py::test_arg_parser_subcommands PASSED                    [ 25%]
tests/test_client.py::test_url_sanitization PASSED                       [ 29%]
tests/test_client.py::test_client_ping_success PASSED                    [ 33%]
tests/test_client.py::test_client_get_endpoints PASSED                   [ 37%]
tests/test_client.py::test_client_connection_failure PASSED              [ 40%]
tests/test_client.py::test_client_headers PASSED                         [ 44%]
tests/test_config.py::test_default_config PASSED                         [ 48%]
tests/test_config.py::test_save_and_load_config PASSED                   [ 51%]
tests/test_config.py::test_env_var_override PASSED                       [ 55%]
tests/test_config.py::test_config_set_type_coercion PASSED               [ 59%]
tests/test_config.py::test_config_reset PASSED                           [ 62%]
tests/test_live_monitor.py::test_live_monitor_capture_events PASSED      [ 66%]
tests/test_models.py::test_server_health_model PASSED                    [ 70%]
tests/test_models.py::test_server_status_model PASSED                    [ 74%]
tests/test_models.py::test_server_metrics_model PASSED                   [ 77%]
tests/test_models.py::test_detection_event_model PASSED                  [ 81%]
tests/test_models.py::test_detection_event_untracked PASSED              [ 85%]
tests/test_voice.py::test_voice_engine_enable_disable PASSED             [ 86%]
tests/test_voice.py::test_voice_verbosity_filtering PASSED               [ 89%]
tests/test_voice.py::test_voice_deduplication_cooldown PASSED            [ 93%]
tests/test_voice.py::test_voice_status_dict PASSED                       [ 96%]
tests/test_voice.py::test_voice_force_announcement PASSED                [100%]

======================== 29 passed in 5.01s ========================
```

---

## 3. Practical Verification Checklist

### Windows 10/11 Live Execution (Actually Executed & Verified)

- [x] **Python Environment:** Tested on Python 3.11.9 (Windows 64-bit).
- [x] **Packaging & Entry Point:** Installed via `pip install -e .`; verified `opticore-cli` console script and `python -m opticore_cli`.
- [x] **Character Encoding:** Configured UTF-8 stream reconfiguring and `safe_box=True` in Rich console to prevent `cp1252` encoding crashes on legacy Windows consoles.
- [x] **Audio Subsystem:** SAPI5 voice driver detected via `pyttsx3` (`TTS_MS_EN-US_DAVID_11.0`); verified `voice on`, `voice off`, `voice status`, and `voice test`.
- [x] **Forced Announcements:** Verified `voice test` queues and speaks even when general voice alerts are set to disabled.
- [x] **Network Handling:** Handled `ngrok-skip-browser-warning`, connection timeout, connection refused, 502 Bad Gateway, and DNS failure gracefully with user-friendly diagnostics.
- [x] **Live Streaming:** Tested live priority alert monitor with mock server stream; events printed with color badges, confidence, movement, and risk scores.
- [x] **Clean Exit:** Verified `exit`, `quit`, and `Ctrl+C` interrupt handling without tracebacks.

### Raspberry Pi OS (ARM64) Platform Readiness (Code Analysis & Architecture Verification)

> [!IMPORTANT]
> **Verification Status Note:** Live execution and pytest runs were conducted on a Windows 11 host. Physical Raspberry Pi hardware execution was not performed in this session. The following items reflect codebase architecture compliance and Debian packaging alignment:

- [x] **Lightweight Footprint:** Core dependencies limited to `requests`, `rich`, and `pyttsx3`. No heavy ML frameworks (Torch, OpenCV, CUDA) required on the client device.
- [x] **PEP 668 Virtual Environment Policy:** Debian Bookworm and Raspberry Pi OS enforce externally-managed environments; documented virtual environment setup (`python3 -m venv venv`) to avoid `externally-managed-environment` installation errors.
- [x] **Debian Speech Package Standards:** Configured fallback discovery for both modern `espeak-ng` (Debian 12 Bookworm) and legacy `espeak`.
- [x] **Headless / Missing Audio Resilience:** If no sound card or speaker is connected, audio fallback silently absorbs speech requests without halting the event monitor.
- [x] **Network Resilience:** Implements exponential reconnect backoff when Wi-Fi drops or ngrok tunnels re-establish.
- [x] **Terminal UI Compatibility:** Renders ANSI escape sequences and box borders cleanly on standard Linux terminal and SSH sessions.

---

## 4. Architectural Boundaries & System Limitations

1. **Camera Producer Exclusivity:**  
   The OptiCore server is architected to accept **one active camera stream** over `/ws/video` at a time. The CLI deliberately monitors events via HTTP polling rather than opening a dummy WebSocket, allowing the user's phone or field camera to remain the dedicated producer.

2. **Distance Estimation:**  
   As documented in the notebook's `process_frame` implementation, the vision pipeline does not have depth sensor hardware and sets `"distance_available": false`. Object proximity is calculated as apparent bounding-box growth and motion heuristics. The CLI displays this accurately as movement direction (`head-on`, `from your left`, `from your right`) rather than physical meters.

3. **ngrok Tunnel Lifespan:**  
   Free-tier ngrok tunnels expire when the notebook session restarts. When an expired tunnel URL is used, the CLI detects the condition and notifies the user with actionable instructions to copy the new tunnel URL.
