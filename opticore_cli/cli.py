"""OptiCore CLI Command Center - Main Entry Point & Interactive Shell."""

import argparse
import os
import shlex
import sys
import time
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from opticore_cli.client import OptiCoreClient
from opticore_cli.config import ConfigManager, OptiCoreConfig
from opticore_cli.live_monitor import LiveEventMonitor
from opticore_cli.ui import (
    console,
    print_banner,
    render_events_table,
    render_health,
    render_help,
    render_metrics,
    render_status,
    render_voice_status,
)
from opticore_cli.camera import CameraStreamManager, detect_cameras, run_camera_stream_sync
from opticore_cli.voice import VoiceAlertEngine


class OptiCoreCLI:
    """OptiCore Interactive Command Center Shell."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.config
        self.client = OptiCoreClient(
            base_url=self.config.server_url,
            timeout=self.config.timeout,
        )
        self.voice = VoiceAlertEngine(
            enabled=self.config.voice_enabled,
            verbosity=self.config.voice_verbosity,
            rate=self.config.voice_rate,
            volume=self.config.voice_volume,
            cooldown=self.config.voice_cooldown,
        )
        self.camera_manager = CameraStreamManager(
            config_manager=self.config_manager,
            voice_engine=self.voice,
        )
        self.running = False

    def get_prompt_text(self) -> str:
        """Constructs a colorized, informative REPL prompt."""
        if self.client.is_configured():
            # Show abbreviated hostname / ngrok ID
            url = self.client.base_url
            short_url = url.replace("https://", "").replace("http://", "")
            if len(short_url) > 28:
                short_url = short_url[:25] + "..."
            conn_tag = f"[bold green]{short_url}[/bold green]"
        else:
            conn_tag = "[bold yellow]Disconnected[/bold yellow]"

        v_tag = "[green]Voice:ON[/green]" if self.voice.enabled else "[dim]Voice:OFF[/dim]"
        return f"[{conn_tag} | {v_tag}] opticore> "

    def handle_connect(self, args: List[str]) -> None:
        """Connects to an OptiCore server and runs health check."""
        target_url = args[0] if args else self.config.server_url

        if not target_url:
            target_url = Prompt.ask("[bold cyan]Enter OptiCore server URL[/bold cyan] (e.g. ngrok public URL)")

        if not target_url.strip():
            console.print("[red]No URL provided. Connection aborted.[/red]")
            return

        with console.status(f"[bold cyan]Connecting to {target_url}...[/bold cyan]"):
            result = self.client.ping(target_url)

        if result.ok:
            self.client.set_base_url(result.url)
            self.config.server_url = result.url
            self.config_manager.save()

            console.print(f"[bold green]Connected successfully to OptiCore server![/bold green]")
            console.print(f"[dim]URL: {result.url} | Round-trip latency: {result.latency_ms:.1f} ms[/dim]")

            if result.health:
                console.print(render_health(result.health))
            elif result.status:
                console.print(render_status(result.status))
        else:
            console.print(f"[bold red]Connection failed:[/bold red] {result.error_message}")
            if "ngrok" in result.url:
                console.print("[dim]Tip: Check if the Kaggle notebook is running and public ngrok tunnel is open.[/dim]")

    def handle_disconnect(self) -> None:
        """Disconnects from current server."""
        old = self.client.base_url
        self.client.set_base_url("")
        console.print(f"[yellow]Disconnected from {old or 'server'}.[/yellow]")

    def handle_health(self) -> None:
        """Displays /health response."""
        if not self.client.is_configured():
            console.print("[red]Not connected to any server. Run 'connect <url>' first.[/red]")
            return

        try:
            with console.status("[cyan]Fetching server health...[/cyan]"):
                health = self.client.get_health()
            console.print(render_health(health))
        except Exception as e:
            console.print(f"[bold red]Error fetching health:[/bold red] {e}")

    def handle_status(self) -> None:
        """Displays /status response."""
        if not self.client.is_configured():
            console.print("[red]Not connected to any server. Run 'connect <url>' first.[/red]")
            return

        try:
            with console.status("[cyan]Fetching server status...[/cyan]"):
                status = self.client.get_status()
            console.print(render_status(status))
        except Exception as e:
            console.print(f"[bold red]Error fetching status:[/bold red] {e}")

    def handle_metrics(self) -> None:
        """Displays /metrics response."""
        if not self.client.is_configured():
            console.print("[red]Not connected to any server. Run 'connect <url>' first.[/red]")
            return

        try:
            with console.status("[cyan]Fetching performance metrics...[/cyan]"):
                metrics = self.client.get_metrics()
            console.print(render_metrics(metrics))
        except Exception as e:
            console.print(f"[bold red]Error fetching metrics:[/bold red] {e}")

    def handle_events(self, args: List[str]) -> None:
        """Displays recent detection alert events from /events?limit=N."""
        if not self.client.is_configured():
            console.print("[red]Not connected to any server. Run 'connect <url>' first.[/red]")
            return

        limit = 20
        if args:
            try:
                # Handle either 'events 20' or 'events --limit 20'
                val = args[1] if args[0] in {"--limit", "-l", "-n"} and len(args) > 1 else args[0]
                limit = int(val)
            except ValueError:
                console.print(f"[yellow]Invalid limit '{args[0]}'. Using default limit of 20.[/yellow]")

        try:
            with console.status(f"[cyan]Fetching last {limit} events...[/cyan]"):
                events = self.client.get_events(limit=limit)
            console.print(render_events_table(events, title=f"Last {len(events)} Detection Events"))
        except Exception as e:
            console.print(f"[bold red]Error fetching events:[/bold red] {e}")

    def handle_monitor(self, args: List[str]) -> None:
        """Enters live detection log streaming mode."""
        if not self.client.is_configured():
            console.print("[red]Not connected to any server. Run 'connect <url>' first.[/red]")
            return

        poll_interval = self.config.poll_interval
        new_window = False

        if args:
            if "--new-window" in args or "-w" in args:
                new_window = True
            for idx, a in enumerate(args):
                if a in {"--poll", "-p"} and idx + 1 < len(args):
                    try:
                        poll_interval = float(args[idx + 1])
                    except ValueError:
                        pass
                elif a.replace(".", "", 1).isdigit():
                    try:
                        poll_interval = float(a)
                    except ValueError:
                        pass

        if new_window:
            from opticore_cli.menu import launch_in_new_window
            ok, msg = launch_in_new_window(
                server_url=self.client.base_url,
                poll=poll_interval,
                voice=self.voice.enabled,
                verbosity=self.voice.verbosity,
            )
            if ok:
                console.print(f"[bold green]✓ {msg}[/bold green]")
            else:
                console.print(f"[bold yellow]! {msg}[/bold yellow]")
            return

        monitor = LiveEventMonitor(
            client=self.client,
            voice_engine=self.voice,
            poll_interval=poll_interval,
            max_seen_cache=self.config.max_log_history,
        )
        monitor.run()

    def handle_camera(self, args: List[str]) -> None:
        """Controls background camera streaming or lists hardware cameras."""
        action = args[0].lower() if args else "status"

        if action in {"on", "start"}:
            if not self.client.is_configured():
                console.print("[red]Not connected to any server. Run 'connect <url>' first.[/red]")
                return
            with console.status("[cyan]Starting camera stream to server...[/cyan]"):
                ok, msg = self.camera_manager.start(self.client.base_url)
            if ok:
                console.print(f"[bold green]✓ {msg}[/bold green]")
            else:
                console.print(f"[bold red]Failed to start camera: {msg}[/bold red]")

        elif action in {"off", "stop"}:
            ok, msg = self.camera_manager.stop()
            console.print(f"[bold yellow]{msg}[/bold yellow]")

        elif action in {"toggle"}:
            if self.camera_manager.is_active:
                self.camera_manager.stop()
                console.print("[yellow]Camera stream stopped.[/yellow]")
            else:
                self.handle_camera(["on"])

        elif action in {"status"}:
            st = self.camera_manager.get_status_dict()
            status_tag = "[bold green]STREAMING (ON)[/bold green]" if st["active"] else "[bold red]OFF[/bold red]"
            console.print(f"Camera Stream: {status_tag} | Device: {st['source']} | Frames sent: {st['frames_sent']} | FPS: {st['fps']}")
            if st.get("last_error"):
                console.print(f"[yellow]Notice: {st['last_error']}[/yellow]")

        elif action in {"list", "devices"}:
            with console.status("[cyan]Scanning for connected cameras...[/cyan]"):
                cams = detect_cameras(max_probe=5)
            if not cams:
                console.print("[yellow]No camera devices detected.[/yellow]")
            else:
                console.print(f"[bold cyan]Detected {len(cams)} camera device(s):[/bold cyan]")
                for c in cams:
                    console.print(f"  • Device {c['index']}: [white]{c['label']}[/white] ([yellow]{c['resolution']}[/yellow])")

        elif action in {"stream"}:
            new_window = "--new-window" in args or "-w" in args
            show = "--show" in args or self.config.camera_show_preview
            cam_src = self.config.camera_source
            for idx, a in enumerate(args):
                if a in {"--camera", "-c"} and idx + 1 < len(args):
                    cam_src = args[idx + 1]

            if new_window:
                from opticore_cli.menu import launch_camera_in_new_window
                ok, msg = launch_camera_in_new_window(
                    server_url=self.client.base_url,
                    camera_source=cam_src,
                    fps=self.config.camera_fps,
                    width=self.config.camera_width,
                    quality=self.config.camera_quality,
                    show_window=show,
                )
                if ok:
                    console.print(f"[bold green]✓ {msg}[/bold green]")
                else:
                    console.print(f"[bold yellow]! {msg}[/bold yellow]")
                return

            run_camera_stream_sync(
                server_url=self.client.base_url,
                camera_source=cam_src,
                width=self.config.camera_width,
                target_fps=self.config.camera_fps,
                quality=self.config.camera_quality,
                show_window=show,
                voice_engine=self.voice,
            )

        else:
            console.print(f"[yellow]Usage: camera [on|off|toggle|status|list|stream][/yellow]")

    def handle_voice(self, args: List[str]) -> None:
        """Controls local voice alerts."""
        if not args:
            console.print(render_voice_status(self.voice.get_status_dict()))
            return

        action = args[0].lower()
        if action in {"on", "enable", "start"}:
            self.voice.set_enabled(True)
            self.config.voice_enabled = True
            self.config_manager.save()
            console.print("[bold green]Voice alerts ENABLED.[/bold green]")
            self.voice.speak_text("OptiCore voice alerts enabled.", force=True)

        elif action in {"off", "disable", "stop"}:
            self.voice.set_enabled(False)
            self.config.voice_enabled = False
            self.config_manager.save()
            console.print("[yellow]Voice alerts DISABLED.[/yellow]")

        elif action == "status":
            console.print(render_voice_status(self.voice.get_status_dict()))

        elif action == "test":
            console.print("[cyan]Testing voice alert output...[/cyan]")
            ok = self.voice.speak_text("OptiCore command center test announcement. Audio engine ready.", force=True)
            if ok:
                console.print("[green]Voice test sent to speech queue.[/green]")
            else:
                console.print("[yellow]Voice output could not be queued. Check audio hardware.[/yellow]")

        elif action == "verbosity":
            if len(args) < 2:
                console.print(f"Current verbosity: [bold cyan]{self.voice.verbosity}[/bold cyan] (options: all, priority, critical)")
                return
            level = args[1].lower()
            if self.voice.set_verbosity(level):
                self.config.voice_verbosity = level
                self.config_manager.save()
                console.print(f"[green]Voice verbosity set to: {level}[/green]")
            else:
                console.print("[red]Invalid verbosity level. Choose from: all, priority, critical[/red]")

        elif action == "rate":
            if len(args) < 2:
                console.print(f"Current speech rate: [bold cyan]{self.voice.rate}[/bold cyan] wpm (range: 100-350)")
                return
            try:
                rate = int(args[1])
                self.voice.set_rate(rate)
                self.config.voice_rate = self.voice.rate
                self.config_manager.save()
                console.print(f"[green]Speech rate set to: {self.voice.rate} wpm[/green]")
            except ValueError:
                console.print("[red]Invalid rate. Provide an integer like 180.[/red]")

        elif action == "volume":
            if len(args) < 2:
                console.print(f"Current speech volume: [bold cyan]{int(self.voice.volume * 100)}%[/bold cyan]")
                return
            try:
                vol = float(args[1])
                if vol > 1.0:
                    vol = vol / 100.0  # Handle 0-100 input
                self.voice.set_volume(vol)
                self.config.voice_volume = self.voice.volume
                self.config_manager.save()
                console.print(f"[green]Speech volume set to: {int(self.voice.volume * 100)}%[/green]")
            except ValueError:
                console.print("[red]Invalid volume. Provide a value from 0.0 to 1.0 or percentage.[/red]")

        elif action == "cooldown":
            if len(args) < 2:
                console.print(f"Current deduplication cooldown: [bold cyan]{self.voice.cooldown:.1f}s[/bold cyan]")
                return
            try:
                cd = float(args[1])
                self.voice.set_cooldown(cd)
                self.config.voice_cooldown = self.voice.cooldown
                self.config_manager.save()
                console.print(f"[green]Deduplication cooldown set to: {self.voice.cooldown:.1f} seconds[/green]")
            except ValueError:
                console.print("[red]Invalid cooldown value.[/red]")
        else:
            console.print(f"[yellow]Unknown voice command '{action}'. Use: on, off, status, test, verbosity, rate, volume, cooldown[/yellow]")

    def handle_config(self, args: List[str]) -> None:
        """Inspects or modifies configuration."""
        if not args or args[0] == "show":
            table = Table(box=box.ROUNDED, header_style="bold cyan", title="OptiCore Configuration")
            table.add_column("Setting", style="yellow")
            table.add_column("Current Value", style="white")
            table.add_column("Source Path", style="dim")

            for k, v in self.config.to_dict().items():
                table.add_row(k, str(v), str(self.config_manager.config_path))
            console.print(table)

        elif args[0] == "set":
            if len(args) < 3:
                console.print("[red]Usage: config set <key> <value>[/red]")
                return
            key, val = args[1], args[2]
            if self.config_manager.set(key, val):
                self.config_manager.save()
                self.config = self.config_manager.config
                # Propagate updates to client/voice if applicable
                if key == "server_url":
                    self.client.set_base_url(self.config.server_url)
                elif key == "timeout":
                    self.client.timeout = self.config.timeout
                elif key == "voice_enabled":
                    self.voice.set_enabled(self.config.voice_enabled)
                elif key == "voice_verbosity":
                    self.voice.set_verbosity(self.config.voice_verbosity)
                console.print(f"[green]Configuration '{key}' updated to '{val}'.[/green]")
            else:
                console.print(f"[red]Failed to set '{key}'. Verify key name and format.[/red]")

        elif args[0] == "reset":
            self.config_manager.reset()
            self.config = self.config_manager.config
            console.print("[yellow]Configuration reset to default values.[/yellow]")
        else:
            console.print("[yellow]Unknown config action. Use: show, set, reset[/yellow]")

    def handle_command(self, cmd_line: str) -> bool:
        """Parses and dispatches a single command line. Returns False if exiting."""
        trimmed = cmd_line.strip()
        if not trimmed:
            return True

        try:
            parts = shlex.split(trimmed)
        except ValueError:
            parts = trimmed.split()

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in {"exit", "quit", "q"}:
            return False

        elif cmd == "help":
            console.print(render_help())

        elif cmd in {"clear", "cls"}:
            os.system("cls" if os.name == "nt" else "clear")
            print_banner()

        elif cmd == "connect":
            self.handle_connect(args)

        elif cmd == "disconnect":
            self.handle_disconnect()

        elif cmd == "health":
            self.handle_health()

        elif cmd == "status":
            self.handle_status()

        elif cmd == "metrics":
            self.handle_metrics()

        elif cmd in {"menu", "toggle"}:
            from opticore_cli.menu import InteractiveMenu
            InteractiveMenu(self).run()

        elif cmd in {"events", "alerts"}:
            self.handle_events(args)

        elif cmd in {"camera", "cam"}:
            self.handle_camera(args)

        elif cmd in {"stream", "stream-camera"}:
            self.handle_camera(["stream"] + args)

        elif cmd in {"voice", "audio", "speech"}:
            self.handle_voice(args)

        elif cmd in {"config", "cfg"}:
            self.handle_config(args)

        else:
            console.print(f"[red]Unknown command: '{cmd}'. Type [bold cyan]help[/bold cyan] for available commands.[/red]")

        return True

    def run_interactive(self) -> None:
        """Starts the interactive Command Center shell loop."""
        print_banner()
        self.running = True

        # If a server URL is already configured, test connection automatically
        if self.config.server_url:
            console.print(f"[dim]Checking saved server URL: {self.config.server_url}...[/dim]")
            res = self.client.ping()
            if res.ok:
                console.print(f"[bold green]Connected to OptiCore server ({res.latency_ms:.1f} ms)[/bold green]")
            else:
                console.print(f"[yellow]Could not connect to saved URL: {res.error_message}[/yellow]")
                console.print("[dim]Use 'connect <url>' to set a new server URL.[/dim]")

        console.print("[dim]Type [bold cyan]help[/bold cyan] for commands, [bold cyan]monitor[/bold cyan] for live logs, [bold cyan]exit[/bold cyan] to quit.[/dim]\n")

        while self.running:
            try:
                prompt_str = self.get_prompt_text()
                # Use standard input prompt
                cmd = console.input(prompt_str)
                if not self.handle_command(cmd):
                    break
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Received exit signal.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]Command error: {e}[/red]")

        self.shutdown()

    def shutdown(self) -> None:
        """Performs clean shutdown of CLI and background workers."""
        self.running = False
        self.camera_manager.stop()
        self.voice.shutdown()
        console.print("[bold cyan]OptiCore CLI Command Center safely closed. Goodbye![/bold cyan]")


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds top-level CLI argument parser with inherited subcommand flags."""
    common_parent = argparse.ArgumentParser(add_help=False)
    common_parent.add_argument("--url", help="Target OptiCore server URL (ngrok or IP)")
    common_parent.add_argument("--voice", action="store_true", help="Enable voice alerts")
    common_parent.add_argument("--verbosity", choices=["all", "priority", "critical"], help="Voice alert verbosity")
    common_parent.add_argument("--timeout", type=float, help="HTTP request timeout in seconds")

    parser = argparse.ArgumentParser(
        prog="opticore-cli",
        description="OptiCore CLI Command Center - Assistive Vision Edge Interface",
        parents=[common_parent],
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute directly")

    # menu (interactive arrow-key toggle menu)
    subparsers.add_parser("menu", parents=[common_parent], help="Start interactive arrow-key toggle menu")

    # interactive (classic prompt mode)
    subparsers.add_parser("interactive", parents=[common_parent], help="Start classic command prompt")

    # connect
    p_connect = subparsers.add_parser("connect", parents=[common_parent], help="Test and set server connection")
    p_connect.add_argument("server_url", nargs="?", help="Server URL to connect to")

    # health
    subparsers.add_parser("health", parents=[common_parent], help="Check server health and model state")

    # status
    subparsers.add_parser("status", parents=[common_parent], help="View full server status and metrics")

    # metrics
    subparsers.add_parser("metrics", parents=[common_parent], help="View inference performance metrics")

    # events
    p_events = subparsers.add_parser("events", parents=[common_parent], help="View recent detection events")
    p_events.add_argument("--limit", "-n", type=int, default=20, help="Number of events to retrieve (1-100)")

    # monitor
    p_mon = subparsers.add_parser("monitor", parents=[common_parent], help="Stream live detection logs")
    p_mon.add_argument("--poll", "-p", type=float, default=1.0, help="Polling interval in seconds")
    p_mon.add_argument("--new-window", "-w", action="store_true", help="Open stream in a dedicated new shell window")

    # stream (camera)
    p_stream = subparsers.add_parser("stream", parents=[common_parent], help="Stream local/remote camera to server (/ws/video)")
    p_stream.add_argument("--camera", "-c", default=None, help="Camera device index (0, 1) or video source")
    p_stream.add_argument("--fps", type=float, default=None, help="Target frames per second")
    p_stream.add_argument("--width", type=int, default=None, help="Frame width in pixels")
    p_stream.add_argument("--quality", type=int, default=None, help="JPEG compression quality (1-100)")
    p_stream.add_argument("--show", action="store_true", help="Display local preview window with server annotations")
    p_stream.add_argument("--new-window", "-w", action="store_true", help="Open camera stream in a dedicated new shell window")

    # camera
    p_cam = subparsers.add_parser("camera", parents=[common_parent], help="Control background camera stream (on/off/status/list)")
    p_cam.add_argument("action", nargs="?", default="status", choices=["on", "off", "toggle", "status", "list"], help="Camera action")

    # voice
    p_voice = subparsers.add_parser("voice", parents=[common_parent], help="Control or test voice alerts")
    p_voice.add_argument("action", nargs="?", default="status", choices=["on", "off", "status", "test"], help="Voice action")

    # config
    p_cfg = subparsers.add_parser("config", parents=[common_parent], help="View or modify configuration")
    p_cfg.add_argument("action", nargs="?", default="show", choices=["show", "reset"], help="Config action")

    # mock-server
    p_mock = subparsers.add_parser("mock-server", parents=[common_parent], help="Run local OptiCore mock server")
    p_mock.add_argument("--port", type=int, default=8000, help="Port to bind")
    p_mock.add_argument("--host", default="127.0.0.1", help="Host interface to bind")

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """CLI execution entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    config_manager = ConfigManager()

    # Apply command-line overrides
    if args.url:
        config_manager.config.server_url = args.url
    if args.voice:
        config_manager.config.voice_enabled = True
    if args.verbosity:
        config_manager.config.voice_verbosity = args.verbosity
    if args.timeout:
        config_manager.config.timeout = args.timeout

    cli = OptiCoreCLI(config_manager=config_manager)

    # Dispatch subcommand or launch interactive menu by default
    if args.command is None or args.command == "menu":
        from opticore_cli.menu import InteractiveMenu
        InteractiveMenu(cli).run()
    elif args.command == "interactive" or args.command == "prompt":
        cli.run_interactive()
    elif args.command == "connect":
        cli.handle_connect([args.server_url] if args.server_url else [])
        cli.shutdown()
    elif args.command == "health":
        cli.handle_health()
        cli.shutdown()
    elif args.command == "status":
        cli.handle_status()
        cli.shutdown()
    elif args.command == "metrics":
        cli.handle_metrics()
        cli.shutdown()
    elif args.command == "events":
        cli.handle_events(["--limit", str(args.limit)])
        cli.shutdown()
    elif args.command == "monitor":
        mon_args = ["--poll", str(args.poll)]
        if getattr(args, "new_window", False):
            mon_args.append("--new-window")
        cli.handle_monitor(mon_args)
        cli.shutdown()
    elif args.command == "camera":
        cli.handle_camera([args.action])
        cli.shutdown()
    elif args.command == "stream":
        stream_args = []
        if args.camera is not None:
            stream_args.extend(["--camera", str(args.camera)])
        if args.show:
            stream_args.append("--show")
        if getattr(args, "new_window", False):
            stream_args.append("--new-window")
        cli.handle_camera(["stream"] + stream_args)
        cli.shutdown()
    elif args.command == "voice":
        cli.handle_voice([args.action])
        cli.shutdown()
    elif args.command == "config":
        cli.handle_config([args.action])
        cli.shutdown()
    elif args.command == "mock-server":
        from opticore_cli.mock_server import run_mock_server
        print(f"Starting OptiCore mock server at http://{args.host}:{args.port}")
        run_mock_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
