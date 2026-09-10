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
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional

PISUGAR_HOST = "127.0.0.1"
PISUGAR_PORT = 8423
SOCKET_TIMEOUT_SECONDS = 5


def _send_command(command: str) -> str:
    with socket.create_connection((PISUGAR_HOST, PISUGAR_PORT), timeout=SOCKET_TIMEOUT_SECONDS) as sock:
        sock.sendall((command + "\n").encode("utf-8"))
        sock.settimeout(SOCKET_TIMEOUT_SECONDS)
        buffer = b""
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                if b"\n" in buffer:
                    # Got at least one full line -- give any other
                    # already-in-flight lines a brief moment to arrive too,
                    # then stop waiting (avoids blocking for the full
                    # timeout on the common case).
                    sock.settimeout(0.2)
        except socket.timeout:
            pass
    return buffer.decode("utf-8", errors="replace")


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


def _get_value(key: str) -> Optional[str]:
    """Send `get <key>` to pisugar-server via netcat and return the raw
    response text, or None if the command failed for any reason.

    Uses the same `echo "get <key>" | nc -q 0 127.0.0.1 8423` pattern as
    the original MagInkCal project's power.py (rather than a hand-rolled
    socket read) -- letting `nc` handle the TCP send/receive/close timing
    has proven more reliable against real PiSugar firmware quirks than
    reading raw socket bytes ourselves.
    """
    try:
        echo = subprocess.Popen(("echo", f"get {key}"), stdout=subprocess.PIPE)
        result = subprocess.check_output(
            ("nc", "-q", "0", PISUGAR_HOST, str(PISUGAR_PORT)),
            stdin=echo.stdout,
            timeout=SOCKET_TIMEOUT_SECONDS,
        )
        echo.wait()
        return result.decode("utf-8", errors="replace").rstrip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None


def get_battery_percent() -> float:
    """Return the current battery charge level as a percentage (0-100),
    or -1.0 if it couldn't be read (e.g. a transient PiSugar firmware/I2C
    hiccup) -- never raises, so a bad reading never blocks the rest of
    the wake cycle."""
    raw = _get_value("battery")
    if raw is None:
        return -1.0
    try:
        # Response looks like "battery: 87.65" -- take the last
        # whitespace-separated token rather than splitting on ":", to
        # tolerate any interleaved lines/extra whitespace.
        return float(raw.split()[-1])
    except (ValueError, IndexError):
        return -1.0


def get_battery_charging() -> Optional[bool]:
    """Return whether the PiSugar is currently charging, or None if it
    couldn't be determined."""
    raw = _get_value("battery_charging")
    if raw is None:
        return None
    try:
        token = raw.split()[-1].strip().lower()
    except IndexError:
        return None
    if token in ("true", "false"):
        return token == "true"
    return None
