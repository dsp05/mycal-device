from blob import download
from PIL import Image
from dotenv import load_dotenv
from display.display import DisplayHelper
import os

load_dotenv()

download()

helper = DisplayHelper(1304, 984)

black = Image.open('black-b.png')
red = Image.open('red-b.png')

helper.update(black, red)

helper.sleep()

os.system("sudo shutdown -h now")