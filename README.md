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
# 1. Update system packages and install speech synthesizer packages
# (Note: on Raspberry Pi OS Bookworm / Debian 12, espeak-ng is the modern standard package)
sudo apt update && sudo apt install -y git python3-pip python3-venv espeak-ng libespeak-ng1

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
Keep the Kaggle notebook running while using the CLI Command Center.

---

## Quick Start

Launch the interactive Command Center:

```bash
opticore-cli
```

### Interactive Arrow-Key Toggle Menu (Default Mode)

Launching `opticore-cli` opens the interactive toggle menu:

```
  Status: [Connected: https://xxxx.ngrok-free.app (38.2 ms) | Voice: ON (Priority)]

  Use ↑/↓ arrows to navigate | [Enter] to select | [Space] to toggle | [q] to exit

  ╭─────────────────────────────────────────────────────────────────────────────────────────────╮
  │   1.  Connect to Server              Configure or test OptiCore server URL                  │
  │ ▶ 2.  Launch Live Stream (New Window) Spawns dedicated shell window for live alerts  [POPUP] │
  │   3.  Voice Alerts: [ ON ]           Toggle local text-to-speech alerts on or off  [TOGGLE] │
  │   4.  Voice Verbosity: < PRIORITY >  Cycle: PRIORITY -> CRITICAL -> ALL            [TOGGLE] │
  │   5.  Test Voice Output              Play test speech announcement                          │
  │   6.  Server Status & GPU            View GPU hardware, device, and uptime                  │
  │   7.  Server Health Check            Inference latency, model readiness, and FPS            │
  │   8.  View Recent Priority Alerts    Display table of recent alerts from /events            │
  │   9.  Performance Metrics            Processed frames, avg latency, and FPS EMA             │
  │  10.  Configuration Settings         View and modify persistent CLI settings                │
  │  11.  Switch to Command Prompt       Drop into classic prompt mode (opticore> )             │
  │  12.  Exit Command Center            Safely exit OptiCore CLI Command Center                │
  ╰─────────────────────────────────────────────────────────────────────────────────────────────╯
```

- **Navigate:** Use `↑` and `↓` arrow keys.
- **Toggle Voice Alerts:** Press `Space` or `Enter` on row 3 to immediately toggle Voice alerts `[ ON ]` / `[ OFF ]`.
- **Toggle Verbosity:** Press `Space` or `Enter` on row 4 to cycle verbosity `< PRIORITY >` / `< CRITICAL >` / `< ALL >`.
- **Dedicated Log Stream Window:** Selecting row 2 ("Launch Live Stream in New Window") spawns a **brand-new shell window** dedicated to streaming detection alerts, keeping your main menu open in parallel!

---

## Command Reference & Examples

All commands can be run via the arrow menu, inside the interactive shell (`opticore-cli interactive`), or directly from the terminal.

| Interactive Command | Direct CLI Command | Description |
| :--- | :--- | :--- |
| `menu` | `opticore-cli menu` | Launch the interactive arrow-key toggle menu |
| `connect <url>` | `opticore-cli connect <url>` | Test connectivity, verify model, and save URL |
| `disconnect` | — | Disconnect from current server session |
| `status` | `opticore-cli status` | View full server status, GPU hardware, and camera stream state |
| `health` | `opticore-cli health` | View server health, model status, device, and FPS |
| `metrics` | `opticore-cli metrics` | View inference latency, pipeline speed, and frame counts |
| `events [N]` | `opticore-cli events --limit N` | Display the latest `N` detection alert events (1–100) |
| `monitor [-w]` | `opticore-cli monitor [-w]` | Stream live alerts (`-w` / `--new-window` opens in separate shell) |
| `voice [on\|off]` | `opticore-cli voice [on\|off]` | Enable or disable client-side voice alerts |
| `voice status` | `opticore-cli voice status` | Show TTS audio engine, rate, volume, and queue depth |
| `voice test` | `opticore-cli voice test` | Play a test speech announcement through your speakers |
| `voice verbosity <V>`| `opticore-cli --verbosity <V> monitor` | Set alert filtering: `all`, `priority`, or `critical` |
| `voice rate <WPM>` | — | Adjust speech speed (100–350 words per minute, default: 180) |
| `voice volume <VOL>`| — | Adjust volume (0.0 to 1.0 or 0–100%) |
| `config show` | `opticore-cli config show` | Display all persistent configuration values |
| `config set <k> <v>`| — | Update a configuration setting |
| `config reset` | `opticore-cli config reset` | Reset all configuration parameters to default values |
| `clear` / `cls` | — | Clear the terminal screen |
| `exit` / `quit` | — | Safely exit the Command Center |

### Examples

#### Check Server Health
```
opticore> health
```
Outputs a panel with inference device (`cuda:0`), tracker (`bytetrack.yaml`), input resolution (`640x640`), average inference latency (`31.2 ms`), and rolling FPS (`32.1 FPS`).

#### View Full Status & GPU Info
```
opticore> status
```
Outputs GPU name (e.g. `Tesla T4`), camera stream status (`Active` / `Idle`), server uptime, and deduplication policy.

#### Check Recent Events
```
opticore> events 10
```
Displays a table of the 10 most recent detection events with timestamp, priority badge, class, tracking ID, position, movement, risk score, and alert message.

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

All 27 automated tests pass:
- **Configuration:** File loading, environment variable overrides, type coercion, and defaults.
- **API Client:** URL normalization, health verification, status retrieval, metrics, and error diagnostics.
- **Models:** Strict adherence to notebook schemas (P1–P4 priorities, track IDs, approach heuristics).
- **Voice Engine:** Non-overlapping queueing, verbosity filters, and 7.0-second cooldown deduplication.
- **Live Monitor:** Continuous event polling, event key deduplication, and automatic reconnect backoff.
- **CLI Shell:** Interactive command dispatch, argument parsing, and banner rendering.

---

*OptiCore Assistive Vision Project · Designed for Edge Devices & Assistive Mobility*
