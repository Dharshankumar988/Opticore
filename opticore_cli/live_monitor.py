"""Live detection event monitor and streamer for OptiCore CLI."""

import time
from collections import deque
from typing import Optional, Set

from opticore_cli.client import OptiCoreClient
from opticore_cli.ui import console, print_event_log_line
from opticore_cli.voice import VoiceAlertEngine


class LiveEventMonitor:
    """Streams live detection events from the OptiCore server and triggers voice alerts."""

    def __init__(
        self,
        client: OptiCoreClient,
        voice_engine: VoiceAlertEngine,
        poll_interval: float = 1.0,
        max_seen_cache: int = 500,
    ):
        self.client = client
        self.voice_engine = voice_engine
        self.poll_interval = max(0.2, poll_interval)
        self.seen_event_keys: deque = deque(maxlen=max_seen_cache)
        self.seen_set: Set[str] = set()

    def run(self, max_events: Optional[int] = None) -> int:
        """Runs the live monitoring loop until interrupted by user (Ctrl+C).

        Returns the number of new events captured during this session.
        """
        if not self.client.is_configured():
            console.print("[bold red]Cannot start monitor: Server URL is not configured.[/bold red]")
            return 0

        console.print("\n[bold cyan]--- LIVE PRIORITY ALERT STREAM STARTED ---[/bold cyan]")
        console.print(f"[dim]Connected to: {self.client.base_url} (Poll interval: {self.poll_interval:.1f}s)[/dim]")
        voice_state = "[bold green]ON[/bold green]" if self.voice_engine.enabled else "[dim]OFF[/dim]"
        console.print(f"[dim]Voice alerts: {voice_state} (Verbosity: {self.voice_engine.verbosity})[/dim]")
        console.print("[dim]Streaming priority detection alerts from server /events (raw video frames are handled by camera producer).[/dim]")
        console.print("[dim]Press [bold white]Ctrl+C[/bold white] at any time to return to Command Center.[/dim]\n")

        # Initial bootstrap: populate seen cache with current events so we don't dump old history on start
        try:
            initial_events = self.client.get_events(limit=50)
            for e in initial_events:
                k = e.event_key
                self.seen_set.add(k)
                self.seen_event_keys.append(k)
        except Exception:
            pass

        events_captured = 0
        consecutive_errors = 0
        max_backoff = 8.0

        try:
            while True:
                if max_events is not None and events_captured >= max_events:
                    break

                try:
                    events = self.client.get_events(limit=30)
                    if consecutive_errors > 0:
                        console.print("[bold green]Connection restored to OptiCore server.[/bold green]")
                        consecutive_errors = 0

                    # Events from server are latest-first (prepend), so sort chronologically (oldest to newest)
                    events.sort(key=lambda x: x.timestamp)

                    for event in events:
                        key = event.event_key
                        if key not in self.seen_set:
                            # New event!
                            self.seen_set.add(key)
                            self.seen_event_keys.append(key)

                            # Prune set if deque evacuated old items
                            if len(self.seen_set) > len(self.seen_event_keys) * 1.5:
                                self.seen_set = set(self.seen_event_keys)

                            # Display formatted log line
                            print_event_log_line(event)

                            # Dispatch to voice engine
                            if self.voice_engine.enabled:
                                self.voice_engine.enqueue_event(event)

                            events_captured += 1
                            if max_events is not None and events_captured >= max_events:
                                break

                    time.sleep(self.poll_interval)

                except Exception as err:
                    consecutive_errors += 1
                    backoff = min(max_backoff, self.poll_interval * (1.5 ** min(consecutive_errors, 5)))
                    if consecutive_errors == 1:
                        console.print(f"[yellow]Stream interrupted ({str(err)[:80]}). Reconnecting...[/yellow]")
                    elif consecutive_errors % 5 == 0:
                        console.print(f"[yellow]Still attempting to reconnect (attempt {consecutive_errors})...[/yellow]")
                    time.sleep(backoff)

        except KeyboardInterrupt:
            console.print("\n[dim]Stopping live detection stream...[/dim]")

        console.print(f"[bold cyan]--- STREAM STOPPED ({events_captured} events captured) ---[/bold cyan]\n")
        return events_captured
