"""HTTP client for communicating with the OptiCore Vision API server."""

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from opticore_cli.models import (
    ConnectionResult,
    DetectionEvent,
    ServerHealth,
    ServerMetrics,
    ServerStatus,
)


class OptiCoreAPIError(Exception):
    """Raised when an API request to OptiCore server fails with a diagnostic explanation."""
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception


class OptiCoreClient:
    """Handles communication with the OptiCore FastAPI backend."""

    DEFAULT_HEADERS = {
        "User-Agent": "OptiCore-CLI/1.2.0",
        "Accept": "application/json",
        # Avoids ngrok's free-tier HTML interstitial landing page
        "ngrok-skip-browser-warning": "69420",
    }

    def __init__(self, base_url: str = "", timeout: float = 6.0):
        self.base_url = self.sanitize_url(base_url) if base_url else ""
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    @staticmethod
    def sanitize_url(raw_url: str) -> str:
        """Sanitizes and normalizes an input URL."""
        if not raw_url:
            return ""
        url = raw_url.strip()
        if not url:
            return ""

        # Default to http:// if no protocol supplied (or https:// for ngrok domains)
        if not url.startswith("http://") and not url.startswith("https://"):
            if "ngrok" in url:
                url = f"https://{url}"
            else:
                url = f"http://{url}"

        # If ngrok URL is HTTP, upgrade to HTTPS to avoid redirection issues
        if "ngrok" in url and url.startswith("http://"):
            url = "https://" + url[len("http://"):]

        return url.rstrip("/")

    def set_base_url(self, url: str) -> None:
        """Sets and normalizes the target server base URL."""
        self.base_url = self.sanitize_url(url)

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise ValueError("OptiCore server URL is not configured. Run 'connect <url>' first.")
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{clean_path}"

    def ping(self, target_url: Optional[str] = None) -> ConnectionResult:
        """Tests connectivity and measures round-trip latency to /health and /status."""
        url = self.sanitize_url(target_url) if target_url else self.base_url
        if not url:
            return ConnectionResult(
                ok=False,
                url="",
                error_message="No server URL provided. Please specify a URL.",
            )

        health_url = f"{url}/health"
        start_time = time.perf_counter()

        try:
            resp = self.session.get(health_url, timeout=self.timeout)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code == 200:
                # Ensure it returned JSON, not an HTML error/warning page
                content_type = resp.headers.get("content-type", "")
                if "application/json" not in content_type:
                    text_sample = resp.text[:200].strip()
                    if "ngrok" in text_sample.lower():
                        return ConnectionResult(
                            ok=False,
                            url=url,
                            latency_ms=elapsed_ms,
                            status_code=resp.status_code,
                            error_message="Received ngrok interstitial page instead of API response. Tunnel may be invalid.",
                        )
                    return ConnectionResult(
                        ok=False,
                        url=url,
                        latency_ms=elapsed_ms,
                        status_code=resp.status_code,
                        error_message=f"Expected JSON response but received {content_type}.",
                    )

                health_data = resp.json()
                health = ServerHealth.from_dict(health_data)

                # Fetch status to enrich connection info if possible
                server_status = None
                try:
                    status_resp = self.session.get(f"{url}/status", timeout=self.timeout)
                    if status_resp.status_code == 200:
                        server_status = ServerStatus.from_dict(status_resp.json())
                except Exception:
                    pass

                return ConnectionResult(
                    ok=True,
                    url=url,
                    latency_ms=round(elapsed_ms, 1),
                    status_code=resp.status_code,
                    health=health,
                    status=server_status,
                )

            elif resp.status_code in {502, 503, 504}:
                return ConnectionResult(
                    ok=False,
                    url=url,
                    latency_ms=elapsed_ms,
                    status_code=resp.status_code,
                    error_message=(
                        f"Bad Gateway ({resp.status_code}). The ngrok tunnel is reachable, "
                        "but the OptiCore Python/FastAPI server is not responding."
                    ),
                )
            elif resp.status_code == 404:
                return ConnectionResult(
                    ok=False,
                    url=url,
                    latency_ms=elapsed_ms,
                    status_code=resp.status_code,
                    error_message="HTTP 404 Not Found at /health. Verify this is an OptiCore server.",
                )
            else:
                return ConnectionResult(
                    ok=False,
                    url=url,
                    latency_ms=elapsed_ms,
                    status_code=resp.status_code,
                    error_message=f"HTTP {resp.status_code}: {resp.reason}",
                )

        except Timeout:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectionResult(
                ok=False,
                url=url,
                latency_ms=elapsed_ms,
                error_message=f"Connection timed out after {self.timeout}s. Check your connection or tunnel.",
            )
        except ConnectionError as ce:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            err_str = str(ce)
            if "getaddrinfo failed" in err_str or "NameResolutionError" in err_str:
                msg = "DNS resolution failed. Please check that the URL or ngrok subdomain is correct."
            elif "Connection refused" in err_str:
                msg = "Connection refused. The server is not running on the specified host/port."
            else:
                msg = f"Network connection failed: {err_str[:120]}"
            return ConnectionResult(
                ok=False,
                url=url,
                latency_ms=elapsed_ms,
                error_message=msg,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectionResult(
                ok=False,
                url=url,
                latency_ms=elapsed_ms,
                error_message=f"Unexpected error: {str(exc)}",
            )
    def _translate_error(self, exc: Exception, endpoint: str) -> OptiCoreAPIError:
        """Translates low-level networking exceptions into user-friendly diagnostics."""
        err_str = str(exc)
        if isinstance(exc, HTTPError) and hasattr(exc, "response") and exc.response is not None:
            status = exc.response.status_code
            if status in {502, 503, 504}:
                msg = (
                    f"Bad Gateway ({status}) from ngrok tunnel. "
                    "The public tunnel is reachable, but the OptiCore FastAPI backend on Kaggle or your GPU server "
                    "is not running, restarting, or has stopped. Check Cell 5 in the notebook."
                )
            elif status == 404:
                msg = (
                    f"HTTP 404 Not Found at {self.base_url}{endpoint}. "
                    "Verify that the target URL is a valid OptiCore vision server instance."
                )
            else:
                msg = f"HTTP {status} {exc.response.reason} for {endpoint}: {err_str[:120]}"
            return OptiCoreAPIError(msg, exc)

        if isinstance(exc, Timeout):
            return OptiCoreAPIError(
                f"Request to {self.base_url}{endpoint} timed out after {self.timeout}s. "
                "Check that the server is online and your internet connection is active.",
                exc,
            )

        if isinstance(exc, ConnectionError):
            if "getaddrinfo failed" in err_str or "NameResolutionError" in err_str:
                return OptiCoreAPIError(
                    f"DNS resolution failed for {self.base_url}. "
                    "The ngrok tunnel URL may have expired, or there is a typo in the hostname.",
                    exc,
                )
            if "Connection refused" in err_str:
                return OptiCoreAPIError(
                    f"Connection refused by {self.base_url}. "
                    "The OptiCore server is not running on that address/port.",
                    exc,
                )
            return OptiCoreAPIError(f"Network connection failed: {err_str[:120]}", exc)

        return OptiCoreAPIError(f"OptiCore request failed: {err_str}", exc)

    def get_health(self) -> ServerHealth:
        """Fetches /health from the server."""
        try:
            resp = self.session.get(self._url("/health"), timeout=self.timeout)
            resp.raise_for_status()
            return ServerHealth.from_dict(resp.json())
        except Exception as e:
            raise self._translate_error(e, "/health") from e

    def get_status(self) -> ServerStatus:
        """Fetches /status from the server."""
        try:
            resp = self.session.get(self._url("/status"), timeout=self.timeout)
            resp.raise_for_status()
            return ServerStatus.from_dict(resp.json())
        except Exception as e:
            raise self._translate_error(e, "/status") from e

    def get_metrics(self) -> ServerMetrics:
        """Fetches /metrics from the server."""
        try:
            resp = self.session.get(self._url("/metrics"), timeout=self.timeout)
            resp.raise_for_status()
            return ServerMetrics.from_dict(resp.json())
        except Exception as e:
            raise self._translate_error(e, "/metrics") from e

    def get_events(self, limit: int = 20) -> List[DetectionEvent]:
        """Fetches recent detection events from /events?limit=N."""
        clamped_limit = max(1, min(100, int(limit)))
        try:
            resp = self.session.get(
                self._url("/events"),
                params={"limit": clamped_limit},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_events = data.get("events", [])
            return [DetectionEvent.from_dict(e) for e in raw_events]
        except Exception as e:
            raise self._translate_error(e, "/events") from e
