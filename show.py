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

while True:
    try:
        load_dotenv()

        download()

        helper = DisplayHelper(1304, 984)

        black = Image.open('black-b.png')
        red = Image.open('red-b.png')

        helper.update(black, red)

        helper.sleep()

        break
    except Exception as e:
        print(f"Error: {e}")
        retry -= 1
        if retry == 0:
            break
        time.sleep(durationInSeconds)
        durationInSeconds *= 2

# Re-arm the PiSugar's RTC wakeup alarm *before* shutting down, regardless
# of whether the refresh above succeeded -- if this fails, don't shut down:
# a Pi with no alarm armed would sleep forever with no way to wake itself.
# Re-arm the PiSugar's RTC wakeup alarm *before* shutting down, regardless
# of whether the refresh above succeeded -- if this fails, don't shut down:
# a Pi with no alarm armed would sleep forever with no way to wake itself.
try:
    next_wake = schedule_next_wake(hours=WAKE_INTERVAL_HOURS)
    print(f"Next wake scheduled for {next_wake.isoformat()}")

    # Report battery status to blob storage so it can be checked remotely.
    # Non-fatal: a failure here shouldn't block shutdown/rescheduling.
    try:
        status = {
            "battery_percent": round(get_battery_percent(), 1),
            "charging": get_battery_charging(),
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "next_wake": next_wake.isoformat(),
        }
        upload_status(status)
        print(f"Reported status: {status}")
    except Exception as e:
        print(f"WARNING: failed to report battery status: {e}")

    os.system("sudo shutdown -h now")
except Exception as e:
    print(f"WARNING: failed to schedule next wake, staying awake: {e}")
