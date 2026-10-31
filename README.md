# OptiCore CLI Command Center

A high-performance, cross-platform terminal interface for the **OptiCore Real-Time Assistive Vision System**.

Connect over the internet to your running OptiCore vision server (hosted on Kaggle, a GPU instance, or an edge server with ngrok) directly from a **Windows 10/11** computer or a **Raspberry Pi OS (ARM64)** device.

---

## Table of Contents

1. [Overview & Architecture](#overview--architecture)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
   - [Windows 10/11 Installation](#windows-1011-installation)
   - [Raspberry Pi OS (ARM64) / Debian Linux Installation](#raspberry-pi-os-arm64--debian-linux-installation)
4. [Connecting to the OptiCore Server](#connecting-to-the-opticore-server)
   - [Starting the Vision Server (Kaggle / Remote GPU)](#starting-the-vision-server-kaggle--remote-gpu)
   - [Obtaining Your Public ngrok URL](#obtaining-your-public-ngrok-url)
5. [Quick Start](#quick-start)
6. [Interactive Command Center Shell](#interactive-command-center-shell)
7. [Command Reference & Examples](#command-reference--examples)
8. [Live Detection Logs Stream](#live-detection-logs-stream)
9. [Voice Alert Subsystem](#voice-alert-subsystem)
   - [How Voice Works (Client vs Server)](#how-voice-works-client-vs-server)
   - [Voice Controls & Verbosity](#voice-controls--verbosity)
   - [Audio Reliability & Fallback](#audio-reliability--fallback)
10. [Configuration & Environment Variables](#configuration--environment-variables)
11. [Local Offline Testing & Mock Server](#local-offline-testing--mock-server)
12. [Troubleshooting & FAQs](#troubleshooting--faqs)
13. [Verification & Architecture Conformance](#verification--architecture-conformance)

---

## Overview & Architecture

The OptiCore system combines **YOLO object detection**, **ByteTrack multi-object tracking**, and **heuristic risk analysis** to provide assistive vision alerts for pedestrians, cyclists, and visually impaired individuals.

```
┌────────────────────────────────────────────────────────┐
│               OptiCore Vision Server                   │
│   (Kaggle / Remote GPU / Edge Server on port 8000)     │
│                                                        │
│  • YOLO Object Detection (best.pt)                     │
│  • ByteTrack Multi-Object Tracking                     │
│  • Risk Escalation Engine (P1 Critical to P4 Info)    │
│  • Fast REST API (/health, /status, /metrics, /events) │
│  • ngrok Public HTTPS Tunnel                           │
└──────────────────────────┬─────────────────────────────┘
                           │ Public Internet (HTTPS)
            ┌──────────────┴──────────────┐
            ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────────┐
│  Mobile Browser Client  │   │  OptiCore CLI Command Center│
│  (Camera Producer)      │   │  (Windows 10/11 / Pi OS)    │
│                         │   │                             │
│ • Streams camera video  │   │ • Real-time event monitor   │
│   over WebSocket        │   │ • Status & GPU metrics      │
│ • Browser-local speech  │   │ • Local Cross-Platform TTS  │
│   synthesis             │   │ • Deduplicated voice alerts │
└─────────────────────────┘   └─────────────────────────────┘
```

### Key Integration Principles
- **Separation of Concerns:** The CLI Command Center operates as an independent edge command station. It connects via the server's HTTP monitoring endpoints (`/health`, `/status`, `/metrics`, `/events`), allowing the camera feed to run unhindered.
- **Client-Side Speech Synthesis:** Voice alerts in the existing OptiCore server architecture are generated locally on client devices. The CLI implements its own cross-platform speech engine with intelligent deduplication, preventing repeated warnings and guaranteeing non-overlapping speech.
- **Zero Hallucinated Fields:** All displayed metrics and events correspond 1:1 with the server's actual schemas: `timestamp`, `track_id`, `name`, `confidence`, `class_priority`, `position`, `approaching`, `approach_direction`, `priority`, and `risk_score`.

---

## Prerequisites

- **Python:** Python 3.8 or newer (Python 3.10+ recommended).
- **Network:** Internet access to reach the server's public ngrok or IP URL.
- **Audio Device (Optional):** Speakers or headphones for voice alerts. If no audio device is present (e.g. headless Raspberry Pi), the CLI operates in silent logging mode without crashing.

---

## Installation

### Windows 10/11 Installation

Open **PowerShell** or **Windows Terminal**:

```powershell
# 1. Clone the repository from GitHub
git clone https://github.com/Dharshankumar988/Opticore.git
cd Opticore

# 2. (Recommended) Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install the OptiCore CLI in editable mode
pip install -e .
```

*Note:* If PowerShell restricts script execution, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Raspberry Pi OS (ARM64) / Debian Linux Installation

Open a terminal on your Raspberry Pi:

```bash
# 1. Update system packages and install speech synthesizer and video packages
# (Note: on Raspberry Pi OS Bookworm / Debian 12, espeak-ng is the modern standard package)
sudo apt update && sudo apt install -y git python3-pip python3-venv espeak-ng libespeak-ng1 libgl1 libglib2.0-0

# 2. Clone the repository from GitHub
git clone https://github.com/Dharshankumar988/Opticore.git
cd Opticore

# 3. Create and activate a virtual environment
# (Required by Raspberry Pi OS / PEP 668 externally-managed environment policy)
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies and CLI package in editable mode
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

---

## Connecting to the OptiCore Server

### Starting the Vision Server (Kaggle / Remote GPU)

1. Open your OptiCore notebook (`opticore-server.ipynb`) in Kaggle or your GPU server.
2. Ensure `NGROK_AUTHTOKEN` is set in your Kaggle Secrets or environment.
3. Run Cells 1 through 5 in sequential order.
4. Cell 5 will initialize Uvicorn and display:
   ```
   =======================================================
   OPTICORE SERVER STATUS
   =======================================================
   Local API: http://127.0.0.1:8000
   Public URL: https://d492-34-125-18-200.ngrok-free.app
   Browser UI: https://d492-34-125-18-200.ngrok-free.app/
   Health: 200
   ```

### Obtaining Your Public ngrok URL

Copy the `Public URL` printed in Cell 5 (e.g. `https://d492-34-125-18-200.ngrok-free.app`).  
Keep the Kaggle/Colab notebook running while using the CLI Command Center.

---

## Streaming the Camera to the Server

The OptiCore server receives camera frames over WebSocket at `/ws/video`. You can stream video from your remote system using either of two methods:

### Method A: Built-in Browser Camera (Easiest — Phone, Tablet, Laptop)
1. On your remote system or phone, open **Chrome**, **Safari**, or **Edge**.
2. Navigate to your server's root URL:
   ```
   https://<your-ngrok-url>.ngrok-free.app/
   ```
3. Select **Rear camera** or **Front camera**.
4. Click **Start camera** and allow camera permissions.
5. The browser will begin streaming camera frames to the server in real-time!

### Method B: Headless Python Streamer (`stream_camera.py` — Raspberry Pi / USB Webcam)
If your remote system is a Raspberry Pi or you want to stream from a USB webcam / Pi Camera directly from the terminal without opening a browser:
```bash
# Install OpenCV and WebSockets if not already present:
pip install opencv-python websockets

# Stream from default webcam (index 0) to server:
python stream_camera.py --server https://<your-ngrok-url>.ngrok-free.app --camera 0

# Optional flags:
# --camera 1        Use external USB webcam index 1
# --fps 15          Target frame rate (default: 15)
# --show            Display local GUI preview window with server annotations
```

---

## Quick Start

Launch the interactive Command Center:

```bash
opticore-cli
```

### Interactive Arrow-Key Toggle Menu (Default Mode)

Launching `opticore-cli` opens the interactive toggle menu:

```
  Server: [Connected: https://xxxx.ngrok-free.app (38.2 ms)] | Camera Stream: [ON (STREAMING)] · Device 0 (15 FPS) | Voice: ON (PRIORITY)

  Use ↑/↓ arrows to navigate | [Enter] to select | [Space] to toggle | [q] to exit

  ╭────────────────────────────────────────────────────────────────────────────────────────────────────────╮
  │   1.  Connect to Server                 Configure or test OptiCore server URL (ngrok / IP)             │
  │ ▶ 2.  Camera Stream: [ ON ]             Turn camera stream ON or OFF directly from CLI [TOGGLE]        │
  │   3.  Camera Device: < Device 0 >       Detect connected cameras, show resolutions, and select device  │
  │   4.  Camera Preview Window: [ OFF ]    Toggle local GUI window with server detections [TOGGLE]        │
  │   5.  Stream Camera (Separate Window)   Streams camera in a dedicated popup window     [POPUP]         │
  │   6.  Launch Alert Logs (New Window)    Spawns dedicated shell window for live detection alerts [POPUP]│
  │   7.  Stream Alert Logs in Terminal     Runs detection alert stream in this terminal   [IN-PLACE]      │
  │   8.  Voice Alerts: [ ON ]              Toggle local text-to-speech alerts on or off   [TOGGLE]        │
  │   9.  Voice Verbosity: < PRIORITY >     Cycle: PRIORITY (P1/P2) -> CRITICAL (P1) -> ALL [TOGGLE]      │
  │  10.  Test Voice Output                 Play test speech announcement through speakers                 │
  │  11.  Server Status & GPU               Inspect GPU model, compute device, uptime, and active camera   │
  │  12.  Server Health Check               Check inference latency, model readiness, and stream rate      │
  │  13.  View Recent Priority Alerts       Display table of recent detection alerts from /events          │
  │  14.  Performance Metrics               View processed frames, avg latency, and FPS EMA                │
  │  15.  Configuration Settings            View or update persistent CLI settings                         │
  │  16.  Switch to Command Prompt          Drop into classic interactive prompt (opticore> )              │
  │  17.  Exit Command Center               Safely exit OptiCore CLI Command Center                        │
  ╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

- **Direct Camera Toggle:** Press `Space` or `Enter` on row 2 (**Camera Stream**) to immediately start or stop camera streaming directly from the CLI to your server URL. No browser needed!
- **Detect & Switch Cameras:** Select row 3 (**Camera Device**) to view all connected cameras, their hardware resolutions, and switch between them.
- **Toggle Preview Window:** Press `Space` or `Enter` on row 4 to toggle the local OpenCV preview window `[ ON ]` / `[ OFF ]`.
- **Toggle Voice Alerts:** Press `Space` or `Enter` on row 8 to immediately toggle Voice alerts `[ ON ]` / `[ OFF ]`.
- **Dedicated Log Stream Window:** Selecting row 6 ("Launch Alert Logs in New Window") spawns a dedicated shell window for streaming detection alerts in parallel.

---

## Command Reference & Examples

The OptiCore CLI can be controlled through **three modes**:
1. **Interactive Toggle Menu:** `opticore-cli` or `opticore-cli menu` (arrow keys + Space/Enter).
2. **Interactive Prompt:** `opticore-cli interactive` (the `opticore>` REPL prompt).
3. **Direct Subcommands:** Run single tasks directly from PowerShell, Bash, or automation scripts.

> *Tip:* If you installed via `pip install -e .`, run `opticore-cli`. You can also universally run `python -m opticore_cli`.

---

### Master Command Reference Table

| Interactive Command | Direct Terminal Subcommand | Menu Shortcut | Description |
| :--- | :--- | :--- | :--- |
| `menu` | `opticore-cli menu` | — | Open the interactive arrow-key toggle menu |
| `connect <url>` | `opticore-cli connect [url]` | Item 1 | Test connectivity, verify model, and save server URL |
| `disconnect` | — | — | Disconnect from current server session |
| `health` | `opticore-cli health` | Item 12 | View server health, model status, device, and rolling FPS |
| `status` | `opticore-cli status` | Item 11 | View server status, GPU model, active camera, and uptime |
| `metrics` | `opticore-cli metrics` | Item 14 | View inference latency, pipeline speed, and frame counters |
| `events [--limit N]` | `opticore-cli events [-n N]` | Item 13 | Retrieve latest `N` detection alerts from `/events` (1–100) |
| `camera on` | `opticore-cli camera on` | Item 2 | Start streaming local camera directly to server in background |
| `camera off` | `opticore-cli camera off` | Item 2 | Stop background camera streaming |
| `camera toggle` | `opticore-cli camera toggle` | Item 2 | Toggle camera stream ON / OFF |
| `camera list` | `opticore-cli camera list` | Item 3 | Scan and display all connected video capture hardware |
| `camera status` | `opticore-cli camera status` | Header | View current streaming status, device, FPS, and frames sent |
| `stream` | `opticore-cli stream [flags]` | Item 5 | Foreground camera streaming (`-w` opens in separate window) |
| `monitor` | `opticore-cli monitor [flags]` | Item 6 / 7 | Stream live detection alerts (`-w` opens in new window) |
| `voice on` / `off` | `opticore-cli voice [on\|off]` | Item 8 | Enable or disable local client-side voice alerts |
| `voice status` | `opticore-cli voice status` | — | Display TTS engine, rate, volume, queue depth, and hardware |
| `voice test` | `opticore-cli voice test` | Item 10 | Play a test speech announcement through your speakers |
| `voice verbosity <V>`| `opticore-cli --verbosity <V> monitor` | Item 9 | Set alert filter: `all`, `priority` (P1/P2), or `critical` (P1) |
| `voice rate <WPM>` | — | Settings | Adjust speech rate (100–350 words per minute, default: 180) |
| `voice volume <VOL>`| — | Settings | Adjust volume (`0.0` to `1.0` or percentage `0-100`) |
| `voice cooldown <S>` | — | Settings | Set message deduplication suppression window in seconds |
| `config show` | `opticore-cli config show` | Item 15 | Display all active configuration settings and paths |
| `config set <k> <v>`| — | Settings | Update a persistent setting (e.g. `config set poll_interval 0.5`) |
| `config reset` | `opticore-cli config reset` | — | Reset all configuration settings to factory defaults |
| `clear` / `cls` | — | — | Clear terminal screen and redraw header banner |
| `help` | — | — | Render full colorized command reference card |
| `exit` / `quit` / `q` | — | Item 17 | Safely stop workers and exit the Command Center |

---

### Global Flags

These flags can be prepended or passed to any direct subcommand:

```bash
opticore-cli [GLOBAL_FLAGS] <SUBCOMMAND> [SUBCOMMAND_FLAGS]
```

- `--url <URL>`: Override the OptiCore server address (ngrok public URL or IP).
- `--voice`: Enable local voice announcements during execution.
- `--verbosity <all|priority|critical>`: Set voice alert filtering level.
- `--timeout <SECONDS>`: Set HTTP request timeout in seconds (default: `6.0`).

---

### Direct Terminal Subcommands & Flags

#### 1. Server Connection & Health Inspection
```bash
# Test connection to an ngrok or IP server and save it to config:
opticore-cli connect https://your-tunnel.ngrok-free.app

# Check server health, active YOLO model, and compute device:
opticore-cli health

# Check GPU hardware, server uptime, and camera status:
opticore-cli status

# View pipeline throughput and average inference latency:
opticore-cli metrics

# Fetch the last 25 detection alert events:
opticore-cli events --limit 25
```

#### 2. Camera Streaming Directly to Server
```bash
# Turn camera stream ON in the background (streams directly to server URL):
opticore-cli camera on

# Turn camera stream OFF:
opticore-cli camera off

# Toggle camera stream ON / OFF:
opticore-cli camera toggle

# Detect all connected hardware cameras (Device 0, Device 1, USB webcams):
opticore-cli camera list

# Check camera streaming status, FPS, and frames sent:
opticore-cli camera status

# Run live foreground camera streaming:
opticore-cli stream --camera 0 --fps 15 --width 640 --quality 75

# Run camera streamer in a dedicated new shell window:
opticore-cli stream --new-window

# Stream camera with local OpenCV GUI preview window:
opticore-cli stream --show
```

#### 3. Live Detection Alert Monitoring
```bash
# Stream live priority alerts in the current terminal:
opticore-cli monitor

# Stream alerts with custom polling frequency (every 0.5 seconds):
opticore-cli monitor --poll 0.5

# Launch alert stream in a dedicated popup shell window:
opticore-cli monitor --new-window

# Stream alerts with live text-to-speech enabled:
opticore-cli monitor --voice --verbosity priority
```

#### 4. Voice Alert Management
```bash
# Enable or disable client-side voice alerts:
opticore-cli voice on
opticore-cli voice off

# Inspect TTS audio backend, volume, and deduplication queue:
opticore-cli voice status

# Play a test speech announcement:
opticore-cli voice test
```

#### 5. Configuration & Offline Testing
```bash
# View all persistent configuration settings:
opticore-cli config show

# Reset configuration to defaults:
opticore-cli config reset

# Launch offline mock server for testing without remote GPU:
opticore-cli mock-server --port 8000
```

---

### Interactive Prompt (`opticore>`) Detailed Usage

Start interactive mode with `opticore-cli interactive`:

```text
[https://distill-shrouded... | Voice:ON] opticore> help
```

#### Camera Commands
- `camera on` (or `camera start`): Connects to the server's `/ws/video` WebSocket and streams compressed camera frames in the background. No browser required.
- `camera off` (or `camera stop`): Cleanly releases the camera capture device and closes the WebSocket stream.
- `camera toggle`: Quick toggle between ON and OFF.
- `camera list` (or `camera devices`): Probes `/dev/video*` (Linux) or DirectShow (Windows) up to 5 devices, testing resolutions and listing hardware names.
- `camera status`: Displays whether the camera is streaming, which device is active, total frames sent, and current FPS.
- `stream [--show] [--new-window] [--camera <ID>]`: Runs camera streaming directly in the foreground or spawns a dedicated console window.

#### Live Event Monitoring Commands
- `monitor`: Starts streaming real-time alerts. Colorizes detections by risk level (`P1 CRITICAL` in red, `P2 WARNING` in orange, `P3 CAUTION` in yellow, `P4 INFO` in blue). Press `Ctrl+C` to return to prompt.
- `monitor -w` (or `monitor --new-window`): Spawns a dedicated PowerShell / Terminal window for monitoring while keeping your current shell active.
- `monitor --poll 0.5`: Polls every 500 ms for ultra-low latency alerts.

#### Voice Commands
- `voice on` / `voice off`: Enable or disable speech alerts.
- `voice verbosity <all|priority|critical>`:
  - `critical`: Speaks only urgent P1 alerts (e.g. approaching vehicles, direct potholes).
  - `priority`: Speaks P1 and P2 alerts (default for pedestrian navigation).
  - `all`: Speaks all recognized obstacle candidates.
- `voice rate <100-350>`: Sets speaking speed in words per minute (default: `180`).
- `voice volume <0.0-1.0>`: Adjusts audio volume (e.g. `voice volume 0.8` or `voice volume 80`).
- `voice cooldown <seconds>`: Minimum seconds before repeating an identical alert (default: `7.0`).
- `voice test`: Confirms speaker output by playing an announcement.

#### Configuration Commands
- `config show`: Displays a table of all persistent settings.
- `config set <key> <value>`: Updates and persists any configuration parameter:
  - `config set server_url https://xxxx.ngrok-free.app`
  - `config set camera_source 1`
  - `config set camera_fps 20`
  - `config set camera_show_preview true`
  - `config set voice_verbosity critical`
  - `config set poll_interval 0.5`
  - `config set timeout 8.0`
- `config reset`: Restores all parameters to factory defaults.

---

## Live Priority Alert Stream

> [!NOTE]
> **Priority Alerts vs Camera Stream:**  
> The CLI streams **priority detection alerts and warnings** from the server's `/events` endpoint. In the OptiCore architecture, raw frame-by-frame detections for every visible background object are handled in real-time over the dedicated camera WebSocket (`/ws/video`). Only safety-relevant detections and candidate objects (approaching vehicles, potholes, pedestrians, stairs, obstacles) are escalated to the alert queue. This preserves camera bandwidth and delivers focused, actionable safety alerts.

Running `monitor` (or `logs`) begins streaming events from the server in real-time:

```
opticore> monitor
```

Output:
```
--- LIVE PRIORITY ALERT STREAM STARTED ---
Connected to: https://d492-34-125-18-200.ngrok-free.app (Poll interval: 1.0s)
Voice alerts: ON (Verbosity: priority)
Streaming priority detection alerts from server /events (raw video frames are handled by camera producer).
Press Ctrl+C at any time to return to Command Center.

[12:15:32.410]  P1 CRITICAL  CAR        (#3) conf: 89.2% pos:ahead  [APPROACHING: head-on] risk:85 -> A car appears to be approaching head-on.
[12:15:34.120]  P1 CRITICAL  POTHOLE    (#7) conf: 81.0% pos:ahead  risk:81 -> Pothole detected ahead.
[12:15:35.890]  P2 WARNING   PERSON     (#9) conf: 76.5% pos:left   risk:62 -> Person detected on your left.
[12:15:38.200]  P3 CAUTION   STAIRS     (#12) conf: 74.0% pos:ahead risk:45 -> Stairs detected ahead.
```

### Log Line Details
- **Timestamp:** Precise local time of detection (`HH:MM:SS.mmm`).
- **Priority Badge:**
  - `P1 CRITICAL` (Red): Vehicles approaching rapidly, potholes directly in path.
  - `P2 WARNING` (Orange): People, motorcycles, bicycles in vicinity.
  - `P3 CAUTION` (Yellow): Stairs, doors, static sidewalk obstacles.
  - `P4 INFO` (Blue): Background objects, signs, trees, benches.
- **Class & Track:** Detected object name and persistent ByteTrack ID (`#3`).
- **Confidence:** YOLO detection certainty (`89.2%`).
- **Position & Movement:** Camera-relative position (`left`, `ahead`, `right`) and motion direction (`head-on`, `from your left`, etc.).
- **Risk Score:** Heuristic collision risk calculated by the OptiCore priority engine (0–100).
- **Alert Message:** Plain-English alert description generated by the server.

*To return to the Command Center prompt, press `Ctrl+C`.*

---

## Voice Alert Subsystem

### How Voice Works (Client vs Server)

Inspection of the OptiCore notebook (`opticore-server.ipynb`) confirms that the server generates text alert structures (`"message"` field), but **does not run text-to-speech itself**. In the web interface, the client browser synthesizes voice using JavaScript's `window.speechSynthesis`.

The OptiCore CLI implements client-side voice alerts using a local cross-platform engine:
- **Windows:** Uses SAPI5 via `pyttsx3` with an automated fallback to Windows PowerShell `System.Speech`.
- **Raspberry Pi OS / Linux:** Uses `espeak` / `espeak-ng`.
- **macOS:** Uses `say`.

### Voice Controls & Verbosity

You can customize voice alerts on the fly:

```
opticore> voice on
opticore> voice verbosity critical
opticore> voice rate 190
opticore> voice volume 0.8
opticore> voice status
```

#### Verbosity Levels
- `all`: Speaks every candidate detection alert.
- `priority` *(default)*: Speaks high-priority events (`P1`, `P2`) and safety-critical classes (`car`, `bus`, `truck`, `pothole`).
- `critical`: Speaks only urgent alerts (`P1` and critical approaching obstacles).

#### Intelligent Cooldown & Deduplication
To prevent speech fatigue and overlapping sound:
1. **Deduplication Cooldown:** Identical messages within `voice_cooldown` (default: 7.0 seconds, matching the browser client) are automatically suppressed.
2. **Non-Overlapping Worker Queue:** Announcements are spoken sequentially on a dedicated background thread. New alerts never cut off or garble ongoing speech.

### Audio Reliability & Fallback

If an audio output device is missing or unplugged:
- The CLI detects the absence safely.
- Audio synthesis silently falls back without interrupting visual log streaming or crashing the application.
- The `voice status` command clearly displays whether audio hardware is ready.

---

## Configuration & Environment Variables

Settings are saved in `~/.opticore/config.json` (or `./opticore.config.json` if present in the working directory).

### Precedence Hierarchy
`CLI Arguments` > `Environment Variables` > `Config File` > `Defaults`

### Environment Variables

| Variable | Description | Example |
| :--- | :--- | :--- |
| `OPTICORE_SERVER_URL` | Public ngrok or server address | `https://your-id.ngrok-free.app` |
| `OPTICORE_VOICE_ENABLED` | Enable voice alerts by default | `true` or `1` |
| `OPTICORE_VOICE_VERBOSITY` | Alert verbosity filter | `all`, `priority`, or `critical` |
| `OPTICORE_POLL_INTERVAL` | Polling frequency in seconds | `1.0` |
| `OPTICORE_TIMEOUT` | HTTP request timeout in seconds | `6.0` |
| `OPTICORE_VOICE_RATE` | Speech rate in words per minute | `180` |
| `OPTICORE_VOICE_VOLUME` | Speech volume (0.0 to 1.0) | `0.9` |

### Setting Config via CLI

```
opticore> config show
opticore> config set voice_verbosity critical
opticore> config set poll_interval 0.8
opticore> config reset
```

---

## Local Offline Testing & Mock Server

A built-in mock server replicates the OptiCore FastAPI backend. It allows testing and demonstrations without a GPU instance or active ngrok tunnel.

In a separate terminal, launch the mock server:
```bash
opticore-cli mock-server --port 8000
```

Then connect to it from the Command Center:
```
opticore> connect http://127.0.0.1:8000
opticore> monitor
```

---

## Troubleshooting & FAQs

### Q: "Connection timed out after 6.0s"
**A:** Ensure your Kaggle notebook or GPU server is currently executing Cell 5 and hasn't gone into sleep mode. Verify that your ngrok public URL matches the active session.

### Q: "Bad Gateway (502)"
**A:** The ngrok tunnel is alive, but the OptiCore FastAPI/Uvicorn process inside the notebook crashed or was restarted. Check Cell 5 logs in your notebook.

### Q: "Received ngrok interstitial page instead of API response"
**A:** The CLI automatically passes `ngrok-skip-browser-warning: 69420` to bypass ngrok's free-tier browser interstitial. If you see this error, ensure the ngrok URL was entered without syntax typos.

### Q: "No sound on Raspberry Pi"
**A:** Install the speech synthesizer packages:
```bash
sudo apt install -y espeak libespeak1
```
Ensure your audio output (3.5mm jack, HDMI, or USB DAC) is selected using `raspi-config`.

### Q: "How do I exit the CLI safely?"
**A:** In the interactive shell, type `exit` or `quit`. To stop the live monitor, press `Ctrl+C`.

---

## Verification & Architecture Conformance

The test suite validates compliance with the notebook's API specification:

```bash
python -m pytest -v
```

All 37 automated tests pass:
- **Configuration:** File loading, environment variable overrides, type coercion, and defaults.
- **API Client:** URL normalization, health verification, status retrieval, metrics, and error diagnostics.
- **Models:** Strict adherence to notebook schemas (P1–P4 priorities, track IDs, approach heuristics).
- **Camera Streamer:** WebSocket frame streaming, URL normalization, hardware device discovery, and thread lifecycle.
- **Interactive Menu:** Key handling, dynamic badges, toggles, window spawning, and device switcher.
- **Voice Engine:** Non-overlapping queueing, verbosity filters, and 7.0-second cooldown deduplication.
- **Live Monitor:** Continuous event polling, event key deduplication, and automatic reconnect backoff.
- **CLI Shell:** Interactive command dispatch, argument parsing, and banner rendering.

---

*OptiCore Assistive Vision Project · Designed for Edge Devices & Assistive Mobility*
