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
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        ch3 = sys.stdin.read(1)
                        if ch3 == "A":
                            return "up"
                        elif ch3 == "B":
                            return "down"
                        elif ch3 == "C":
                            return "right"
                        elif ch3 == "D":
                            return "left"
                return "quit"
            elif ch in ("\r", "\n"):
                return "enter"
            elif ch == " ":
                return "space"
            elif ch in ("q", "Q"):
                return "quit"
            elif ch == "\x03":
                raise KeyboardInterrupt
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def launch_in_new_window(server_url: str = "", poll: float = 1.0, voice: bool = False, verbosity: str = "priority") -> Tuple[bool, str]:
    """Spawns a dedicated new shell window for streaming live detection alerts."""
    py_exe = sys.executable

    # Build command arguments
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
            # Launch in a new PowerShell window that stays open on completion
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
            # Fallback to direct python new console
            try:
                subprocess.Popen(cmd_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
                return True, "Launched live detection stream in a new console window."
            except Exception as e2:
                return False, f"Failed to spawn new window: {e2}"

    elif system == "linux":
        # Search for available terminal emulators
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

        return [
            {
                "id": "connect",
                "label": "Connect to Server",
                "tag": conn_status,
                "desc": "Configure or test OptiCore server URL (ngrok / IP)",
                "action": "connect",
            },
            {
                "id": "monitor_new",
                "label": "Launch Live Stream (New Window)",
                "tag": "[bold cyan]POPUP WINDOW[/bold cyan]",
                "desc": "Spawns a dedicated new shell window for streaming live detection alerts",
                "action": "monitor_new",
            },
            {
                "id": "monitor_here",
                "label": "Stream Logs in This Window",
                "tag": "[dim]IN-PLACE[/dim]",
                "desc": "Runs detection stream in this terminal (Press Ctrl+C to return to menu)",
                "action": "monitor_here",
            },
            {
                "id": "voice_toggle",
                "label": f"Voice Alerts: [ {voice_badge} ]",
                "tag": "[bold yellow]PRESS SPACE / ENTER[/bold yellow]",
                "desc": "Toggle local text-to-speech alerts on or off",
                "action": "toggle_voice",
            },
            {
                "id": "voice_verb",
                "label": f"Voice Verbosity: < {verb} >",
                "tag": "[bold yellow]PRESS SPACE / ENTER[/bold yellow]",
                "desc": "Cycle alert verbosity: PRIORITY (P1/P2) -> CRITICAL (P1 only) -> ALL",
                "action": "cycle_verbosity",
            },
            {
                "id": "voice_test",
                "label": "Test Voice Output",
                "tag": "[dim]AUDIO CHECK[/dim]",
                "desc": "Play a test speech announcement through local speakers",
                "action": "test_voice",
            },
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
                "id": "metrics",
                "label": "Performance Metrics",
                "tag": "[dim]COUNTERS[/dim]",
                "desc": "View processed frames, avg latency, FPS EMA, and rejected frames",
                "action": "metrics",
            },
            {
                "id": "config",
                "label": "Configuration Settings",
                "tag": "[dim]SETTINGS[/dim]",
                "desc": "View or update local CLI settings (timeout, speech rate, cooldown)",
                "action": "config",
            },
            {
                "id": "cli_prompt",
                "label": "Switch to Command Prompt",
                "tag": "[dim]opticore> [/dim]",
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

        # Connection & Voice Summary Bar
        v_state = "[bold green]ON[/bold green]" if self.cli.voice.enabled else "[bold red]OFF[/bold red]"
        conn_str = f"[bold green]{self.cli.client.base_url}[/bold green]" if self.cli.client.is_configured() else "[bold yellow]Disconnected[/bold yellow]"
        summary_panel = Panel(
            f" [bold white]Server:[/bold white] {conn_str}   |   [bold white]Voice Alerts:[/bold white] {v_state} ({self.cli.voice.verbosity.upper()})   |   [bold white]Audio Engine:[/bold white] {self.cli.voice.backend_name}",
            box=box.SIMPLE,
            style="cyan",
        )
        console.print(summary_panel)

        # Instructions Bar
        console.print("[dim]Use [bold white]↑/↓[/bold white] to navigate | [bold white]Enter[/bold white] to select | [bold white]Space[/bold white] to toggle | [bold white]q[/bold white] to quit[/dim]\n")

        # Menu Table
        table = Table(box=box.ROUNDED, show_header=False, expand=True, padding=(0, 1))
        table.add_column("Cursor", width=3, justify="center")
        table.add_column("Number", width=4, justify="right", style="dim")
        table.add_column("Option", width=36)
        table.add_column("Status / Badge", width=24)
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

            if key == "up":
                self.selected_index = (self.selected_index - 1) % len(items)
            elif key == "down":
                self.selected_index = (self.selected_index + 1) % len(items)
            elif key in ("space", "enter"):
                current_item = items[self.selected_index]
                action = current_item["action"]

                if action == "toggle_voice":
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
                    # When interactive finishes, check if still running
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
