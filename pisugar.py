"""Talks to the local pisugar-server over its plain-text TCP API
(default port 8423, no auth required for local/loopback connections)
to manage the PiSugar's single hardware RTC wakeup alarm.

The RTC can only store one alarm at a time, and its "repeat" field is a
weekday bitmask (not an hourly interval) -- so there's no native way to
say "wake me up every N hours, but only during certain hours of the
day". Instead, every time the Pi wakes up, it works out the next
qualifying slot on a fixed daily schedule and re-arms a fresh one-shot
alarm for that time right before shutting down again, creating a
self-perpetuating wake loop.
"""
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

PISUGAR_HOST = "127.0.0.1"
PISUGAR_PORT = 8423
SOCKET_TIMEOUT_SECONDS = 5

# Wake schedule: twice a day, at :10 past 5 AM and 5 PM.
_WAKE_TZ = ZoneInfo("America/Chicago")
_WAKE_HOURS = (5, 17)
_WAKE_MINUTE = 10


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


def _next_scheduled_wake(after: datetime) -> datetime:
    """Return the next wake time (UTC, tz-aware) strictly after `after`,
    following the fixed daytime-only schedule (see `_WAKE_HOURS` /
    `_WAKE_MINUTE` above), expressed in America/Chicago local time."""
    local_after = after.astimezone(_WAKE_TZ)
    for day_offset in range(0, 3):  # plenty of headroom, only ever need 0 or 1
        candidate_date = (local_after + timedelta(days=day_offset)).date()
        for hour in _WAKE_HOURS:
            candidate = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                hour,
                _WAKE_MINUTE,
                tzinfo=_WAKE_TZ,
            )
            if candidate > local_after:
                return candidate.astimezone(timezone.utc)
    raise RuntimeError("could not compute next scheduled wake time")


def schedule_next_wake() -> datetime:
    """Arm a one-shot RTC wakeup alarm for the next qualifying slot on the
    fixed daytime schedule and return that wakeup time (UTC). Raises on
    any communication failure with pisugar-server so the caller can
    decide how to handle it (the Pi should NOT be shut down if we failed
    to arm the next wakeup, or it may never wake up again)."""
    next_wake = _next_scheduled_wake(datetime.now(timezone.utc))
    # pisugar-server expects milliseconds in the timestamp (it echoes
    # alarm/rtc times back as e.g. "...T17:10:00.000-05:00") -- without
    # them it silently fails to parse the date portion and falls back to
    # 2000-01-01, while somehow still picking up the correct time-of-day.
    iso_time = next_wake.isoformat(timespec="milliseconds")

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
