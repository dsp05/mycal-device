import time
from blob import download
from PIL import Image
from dotenv import load_dotenv
from display.display import DisplayHelper
import os

retry = 3
durationInSeconds = 60

while True:
    try:
        load_dotenv()

        download()

        helper = DisplayHelper(1304, 984)

        black = Image.open('black-b.png')
        red = Image.open('red-b.png')

        helper.update(black, red)

        helper.sleep()
    except Exception as e:
        print(f"Error: {e}")
        retry -= 1
        if retry == 0:
            break
        time.sleep(durationInSeconds)
        durationInSeconds *= 2

os.system("sudo shutdown -h now")