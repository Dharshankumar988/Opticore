"""Interactive Arrow-Key Navigation Menu for OptiCore CLI Command Center."""

import os
import platform
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from opticore_cli.ui import (
    console,
    get_priority_styled,
    print_banner,
    render_events_table,
    render_health,
    render_metrics,
    render_status,
    render_voice_status,
)


def read_key() -> str:
    """Reads a single keypress cross-platform.
    Returns: 'up', 'down', 'left', 'right', 'enter', 'space', 'esc', 'quit', or key char.
    """
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            if ch2 == b"H":
                return "up"
            elif ch2 == b"P":
                return "down"
            elif ch2 == b"K":
                return "left"
            elif ch2 == b"M":
                return "right"
            return "other"
        elif ch in (b"\r", b"\n"):
            return "enter"
        elif ch == b" ":
            return "space"
        elif ch in (b"\x1b", b"q", b"Q"):
            return "quit"
        elif ch in (b"w", b"W", b"k", b"K"):
            return "up"
        elif ch in (b"s", b"S", b"j", b"J"):
            return "down"
        elif ch == b"\x03":  # Ctrl+C
            raise KeyboardInterrupt
        try:
            return ch.decode("utf-8", errors="ignore").lower()
        except Exception:
            return "other"
    else:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                # Collect remaining escape bytes with generous 200ms timeout for VMs / SSH / Kali
                seq = ch
                while True:
                    r, _, _ = select.select([sys.stdin], [], [], 0.20)
                    if not r:
                        break
                    next_ch = sys.stdin.read(1)
                    seq += next_ch
                    if len(seq) >= 2 and (next_ch.isalpha() or next_ch == "~"):
                        break
                    if len(seq) >= 8:
                        break

                # Handle ANSI, SS3 (Application Cursor Mode used in Kali / xfce), and extended codes
                if seq in ("\x1b[A", "\x1bOA", "\x1b[1;2A", "\x1b[1;5A") or (seq.startswith("\x1b") and seq.endswith("A")):
                    return "up"
                elif seq in ("\x1b[B", "\x1bOB", "\x1b[1;2B", "\x1b[1;5B") or (seq.startswith("\x1b") and seq.endswith("B")):
                    return "down"
                elif seq in ("\x1b[C", "\x1bOC", "\x1b[1;2C", "\x1b[1;5C") or (seq.startswith("\x1b") and seq.endswith("C")):
                    return "right"
                elif seq in ("\x1b[D", "\x1bOD", "\x1b[1;2D", "\x1b[1;5D") or (seq.startswith("\x1b") and seq.endswith("D")):
                    return "left"
                elif seq == "\x1b":
                    return "quit"
                return "other"
            elif ch in ("\r", "\n"):
                return "enter"
            elif ch == " ":
                return "space"
            elif ch in ("q", "Q"):
                return "quit"
            elif ch in ("w", "W", "k", "K"):
                return "up"
            elif ch in ("s", "S", "j", "J"):
                return "down"
            elif ch == "\x03":
                raise KeyboardInterrupt
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def launch_in_new_window(server_url: str = "", poll: float = 1.0, voice: bool = False, verbosity: str = "priority") -> Tuple[bool, str]:
    """Spawns a dedicated new shell window for streaming live detection alerts."""
    py_exe = sys.executable

    cmd_args = [py_exe, "-m", "opticore_cli", "monitor", "--poll", str(poll)]
    if server_url:
        cmd_args.extend(["--url", server_url])
    if voice:
        cmd_args.append("--voice")
    if verbosity:
        cmd_args.extend(["--verbosity", verbosity])

    system = platform.system().lower()

    if system == "windows":
        try:
            ps_cmd = f"& '{py_exe}' -m opticore_cli monitor --poll {poll}"
            if server_url:
                ps_cmd += f" --url '{server_url}'"
            if voice:
                ps_cmd += " --voice"
            if verbosity:
                ps_cmd += f" --verbosity {verbosity}"

            subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            return True, "Launched live detection stream in a new PowerShell window."
        except Exception as e:
            try:
                subprocess.Popen(cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                return True, "Launched live detection stream in a new console window."
            except Exception as e2:
                return False, f"Failed to spawn new window: {e2}"

    elif system == "linux":
        terminals = [
            ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
            ("lxterminal", ["lxterminal", "-e"]),
            ("gnome-terminal", ["gnome-terminal", "--"]),
            ("xfce4-terminal", ["xfce4-terminal", "-e"]),
            ("xterm", ["xterm", "-e"]),
        ]
        cmd_str = f"'{py_exe}' -m opticore_cli monitor --poll {poll}"
        if server_url:
            cmd_str += f" --url '{server_url}'"
        if voice:
            cmd_str += " --voice"
        if verbosity:
            cmd_str += f" --verbosity {verbosity}"

        for name, prefix in terminals:
            try:
                which = subprocess.run(["which", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if which.returncode == 0:
                    if name == "gnome-terminal":
                        subprocess.Popen(prefix + ["bash", "-c", f"{cmd_str}; exec bash"])
                    else:
                        subprocess.Popen(prefix + [f"bash -c \"{cmd_str}; exec bash\""])
                    return True, f"Launched live detection stream in a new {name} window."
            except Exception:
                continue

        return False, "No desktop terminal emulator found. Use 'monitor' to run in current shell."

    elif system == "darwin":
        try:
            cmd_str = f"'{py_exe}' -m opticore_cli monitor"
            osascript = f'tell application "Terminal" to do script "{cmd_str}"'
            subprocess.Popen(["osascript", "-e", osascript])
            return True, "Launched live detection stream in a new Terminal window."
        except Exception as e:
            return False, f"Failed to open Terminal window: {e}"

    return False, "Unsupported platform for automatic window spawning."


def launch_camera_in_new_window(
    server_url: str = "",
    camera_source: str = "0",
    fps: float = 15.0,
    width: int = 640,
    quality: int = 65,
    show_window: bool = False,
) -> Tuple[bool, str]:
    """Spawns a dedicated new shell window for streaming camera frames to /ws/video."""
    py_exe = sys.executable
    system = platform.system().lower()

    cmd_args = [
        py_exe, "-m", "opticore_cli.camera",
        "--server", server_url,
        "--camera", str(camera_source),
        "--fps", str(fps),
        "--width", str(width),
        "--quality", str(quality),
    ]
    if show_window:
        cmd_args.append("--show")

    if system == "windows":
        try:
            ps_cmd = f"& '{py_exe}' -m opticore_cli.camera --server '{server_url}' --camera '{camera_source}' --fps {fps} --width {width} --quality {quality}"
            if show_window:
                ps_cmd += " --show"

            subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            return True, "Launched camera stream in a new PowerShell window."
        except Exception as e:
            try:
                subprocess.Popen(cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                return True, "Launched camera stream in a new console window."
            except Exception as e2:
                return False, f"Failed to spawn camera window: {e2}"

    elif system == "linux":
        terminals = [
            ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
            ("lxterminal", ["lxterminal", "-e"]),
            ("gnome-terminal", ["gnome-terminal", "--"]),
            ("xfce4-terminal", ["xfce4-terminal", "-e"]),
            ("xterm", ["xterm", "-e"]),
        ]
        cmd_str = f"'{py_exe}' -m opticore_cli.camera --server '{server_url}' --camera '{camera_source}' --fps {fps} --width {width} --quality {quality}"
        if show_window:
            cmd_str += " --show"

        for name, prefix in terminals:
            try:
                which = subprocess.run(["which", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if which.returncode == 0:
                    if name == "gnome-terminal":
                        subprocess.Popen(prefix + ["bash", "-c", f"{cmd_str}; exec bash"])
                    else:
                        subprocess.Popen(prefix + [f"bash -c \"{cmd_str}; exec bash\""])
                    return True, f"Launched camera stream in a new {name} window."
            except Exception:
                continue

        return False, "No desktop terminal emulator found. Use in-place camera streaming."

    elif system == "darwin":
        try:
            cmd_str = f"'{py_exe}' -m opticore_cli.camera --server '{server_url}' --camera '{camera_source}'"
            osascript = f'tell application "Terminal" to do script "{cmd_str}"'
            subprocess.Popen(["osascript", "-e", osascript])
            return True, "Launched camera stream in a new Terminal window."
        except Exception as e:
            return False, f"Failed to open Terminal window: {e}"

    return False, "Unsupported platform for automatic window spawning."


class InteractiveMenu:
    """Renders and manages the arrow-key toggle menu."""

    def __init__(self, cli):
        self.cli = cli
        self.selected_index = 0
        self.running = True

    def get_menu_items(self) -> List[Dict]:
        """Constructs current menu state with dynamic badges and toggle statuses."""
        voice_on = self.cli.voice.enabled
        voice_badge = "[bold green]ON[/bold green]" if voice_on else "[bold red]OFF[/bold red]"
        verb = self.cli.voice.verbosity.upper()

        url = self.cli.client.base_url
        if url:
            short_url = url.replace("https://", "").replace("http://", "")
            if len(short_url) > 28:
                short_url = short_url[:25] + "..."
            conn_status = f"[green]{short_url}[/green]"
        else:
            conn_status = "[yellow]Not Configured[/yellow]"

        # Camera streaming status
        cam_active = self.cli.camera_manager.is_active
        cam_badge = "[bold green]ON (STREAMING)[/bold green]" if cam_active else "[bold red]OFF[/bold red]"
        cam_src = str(getattr(self.cli.config, "camera_source", "0"))
        cam_label = f"Device {cam_src}" if cam_src in ("0", "1") else f"Src: {cam_src[:14]}"
        cam_preview = getattr(self.cli.config, "camera_show_preview", False)
        is_linux = sys.platform.startswith("linux")
        has_display = True if not is_linux else bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if not has_display:
            preview_badge = "[dim]OFF (Headless / SSH)[/dim]"
        else:
            preview_badge = "[bold green]ON[/bold green]" if cam_preview else "[dim]OFF[/dim]"

        return [
            {
                "id": "connect",
                "label": "Connect to Server",
                "tag": conn_status,
                "desc": "Configure or test OptiCore server URL (ngrok / IP)",
                "action": "connect",
            },
            # --- Camera Controls (Direct ON/OFF from CLI) ---
            {
                "id": "camera_toggle",
                "label": f"Camera Stream: [ {cam_badge} ]",
                "tag": "[bold yellow]PRESS SPACE / ENTER[/bold yellow]",
                "desc": "Turn camera stream ON or OFF directly from CLI to server URL",
                "action": "toggle_camera_stream",
            },
            {
                "id": "camera_source_toggle",
                "label": f"Camera Device: < {cam_label} >",
                "tag": "[bold yellow]DETECT & CHOOSE[/bold yellow]",
                "desc": "Detect connected cameras, show resolutions, and select device",
                "action": "camera_source_toggle",
            },
            {
                "id": "camera_preview_toggle",
                "label": f"Camera Preview Window: [ {preview_badge} ]",
                "tag": "[bold yellow]SPACE / ENTER[/bold yellow]",
                "desc": "Toggle local OpenCV window showing server-annotated detections",
                "action": "camera_preview_toggle",
            },
            # --- Important Safety Alert Logs ---
            {
                "id": "monitor_new",
                "label": "Important Alert Logs (New Window)",
                "tag": "[bold cyan]LOGS POPUP[/bold cyan]",
                "desc": "Dedicated window showing ONLY important safety alerts (P1 Critical / P2 Warning)",
                "action": "monitor_new",
            },
            {
                "id": "monitor_here",
                "label": "Stream Alert Logs in This Terminal",
                "tag": "[dim]IN-PLACE[/dim]",
                "desc": "Stream important safety alerts here (Ctrl+C to return to menu)",
                "action": "monitor_here",
            },
            # --- Voice Controls ---
            {
                "id": "voice_toggle",
                "label": f"Voice Alerts: [ {voice_badge} ]",
                "tag": "[bold yellow]SPACE / ENTER[/bold yellow]",
                "desc": "Toggle local text-to-speech alerts on or off",
                "action": "toggle_voice",
            },
            {
                "id": "voice_verb",
                "label": f"Voice Verbosity: < {verb} >",
                "tag": "[bold yellow]SPACE / ENTER[/bold yellow]",
                "desc": "Cycle alert verbosity: PRIORITY (P1/P2/People) -> CRITICAL (P1) -> ALL",
                "action": "cycle_verbosity",
            },
            {
                "id": "voice_test",
                "label": "Test Voice Output",
                "tag": "[dim]AUDIO CHECK[/dim]",
                "desc": "Play a test speech announcement through local speakers",
                "action": "test_voice",
            },
            # --- Server Diagnostics & Settings ---
            {
                "id": "status",
                "label": "Server Status & GPU",
                "tag": "[dim]INFO[/dim]",
                "desc": "Inspect GPU model, compute device, uptime, and active camera",
                "action": "status",
            },
            {
                "id": "health",
                "label": "Server Health Check",
                "tag": "[dim]METRICS[/dim]",
                "desc": "Check inference latency, model readiness, classes, and stream rate",
                "action": "health",
            },
            {
                "id": "events",
                "label": "View Recent Priority Alerts",
                "tag": "[dim]TABLE[/dim]",
                "desc": "Display table of recent detection alerts from /events",
                "action": "events",
            },
            {
                "id": "config",
                "label": "Configuration Settings",
                "tag": "[dim]SETTINGS[/dim]",
                "desc": "View or update local CLI settings (timeout, camera, speech rate)",
                "action": "config",
            },
            {
                "id": "cli_prompt",
                "label": "Switch to Command Prompt",
                "tag": "[dim]opticore>[/dim]",
                "desc": "Drop into classic interactive command-line mode (type 'menu' to return)",
                "action": "cli_prompt",
            },
            {
                "id": "exit",
                "label": "Exit Command Center",
                "tag": "[red]QUIT[/red]",
                "desc": "Safely exit OptiCore CLI Command Center",
                "action": "exit",
            },
        ]

    def render_menu(self) -> None:
        """Renders the entire toggle menu cleanly to console."""
        os.system("cls" if os.name == "nt" else "clear")
        print_banner()

        items = self.get_menu_items()

        # Connection, Camera & Voice Summary Bar
        v_state = "[bold green]ON[/bold green]" if self.cli.voice.enabled else "[bold red]OFF[/bold red]"
        conn_str = f"[bold green]{self.cli.client.base_url}[/bold green]" if self.cli.client.is_configured() else "[bold yellow]Disconnected[/bold yellow]"
        cam_active = self.cli.camera_manager.is_active
        cam_src = getattr(self.cli.config, "camera_source", "0")
        cam_fps = getattr(self.cli.config, "camera_fps", 15.0)
        cam_state = "[bold green]ON (STREAMING)[/bold green]" if cam_active else "[bold red]OFF[/bold red]"
        cam_str = f"{cam_state} · Device {cam_src} ({cam_fps:.0f} FPS)"

        summary_panel = Panel(
            f" [bold white]Server:[/bold white] {conn_str}   |   [bold white]Camera Stream:[/bold white] {cam_str}   |   [bold white]Voice Alerts:[/bold white] {v_state} ({self.cli.voice.verbosity.upper()})",
            box=box.SIMPLE,
            style="cyan",
        )
        console.print(summary_panel)

        # Instructions Bar
        console.print("[dim]Use [bold white]↑/↓[/bold white] (or [bold white]W/S[/bold white]) to navigate | [bold white]Enter[/bold white] to select | [bold white]Space[/bold white] to toggle | [bold white]q[/bold white] to quit[/dim]\n")

        # Menu Table
        table = Table(box=box.ROUNDED, show_header=False, expand=True, padding=(0, 1))
        table.add_column("Cursor", width=3, justify="center")
        table.add_column("Number", width=4, justify="right", style="dim")
        table.add_column("Option", width=38)
        table.add_column("Status / Badge", width=22)
        table.add_column("Description", style="dim")

        for i, item in enumerate(items):
            is_selected = i == self.selected_index
            if is_selected:
                cursor = "[bold cyan]▶[/bold cyan]"
                num = f"[bold cyan]{i + 1}.[/bold cyan]"
                label = f"[bold white on blue] {item['label']} [/bold white on blue]"
                tag = item["tag"]
                desc = f"[bold white]{item['desc']}[/bold white]"
            else:
                cursor = " "
                num = f"{i + 1}."
                label = f"[white]{item['label']}[/white]"
                tag = item["tag"]
                desc = item["desc"]

            table.add_row(cursor, num, label, tag, desc)

        console.print(table)

    def pause_for_user(self) -> None:
        """Pauses execution until the user presses a key."""
        console.print("\n[dim]Press [bold white]Enter[/bold white] or [bold white]Space[/bold white] to return to menu...[/dim]")
        try:
            read_key()
        except Exception:
            pass

    def run(self) -> None:
        """Runs the interactive arrow-key menu loop."""
        self.running = True

        while self.running:
            self.render_menu()
            items = self.get_menu_items()

            try:
                key = read_key()
            except (KeyboardInterrupt, EOFError):
                break

            if key in ("up", "w", "k"):
                self.selected_index = (self.selected_index - 1) % len(items)
            elif key in ("down", "s", "j"):
                self.selected_index = (self.selected_index + 1) % len(items)
            elif key.isdigit() and 1 <= int(key) <= len(items):
                self.selected_index = int(key) - 1
            elif key in ("space", "enter"):
                current_item = items[self.selected_index]
                action = current_item["action"]

                if action == "toggle_camera_stream":
                    if not self.cli.client.is_configured():
                        os.system("cls" if os.name == "nt" else "clear")
                        console.print("[bold red]Cannot start camera: Server URL is not configured. Connect first![/bold red]")
                        self.pause_for_user()
                    else:
                        if self.cli.camera_manager.is_active:
                            self.cli.camera_manager.stop()
                        else:
                            with console.status("[cyan]Starting camera stream to server...[/cyan]"):
                                ok, msg = self.cli.camera_manager.start(self.cli.client.base_url)
                            if not ok:
                                os.system("cls" if os.name == "nt" else "clear")
                                console.print(f"[bold red]Failed to start camera stream:[/bold red] {msg}")
                                if "Another camera stream is active" in msg or "producer_busy" in msg:
                                    console.print("\n[yellow]Note: Another camera is already streaming to the server (e.g. in your browser).[/yellow]")
                                    console.print("[yellow]Please close the browser tab or click 'Stop camera' in the browser so the CLI can take over.[/yellow]")
                                self.pause_for_user()

                elif action == "toggle_voice":
                    new_val = not self.cli.voice.enabled
                    self.cli.voice.set_enabled(new_val)
                    self.cli.config.voice_enabled = new_val
                    self.cli.config_manager.save()
                    if new_val:
                        self.cli.voice.speak_text("Voice alerts enabled.", force=True)

                elif action == "cycle_verbosity":
                    levels = ["priority", "critical", "all"]
                    curr = self.cli.voice.verbosity
                    next_verb = levels[(levels.index(curr) + 1) % len(levels)] if curr in levels else "priority"
                    self.cli.voice.set_verbosity(next_verb)
                    self.cli.config.voice_verbosity = next_verb
                    self.cli.config_manager.save()

                elif action == "camera_source_toggle":
                    os.system("cls" if os.name == "nt" else "clear")
                    console.print(Panel("[bold cyan]Scanning for connected cameras on this system...[/bold cyan]", box=box.ROUNDED))

                    from opticore_cli.camera import detect_cameras
                    detected = detect_cameras(max_probe=5)

                    table = Table(
                        box=box.ROUNDED,
                        header_style="bold cyan",
                        title="[bold cyan]Available Video Input Devices[/bold cyan]",
                    )
                    table.add_column("No.", justify="right", style="bold white", width=5)
                    table.add_column("Device", style="cyan", width=12)
                    table.add_column("Description / Hardware Name", style="white", width=38)
                    table.add_column("Max Resolution", justify="center", style="yellow", width=16)
                    table.add_column("Status", justify="center", width=14)

                    curr_src = str(getattr(self.cli.config, "camera_source", "0"))
                    options_map = {}
                    opt_num = 1

                    if detected:
                        for cam in detected:
                            is_active = (cam["index"] == curr_src)
                            status_str = "[bold green][ACTIVE][/bold green]" if is_active else "[dim]Available[/dim]"
                            table.add_row(
                                f"{opt_num}.",
                                f"Device {cam['index']}",
                                cam["label"],
                                cam["resolution"],
                                status_str,
                            )
                            options_map[str(opt_num)] = cam["index"]
                            opt_num += 1
                    else:
                        table.add_row("-", "None", "No hardware cameras detected", "—", "[yellow]Offline[/yellow]")

                    # Add Custom option
                    is_custom = curr_src not in [c["index"] for c in detected] and curr_src != ""
                    custom_status = f"[bold green][ACTIVE: {curr_src}][/bold green]" if is_custom else "[dim]Custom[/dim]"
                    table.add_row(
                        f"{opt_num}.",
                        "Custom",
                        "Enter index, video file, or RTSP stream",
                        "—",
                        custom_status,
                    )
                    options_map[str(opt_num)] = "custom"

                    console.print(table)
                    console.print(f"\nCurrently active: [bold cyan]Device {curr_src}[/bold cyan]")
                    console.print(f"[dim]Select camera number (1-{opt_num}) or press Enter to keep current:[/dim]")

                    try:
                        choice = input("select camera> ").strip()
                        if choice in options_map:
                            selected_source = options_map[choice]
                            if selected_source == "custom":
                                console.print("\nEnter device index (e.g. 2, 3) or file/stream path (e.g. video.mp4, rtsp://...):")
                                custom_val = input("custom source> ").strip()
                                if custom_val:
                                    self.cli.config.camera_source = custom_val
                                    self.cli.config_manager.save()
                                    console.print(f"[bold green]✓ Saved custom camera source: {custom_val}[/bold green]")
                            else:
                                self.cli.config.camera_source = selected_source
                                self.cli.config_manager.save()
                                console.print(f"[bold green]✓ Switched active camera to Device {selected_source}[/bold green]")
                        elif choice == "":
                            console.print("[dim]Kept current camera selection.[/dim]")
                        else:
                            console.print(f"[yellow]Invalid selection '{choice}'. Kept current camera.[/yellow]")
                    except Exception:
                        pass
                    self.pause_for_user()

                elif action == "camera_preview_toggle":
                    is_linux = sys.platform.startswith("linux")
                    has_display = True if not is_linux else bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
                    if not has_display:
                        self.cli.config.camera_show_preview = False
                        self.cli.config_manager.save()
                        os.system("cls" if os.name == "nt" else "clear")
                        console.print(Panel(
                            "[yellow]No graphical display detected (DISPLAY is not set).[/yellow]\n\n"
                            "[white]When connected remotely via SSH without an X11/Wayland display server, "
                            "local GUI preview windows are disabled to prevent Qt crashes.\n"
                            "Frames and detections are streamed headlessly to the server.[/white]",
                            title="[bold cyan]Headless Mode Active[/bold cyan]",
                            box=box.ROUNDED,
                        ))
                        self.pause_for_user()
                    else:
                        new_preview = not getattr(self.cli.config, "camera_show_preview", False)
                        self.cli.config.camera_show_preview = new_preview
                        self.cli.config_manager.save()

                elif action == "camera_stream_new":
                    os.system("cls" if os.name == "nt" else "clear")
                    if not self.cli.client.is_configured():
                        console.print("[bold red]Cannot start camera stream: Server URL is not configured. Connect first![/bold red]")
                    else:
                        console.print("[bold cyan]Spawning dedicated camera streaming window...[/bold cyan]")
                        ok, msg = launch_camera_in_new_window(
                            server_url=self.cli.client.base_url,
                            camera_source=self.cli.config.camera_source,
                            fps=self.cli.config.camera_fps,
                            width=self.cli.config.camera_width,
                            quality=self.cli.config.camera_quality,
                            show_window=self.cli.config.camera_show_preview,
                        )
                        if ok:
                            console.print(f"[bold green]✓ {msg}[/bold green]")
                            console.print("[dim]The camera is now capturing and streaming frames to the server in that dedicated window.[/dim]")
                        else:
                            console.print(f"[bold yellow]! {msg}[/bold yellow]")
                    self.pause_for_user()

                elif action == "test_voice":
                    os.system("cls" if os.name == "nt" else "clear")
                    console.print("[cyan]Testing voice alert output...[/cyan]")
                    ok = self.cli.voice.speak_text("OptiCore voice engine test. Audio hardware ready.", force=True)
                    if ok:
                        console.print("[green]Voice test sent to speech queue.[/green]")
                    else:
                        console.print("[yellow]Voice output could not be queued. Check audio hardware.[/yellow]")
                    self.pause_for_user()

                elif action == "monitor_new":
                    os.system("cls" if os.name == "nt" else "clear")
                    if not self.cli.client.is_configured():
                        console.print("[bold red]Cannot start stream: Server URL is not configured. Connect first![/bold red]")
                    else:
                        console.print("[bold cyan]Spawning dedicated live detection stream window...[/bold cyan]")
                        ok, msg = launch_in_new_window(
                            server_url=self.cli.client.base_url,
                            poll=self.cli.config.poll_interval,
                            voice=self.cli.voice.enabled,
                            verbosity=self.cli.voice.verbosity,
                        )
                        if ok:
                            console.print(f"[bold green]✓ {msg}[/bold green]")
                            console.print("[dim]The live detection log stream is now running in that dedicated window.[/dim]")
                            console.print("[dim]You can continue using this Command Center menu in parallel.[/dim]")
                        else:
                            console.print(f"[bold yellow]! {msg}[/bold yellow]")
                    self.pause_for_user()

                elif action == "monitor_here":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_monitor([])
                    self.pause_for_user()

                elif action == "connect":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_connect([])
                    self.pause_for_user()

                elif action == "status":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_status()
                    self.pause_for_user()

                elif action == "health":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_health()
                    self.pause_for_user()

                elif action == "events":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_events(["20"])
                    self.pause_for_user()

                elif action == "metrics":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_metrics()
                    self.pause_for_user()

                elif action == "config":
                    os.system("cls" if os.name == "nt" else "clear")
                    self.cli.handle_config(["show"])
                    self.pause_for_user()

                elif action == "cli_prompt":
                    os.system("cls" if os.name == "nt" else "clear")
                    console.print("[bold cyan]Entering Command Prompt mode. Type 'menu' to return to toggle menu.[/bold cyan]\n")
                    self.cli.run_interactive()
                    if not self.cli.running:
                        self.running = False

                elif action == "exit":
                    self.running = False
                    break

            elif key == "quit":
                self.running = False
                break

            elif key.isdigit() and 1 <= int(key) <= len(items):
                self.selected_index = int(key) - 1

        self.cli.shutdown()
