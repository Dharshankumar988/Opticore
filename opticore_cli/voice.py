"""Voice alert engine for OptiCore CLI Command Center.

Provides cross-platform, non-blocking text-to-speech alerts with deduplication,
verbosity filtering, and safe fallbacks for headless or missing audio environments.
"""

import logging
import platform
import queue
import subprocess
import threading
import time
from typing import Optional

from opticore_cli.models import DetectionEvent

logger = logging.getLogger("opticore.voice")


class VoiceAlertEngine:
    """Manages text-to-speech alerts on Windows, macOS, and Linux/Raspberry Pi OS."""

    def __init__(
        self,
        enabled: bool = False,
        verbosity: str = "priority",  # "all", "priority", "critical"
        rate: int = 195,
        volume: float = 1.0,
        cooldown: float = 3.0,
    ):
        self.enabled = enabled
        self.verbosity = verbosity.lower()
        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))
        self.cooldown = cooldown

        self._queue: queue.Queue = queue.Queue(maxsize=30)
        self._spoken_keys: dict = {}
        self._last_spoken_message = ""
        self._last_spoken_time = 0.0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._engine_available = False
        self._backend = "none"

        self._init_tts_engine()
        self._start_worker()

    def _init_tts_engine(self) -> None:
        """Initializes the best available TTS backend."""
        system = platform.system().lower()
        if system == "windows":
            try:
                import win32com.client
                import pythoncom
                pythoncom.CoInitialize()
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                del speaker
                self._backend = "sapi_native"
                self._engine_available = True
                return
            except Exception as e:
                logger.debug("win32com SAPI init failed: %s", e)

            self._backend = "powershell_sapi"
            self._engine_available = True
            return

        if system == "linux":
            import shutil
            # On Linux / Raspberry Pi, prefer native espeak-ng or espeak CLI
            # This routes directly through PipeWire / PulseAudio into Bluetooth sinks
            for b in ["espeak-ng", "espeak"]:
                if shutil.which(b) or os.path.exists(f"/usr/bin/{b}") or os.path.exists(f"/bin/{b}"):
                    self._backend = b
                    self._engine_available = True
                    return
                try:
                    res = subprocess.run(
                        [b, "--version"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    if res.returncode == 0:
                        self._backend = b
                        self._engine_available = True
                        return
                except Exception:
                    pass

        try:
            import pyttsx3

            # Test initialization in a safe block
            test_engine = pyttsx3.init()
            self._backend = "pyttsx3"
            self._engine_available = True
            del test_engine
            return
        except Exception as e:
            logger.debug("pyttsx3 unavailable: %s", e)

        if system == "darwin":
            self._backend = "say"
            self._engine_available = True
        else:
            self._backend = "silent"
            self._engine_available = False

    def _start_worker(self) -> None:
        """Starts the dedicated background speech worker thread."""
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="opticore-voice-worker",
            daemon=True,
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        """Sequential speech worker loop to guarantee speech does not overlap."""
        if platform.system().lower() == "windows":
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

        speaker = None
        if platform.system().lower() == "windows":
            try:
                import win32com.client
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                sapi_rate = max(-10, min(10, int((self.rate - 180) / 15)))
                speaker.Rate = sapi_rate
                speaker.Volume = int(self.volume * 100)
            except Exception as e:
                logger.debug("win32com SAPI init failed: %s", e)

        tts_instance = None
        if self._backend == "pyttsx3":
            try:
                import pyttsx3
                tts_instance = pyttsx3.init()
                tts_instance.setProperty("rate", self.rate)
                tts_instance.setProperty("volume", self.volume)
            except Exception as e:
                logger.warning("Failed to initialize pyttsx3 in worker thread: %s", e)
                tts_instance = None
                self._backend = "powershell_sapi" if platform.system().lower() == "windows" else "silent"

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if not item:
                self._queue.task_done()
                continue

            if isinstance(item, tuple):
                message, force = item
            else:
                message, force = str(item), False

            if not message or (not self.enabled and not force):
                self._queue.task_done()
                continue

            try:
                self._speak_message(message, tts_instance, speaker)
            except Exception as e:
                logger.debug("Speech synthesis error: %s", e)
            finally:
                self._queue.task_done()

        if tts_instance:
            try:
                tts_instance.stop()
            except Exception:
                pass

    def _speak_message(self, message: str, tts_instance: Optional[object], speaker: Optional[object] = None) -> None:
        """Speaks a message sequentially using the active backend."""
        if not self._engine_available:
            return

        clean_message = message.strip()
        if not clean_message:
            return

        # Windows native SAPI (sequential, synchronous, zero-overlap)
        if speaker is not None:
            try:
                # Flag 0 = SVSFDefault (synchronous blocking speak so phrases never overlap)
                speaker.Speak(clean_message, 0)
                return
            except Exception as e:
                logger.debug("win32com SAPI speak failed: %s. Falling back to PowerShell.", e)

        if platform.system().lower() == "windows":
            try:
                escaped = clean_message.replace("'", "''")
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{escaped}')",
                ]
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=10,
                )
                return
            except Exception as e:
                logger.debug("PowerShell SAPI failed: %s", e)

        if self._backend == "pyttsx3" and tts_instance is not None:
            try:
                tts_instance.setProperty("rate", self.rate)
                tts_instance.setProperty("volume", self.volume)
                tts_instance.say(clean_message)
                tts_instance.runAndWait()
                return
            except Exception as e:
                logger.debug("pyttsx3 failed during speech: %s.", e)

        # Fallback 2: espeak / espeak-ng (Raspberry Pi OS / Linux)
        elif self._backend in {"espeak", "espeak-ng"}:
            try:
                import sys
                sys.stdout.write(f"\n[VOICE ALERT] {clean_message}\n")
                sys.stdout.flush()

                # Ensure XDG_RUNTIME_DIR is set so PipeWire / PulseAudio routes to Bluetooth sink
                sub_env = dict(os.environ)
                if "XDG_RUNTIME_DIR" not in sub_env and hasattr(os, "getuid"):
                    user_run = f"/run/user/{os.getuid()}"
                    if os.path.exists(user_run):
                        sub_env["XDG_RUNTIME_DIR"] = user_run

                subprocess.run(
                    [self._backend, "-s", str(self.rate), "-a", "130", clean_message],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    env=sub_env,
                    check=False,
                    timeout=10,
                )
                return
            except Exception as e:
                logger.warning("%s failed: %s", self._backend, e)

        # Fallback 3: say (macOS)
        elif self._backend == "say":
            try:
                subprocess.run(
                    ["say", "-r", str(self.rate), clean_message],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=10,
                )
                return
            except Exception as e:
                logger.debug("say failed: %s", e)

    def should_announce(self, event: DetectionEvent) -> bool:
        """Determines if an event should be spoken based on verbosity setting."""
        if not self.enabled:
            return False

        if not event.message:
            return False

        v = self.verbosity
        if v == "all":
            return True

        # Matches server CLASS_PRIORITY rankings (P1 / P2 classes)
        priority_classes = {
            "car", "bus", "truck", "motorcycle", "bicycle",
            "pothole", "crack", "manhole", "animal", "person"
        }
        is_priority_class = event.name in priority_classes
        is_high_priority = event.priority in {"P1", "P2"}

        if v == "priority":
            return is_high_priority or is_priority_class

        if v == "critical":
            return event.priority == "P1" or event.name in {"car", "bus", "truck", "motorcycle"}

        return False

    def enqueue_event(self, event: DetectionEvent) -> bool:
        """Enqueues an event announcement if eligible and not on cooldown."""
        if not self.should_announce(event):
            return False

        message = event.message
        if not message:
            return False

        now = time.time()
        # Per-object and position key (matches OptiCore vision server repeat logic)
        track_str = str(event.track_id) if event.track_id is not None else "any"
        pos_str = str(event.position or "ahead")
        dir_str = str(event.approach_direction or ("approaching" if event.approaching else "stationary"))
        key = f"{track_str}|{event.name.lower()}|{pos_str}|{dir_str}"

        # Delay requirements:
        # - person, door, stairs: exactly 4.0s delay for repeated detections
        # - approaching vehicles/entities: 2.0s
        # - other static items/obstacles: 7.0-8.0s so it does not keep repeating
        norm_name = event.name.lower()
        if norm_name in {"person", "door", "stairs"}:
            effective_cooldown = 4.0
        elif event.approaching or event.priority == "P1":
            effective_cooldown = 2.0
        elif norm_name in {"car", "truck", "bus", "motorcycle", "bicycle", "animal"}:
            effective_cooldown = 3.0
        else:
            effective_cooldown = max(7.0, self.cooldown)

        with self._lock:
            last_time = self._spoken_keys.get(key, 0.0)
            if (now - last_time) < effective_cooldown:
                return False

            self._spoken_keys[key] = now
            if len(self._spoken_keys) > 200:
                cutoff = now - 30.0
                self._spoken_keys = {k: t for k, t in self._spoken_keys.items() if t > cutoff}

            self._last_spoken_message = message
            self._last_spoken_time = now

            # Clean backlog so queue never exceeds 1 item waiting (prevents speech overlap / delays)
            while self._queue.qsize() > 1:
                try:
                    self._queue.get_nowait()
                except Exception:
                    break

        try:
            self._queue.put_nowait((message, False))
            return True
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((message, False))
                return True
            except (queue.Empty, queue.Full):
                return False

    def speak_text(self, text: str, force: bool = False) -> bool:
        """Speaks arbitrary text (e.g. for testing or status confirmations)."""
        if not self.enabled and not force:
            return False

        try:
            self._queue.put_nowait((text, force))
            return True
        except queue.Full:
            return False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.clear_queue()

    def set_verbosity(self, verbosity: str) -> bool:
        clean = verbosity.strip().lower()
        if clean in {"all", "priority", "critical"}:
            self.verbosity = clean
            return True
        return False

    def set_rate(self, rate: int) -> None:
        self.rate = max(100, min(350, int(rate)))

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))

    def set_cooldown(self, cooldown: float) -> None:
        self.cooldown = max(1.0, float(cooldown))

    def clear_queue(self) -> None:
        with self._queue.mutex:
            self._queue.queue.clear()

    @property
    def backend_name(self) -> str:
        return self._backend

    @property
    def is_available(self) -> bool:
        return self._engine_available

    def get_status_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "verbosity": self.verbosity,
            "backend": self._backend,
            "available": self._engine_available,
            "rate": self.rate,
            "volume": self.volume,
            "cooldown": self.cooldown,
            "pending_in_queue": self._queue.qsize(),
        }

    def shutdown(self) -> None:
        self._stop_event.set()
        self.clear_queue()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
