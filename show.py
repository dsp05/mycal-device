from blob import download
import display.epd12in48b_V2 as eink
from PIL import Image
from dotenv import load_dotenv


load_dotenv()

download()

black = Image.open('black-b.png')
red = Image.open('red-b.png')

epd = eink.EPD()
height = 984
width = 1304

white = Image.new('1', (width, height), 'white')
black = Image.new('1', (width, height), 'black')

epd.display(black, white)
epd.display(white, black)
epd.display(white, white)

epd.display(black, red)

epd.EPD_Sleep()