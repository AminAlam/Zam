from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
from re import match
import os
import base64
from PIL import Image, ImageDraw

def get_driver(custom_options=None, driver_path=None, gui=False):
    chrome_options = Options()
    if gui is False:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--test-type")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=768,2000")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36")

    if isinstance(custom_options, list) and len(custom_options) > 0:
        for option in custom_options:
            chrome_options.add_argument(option)

    chrome_options.add_experimental_option(
        'excludeSwitches', ['enable-logging'])

    # CHROME_DRIVER environment variable : priority 1
    if os.environ.get('CHROME_DRIVER') is not None:
        try:
            driver = webdriver.Chrome(service=Service(executable_path=os.environ.get('CHROME_DRIVER')), options=chrome_options)
            return driver
        except Exception as e:
            print(e)
            pass

    # driver_path argument : priority 2
    if driver_path is None: driver_path = get_chromedriver_default_path()
    if os.path.exists(driver_path):
        try:
            driver = webdriver.Chrome(service=Service(executable_path=driver_path), options=chrome_options)
            return driver
        except Exception as e:
            print(e)
            pass
    
    # webdriver-manager : priority 3
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        return driver
    except Exception as e:
        print(e)
        pass

    return None

def is_valid_tweet_url(url):
    result = match(
        "^https?:\/\/([A-Za-z0-9.]+)?twitter\.com\/(?:#!\/)?(\w+)\/status(es)?\/(\d+)", url)
    if result is not None:
        return result[0]
    return False


def get_tweet_file_name(url):
    result = match(
        "^https?:\/\/([A-Za-z0-9.]+)?twitter\.com\/(?:#!\/)?(\w+)\/status(es)?\/(\d+)", url)
    return f"@{result[2]}_{result[4]}_tweetcapture.png"

def get_tweet_base_url(url):
    result = match(
        "^https?:\/\/([A-Za-z0-9.]+)?twitter\.com\/(?:#!\/)?(\w+)\/status(es)?\/(\d+)", url)
    return f"/{result[2].lower()}/status/{result[4].lower()}"


def get_chromedriver_default_path():
    chrome_driver_env = os.getenv('CHROME_DRIVER')
    if chrome_driver_env is not None:
        return chrome_driver_env
    elif os.name == "nt":
        return "C:/bin/chromedriver.exe"
    else:
        return '/usr/local/bin/chromedriver'

def image_base64(filename): 
    if os.path.exists(filename):
        with open(filename, "rb") as image_file:
            encoded_string = "data:image/png;base64," + base64.b64encode(image_file.read()).decode('ascii')
            return encoded_string
    return ""



def add_corners(im, rad):
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im