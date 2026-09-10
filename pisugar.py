"""Talks to the local pisugar-server over its plain-text TCP API
(default port 8423, no auth required for local/loopback connections)
to manage the PiSugar's single hardware RTC wakeup alarm.

The RTC can only store one alarm at a time, and its "repeat" field is a
weekday bitmask (not an hourly interval) -- so there's no native way to
say "wake me up every hour". Instead, every time the Pi wakes up, it
re-arms a fresh one-shot alarm for `now + interval` right before shutting
down again, creating a self-perpetuating wake loop at whatever interval
you choose.
"""
import socket
from datetime import datetime, timedelta, timezone

PISUGAR_HOST = "127.0.0.1"
PISUGAR_PORT = 8423
SOCKET_TIMEOUT_SECONDS = 5


def _send_command(command: str) -> str:
    with socket.create_connection((PISUGAR_HOST, PISUGAR_PORT), timeout=SOCKET_TIMEOUT_SECONDS) as sock:
        sock.sendall((command + "\n").encode("utf-8"))
        sock.settimeout(SOCKET_TIMEOUT_SECONDS)
        response = sock.recv(4096).decode("utf-8", errors="replace")
    return response.strip()


def schedule_next_wake(hours: float = 1.0) -> datetime:
    """Arm a one-shot RTC wakeup alarm `hours` from now (UTC) and return
    that wakeup time. Raises on any communication failure with
    pisugar-server so the caller can decide how to handle it (the Pi
    should NOT be shut down if we failed to arm the next wakeup, or it
    may never wake up again)."""
    next_wake = datetime.now(timezone.utc) + timedelta(hours=hours)
    iso_time = next_wake.isoformat(timespec="seconds")

    # repeat=0 -- single-shot alarm, no weekday repeat.
    response = _send_command(f"rtc_alarm_set {iso_time} 0")
    if "error" in response.lower() or "fail" in response.lower():
        raise RuntimeError(f"pisugar-server rejected rtc_alarm_set: {response}")

    return next_wake


def _get_value(key: str) -> str:
    """Send a `get <key>` command and return the value portion of the
    "key: value" response pisugar-server sends back."""
    response = _send_command(f"get {key}")
    if "error" in response.lower() or "fail" in response.lower():
        raise RuntimeError(f"pisugar-server rejected 'get {key}': {response}")
    # Response looks like "battery: 87.65" -- split on the first colon only,
    # since some values (e.g. rtc_time) contain colons themselves.
    _, _, value = response.partition(":")
    return value.strip()


def get_battery_percent() -> float:
    """Return the current battery charge level as a percentage (0-100)."""
    return float(_get_value("battery"))


def get_battery_charging() -> bool:
    """Return True if the PiSugar is currently charging (e.g. on USB power)."""
    return _get_value("battery_charging").lower() == "true"
