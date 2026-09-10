import time
from blob import download, upload_status
from PIL import Image
from dotenv import load_dotenv
from display.display import DisplayHelper
from pisugar import schedule_next_wake, get_battery_percent, get_battery_charging
from datetime import datetime, timezone
import os

retry = 3
durationInSeconds = 60
WAKE_INTERVAL_HOURS = 1

# Collected alongside the usual stdout output and published as part of
# this run's status blob, so what happened on a given wake cycle can be
# checked remotely (e.g. via `az storage blob download`) without needing
# to SSH into the Pi.
log_lines = []


def log(message) -> None:
    print(message)
    log_lines.append(str(message))


while True:
    try:
        load_dotenv()

        download()

        helper = DisplayHelper(1304, 984)

        black = Image.open('black-b.png')
        red = Image.open('red-b.png')

        helper.update(black, red)

        helper.sleep()

        log("Display updated successfully")
        break
    except Exception as e:
        log(f"Error: {e}")
        retry -= 1
        if retry == 0:
            break
        time.sleep(durationInSeconds)
        durationInSeconds *= 2

# Re-arm the PiSugar's RTC wakeup alarm *before* shutting down, regardless
# of whether the refresh above succeeded -- if this fails, don't shut down:
# a Pi with no alarm armed would sleep forever with no way to wake itself.
next_wake = None
try:
    next_wake = schedule_next_wake(hours=WAKE_INTERVAL_HOURS)
    log(f"Next wake scheduled for {next_wake.isoformat()}")
except Exception as e:
    log(f"WARNING: failed to schedule next wake, staying awake: {e}")

# Report status (battery + this run's log) to blob storage regardless of
# whether scheduling succeeded above -- this is the only way to see what
# went wrong on a run that couldn't even arm the next wakeup.
# get_battery_percent()/get_battery_charging() never raise -- they return
# a -1.0/None sentinel on failure instead -- so a bad reading is reported
# as "unknown" rather than blocking this whole block.
try:
    battery_percent = get_battery_percent()
    status = {
        "battery_percent": round(battery_percent, 1) if battery_percent >= 0 else None,
        "charging": get_battery_charging(),
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "next_wake": next_wake.isoformat() if next_wake else None,
        "log": log_lines,
    }
    upload_status(status)
    print(f"Reported status: battery={status['battery_percent']} charging={status['charging']}")
except Exception as e:
    print(f"WARNING: failed to report status: {e}")

if next_wake is not None:
    os.system("sudo shutdown -h now")

