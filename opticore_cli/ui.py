"""Terminal UI formatting and rendering using Rich for OptiCore CLI."""

import sys
from typing import List, Optional
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from opticore_cli.models import DetectionEvent, ServerHealth, ServerMetrics, ServerStatus

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(safe_box=True)


def print_banner() -> None:
    """Prints the rich OptiCore header banner."""
    header_text = Text()
    header_text.append("OPTICORE ", style="bold cyan")
    header_text.append("CLI COMMAND CENTER ", style="bold white")
    header_text.append("v1.2.0\n", style="dim cyan")
    header_text.append("Real-Time Assistive Vision & Edge Monitoring Interface\n", style="italic blue")
    header_text.append("Compatible with Windows 10/11 & Raspberry Pi OS (ARM64)", style="dim")

    panel = Panel(
        header_text,
        box=box.DOUBLE_EDGE,
        border_style="cyan",
        subtitle="[dim]Type 'help' for available commands[/dim]",
        subtitle_align="right",
    )
    console.print(panel)


def get_priority_styled(priority: str) -> Text:
    """Returns a color-coded priority badge."""
    p = priority.upper()
    if p == "P1":
        return Text(" P1 CRITICAL ", style="bold white on red")
    elif p == "P2":
        return Text(" P2 WARNING  ", style="bold black on dark_orange")
    elif p == "P3":
        return Text(" P3 CAUTION  ", style="bold black on yellow")
    else:
        return Text(" P4 INFO     ", style="bold white on blue")


def render_health(health: ServerHealth) -> Panel:
    """Renders server health information in a structured panel."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Property", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    status_style = "bold green" if health.status == "ok" else "bold red"
    table.add_row("Server Status", Text(health.status.upper(), style=status_style))
    table.add_row("Model Loaded", "[green]Yes[/green]" if health.model_loaded else "[red]No[/red]")
    table.add_row("Inference Device", health.device)
    table.add_row("Classes Configured", str(health.classes))
    table.add_row("Active Tracker", health.tracker or "None")
    table.add_row("Input Resolution", f"{health.imgsz}x{health.imgsz}")
    table.add_row("Frames Processed", f"{health.frames_processed:,}")
    table.add_row("Last Inference Latency", f"{health.last_inference_ms:.1f} ms")
    table.add_row("Average Inference Latency", f"{health.avg_inference_ms:.1f} ms")
    table.add_row("Stream FPS (EMA)", f"{health.fps_ema:.1f} FPS")
    table.add_row("Frames Rejected", str(health.frames_rejected))

    return Panel(table, title="[bold cyan]OptiCore Server Health[/bold cyan]", border_style="cyan")


def render_status(status: ServerStatus) -> Panel:
    """Renders full server status in a structured panel."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Property", style="bold cyan", width=22)
    table.add_column("Value", style="white")

    table.add_row("Service Name", status.service)
    table.add_row("API Version", status.version)
    table.add_row("Model Loaded", "[green]Ready[/green]" if status.model_loaded else "[red]Not Loaded[/red]")
    table.add_row("Device / Compute", status.device)
    gpu_txt = f"{status.gpu_name} ([green]Available[/green])" if status.gpu_available else "[yellow]CPU Only[/yellow]"
    table.add_row("GPU Hardware", gpu_txt)

    prod_txt = f"[green]Active[/green] (Producer ID: {status.producer_id})" if status.producer_active else "[dim]Idle (No active camera)[/dim]"
    table.add_row("Camera Stream", prod_txt)

    # Convert uptime
    mins, secs = divmod(int(status.uptime_seconds), 60)
    hours, mins = divmod(mins, 60)
    uptime_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"
    table.add_row("Server Uptime", uptime_str)

    table.add_row("Priority Engine", status.priority_engine)
    table.add_row("Speech Policy", status.speech_policy)

    # Sub-metrics
    m = status.metrics
    if m:
        table.add_row("Frames Processed", str(m.get("frames_processed", 0)))
        table.add_row("Avg Inference", f"{m.get('avg_inference_ms', 0):.1f} ms")
        table.add_row("Stream FPS", f"{m.get('fps_ema', 0):.1f}")

    return Panel(table, title="[bold cyan]OptiCore Server Status & Configuration[/bold cyan]", border_style="cyan")


def render_metrics(metrics: ServerMetrics) -> Panel:
    """Renders performance metrics table."""
    table = Table(box=box.ROUNDED, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold white", justify="right")

    table.add_row("Total Processed Frames", f"{metrics.frames_processed:,}")
    table.add_row("Last Inference Latency", f"{metrics.last_inference_ms:.2f} ms")
    table.add_row("Rolling Average Latency", f"{metrics.avg_inference_ms:.2f} ms")
    table.add_row("Estimated Stream Rate", f"{metrics.fps_ema:.2f} FPS")
    table.add_row("Rejected / Dropped Frames", str(metrics.frames_rejected))

    return Panel(table, title="[bold magenta]Inference & Pipeline Performance[/bold magenta]", border_style="magenta")


def render_events_table(events: List[DetectionEvent], title: str = "Recent Priority Detection Alerts (Server /events)") -> Table:
    """Renders a formatted table of detection priority alerts."""
    table = Table(
        box=box.ROUNDED,
        header_style="bold cyan",
        title=title,
        caption="[dim]Streaming detection alerts from server /events; raw frame-by-frame boxes are handled by the camera producer.[/dim]",
        caption_align="left",
    )
    table.add_column("Time", style="dim", width=10, no_wrap=True)
    table.add_column("Priority", justify="center", width=13)
    table.add_column("Class", style="bold white", width=10)
    table.add_column("Track", style="magenta", width=8)
    table.add_column("Conf", justify="right", width=7)
    table.add_column("Pos", style="yellow", width=7)
    table.add_column("Movement", style="cyan", width=18)
    table.add_column("Risk", justify="right", width=6)
    table.add_column("Message", style="italic white")

    if not events:
        table.add_row("-", "-", "No events", "-", "-", "-", "-", "-", "No detection alerts recorded.")
        return table

    for e in events:
        badge = get_priority_styled(e.priority)
        table.add_row(
            e.formatted_time,
            badge,
            e.name,
            e.tracking_id_display,
            e.confidence_pct,
            e.position,
            e.movement_display,
            f"{e.risk_score:.1f}",
            e.message,
        )

    return table


def print_event_log_line(e: DetectionEvent) -> None:
    """Prints a single live detection log line in streaming mode."""
    badge = get_priority_styled(e.priority)
    line = Text()
    line.append(f"[{e.formatted_time}] ", style="dim")
    line.append_text(badge)
    line.append(f" {e.name.upper():<10}", style="bold white")
    line.append(f" ({e.tracking_id_display})", style="magenta")
    line.append(f" conf:{e.confidence_pct:>5}", style="dim")
    line.append(f" pos:{e.position:<6}", style="yellow")
    if e.approaching:
        dir_str = e.approach_direction or "head-on"
        line.append(f" [APPROACHING: {dir_str}]", style="bold red")
    line.append(f" risk:{e.risk_score:.0f}", style="dim")
    line.append(f" -> {e.message}", style="white")

    console.print(line)


def render_voice_status(status: dict) -> Panel:
    """Renders voice alert subsystem status."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Parameter", style="bold cyan", width=22)
    table.add_column("Setting", style="white")

    enabled = status.get("enabled", False)
    table.add_row("Voice Alerts", "[bold green]ENABLED[/bold green]" if enabled else "[bold red]DISABLED[/bold red]")
    table.add_row("Alert Verbosity", status.get("verbosity", "priority").upper())
    table.add_row("Audio Engine", status.get("backend", "none"))
    table.add_row("Audio Hardware Ready", "[green]Yes[/green]" if status.get("available") else "[yellow]Unavailable (Silent Fallback)[/yellow]")
    table.add_row("Speech Rate", f"{status.get('rate', 180)} words/min")
    table.add_row("Speech Volume", f"{int(status.get('volume', 1.0) * 100)}%")
    table.add_row("Deduplication Cooldown", f"{status.get('cooldown', 7.0)} seconds")
    table.add_row("Pending Queue", str(status.get("pending_in_queue", 0)))

    return Panel(table, title="[bold cyan]CLI Voice Alert System[/bold cyan]", border_style="cyan")


def render_help() -> Panel:
    """Renders help command reference table."""
    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Command", style="bold yellow", width=18)
    table.add_column("Syntax", style="cyan", width=26)
    table.add_column("Description", style="white")

    table.add_row("menu", "menu", "Open the interactive arrow-key toggle menu")
    table.add_row("connect", "connect [URL]", "Connect to OptiCore server (supports ngrok or direct IP)")
    table.add_row("disconnect", "disconnect", "Disconnect from current server")
    table.add_row("status", "status", "View server status, GPU, active camera, and uptime")
    table.add_row("health", "health", "Check server health, model state, and inference metrics")
    table.add_row("metrics", "metrics", "View detailed pipeline performance metrics")
    table.add_row("events", "events [--limit N]", "Display the most recent detection alert events (1-100)")
    table.add_row("monitor / logs", "monitor [-w] [--poll S]", "Stream live logs (-w / --new-window opens in dedicated shell)")
    table.add_row("stream / camera", "stream [-w] [-c CAM] [--show]", "Stream local/remote camera to server (/ws/video)")
    table.add_row("voice", "voice [on|off|status|test]", "Enable, disable, check, or test local CLI voice alerts")
    table.add_row("voice verbosity", "voice verbosity <all|priority|critical>", "Set voice filtering level")
    table.add_row("voice rate", "voice rate <100-350>", "Set voice speech rate in words per minute")
    table.add_row("voice volume", "voice volume <0.0-1.0>", "Set voice alert volume")
    table.add_row("config", "config [show|set <k> <v>]", "View or update CLI configuration")
    table.add_row("clear", "clear", "Clear terminal screen")
    table.add_row("help", "help", "Show this command reference")
    table.add_row("exit / quit", "exit", "Safely exit OptiCore CLI Command Center")

    return Panel(table, title="[bold cyan]OptiCore CLI Command Reference[/bold cyan]", border_style="cyan")
