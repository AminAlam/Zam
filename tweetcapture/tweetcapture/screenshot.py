from asyncio import sleep
import os
import time as sync_time
import random
import logging
from tweetcapture.utils.webdriver import get_driver

# Configure logger for this module
logger = logging.getLogger(__name__)
from tweetcapture.utils.utils import is_valid_tweet_url, get_tweet_file_name, add_corners
from tweetcapture.utils.video import (
    VideoRecordingManager, 
    get_element_screen_position, 
    check_ffmpeg_available,
    compress_video_for_telegram,
    _ffprobe_basic_stats
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from os import remove, environ
from os.path import exists

# #region agent log
import json as _json
def _ndjson_log(hypothesisId: str, location: str, message: str, data: dict | None = None, runId: str = "pre-fix") -> None:
    """
    Debug-mode NDJSON logger (best-effort). Requires ZAM_DEBUG_LOG_PATH to be set.
    """
    path = os.environ.get("ZAM_DEBUG_LOG_PATH")
    if not path:
        return
    payload = {
        "sessionId": "debug-session",
        "runId": runId,
        "hypothesisId": hypothesisId,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(sync_time.time() * 1000),
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion

class TweetCapture:
    driver = None
    driver_path = None
    gui = False
    mode = 3
    night_mode = 0
    wait_time = 5
    chrome_opts = []
    lang = None
    test = False
    show_parent_tweets = False
    parent_tweets_limit = 0
    show_mentions_count = 0
    overwrite = False
    radius = 15
    scale = 1.0
    cookies = None

    hide_link_previews = False
    hide_photos = False
    hide_videos = False
    hide_gifs = False
    hide_quotes = False

    # Video capture settings
    capture_videos = True
    video_output_dir = "/app/videos"  # Maps to Docker media folder
    x_display = ":99"
    video_max_duration = 120  # Maximum video duration in seconds
    video_with_audio = True

    __web = 1

    def __init__(self, mode=3, night_mode=0, test=False, show_parent_tweets=False, parent_tweets_limit=0, show_mentions_count=0, overwrite=False, radius=15, scale=1.0):
        self.set_night_mode(night_mode)
        self.set_mode(mode)
        self.set_scale(scale)
        self.test = test
        self.show_parent_tweets = show_parent_tweets
        self.parent_tweets_limit = parent_tweets_limit
        self.show_mentions_count = show_mentions_count
        self.overwrite = overwrite
        self.radius = radius
        if environ.get('AUTH_TOKEN') != None:
            self.cookies = [{'name': 'auth_token', 'value': environ.get('AUTH_TOKEN')}]

    async def screenshot(self, url, path=None, mode=None, night_mode=None, show_parent_tweets=None, parent_tweets_limit=None, show_mentions_count=None, overwrite=None, radius=None, scale=None):
        if is_valid_tweet_url(url) is False:
            raise Exception("Invalid tweet url")

        if not isinstance(path, str) or len(path) == 0:
            path = get_tweet_file_name(url)

        if exists(path):
            if (self.overwrite if overwrite is None else overwrite) is False:
                raise Exception("File already exists")
            else:
                remove(path)

        url = is_valid_tweet_url(url)
        if self.lang:
            url += "?lang=" + self.lang

        radius = self.radius if radius is None else radius
        scale = self.scale if scale is None else scale
        driver = await get_driver(self.chrome_opts, self.driver_path, self.gui, scale)
        if driver is None:
            raise Exception("webdriver cannot be initialized")
        try:
            driver.get(url)
            driver.add_cookie(
                {"name": "night_mode", "value": str(self.night_mode if night_mode is None else night_mode)})
            if self.cookies:
                for cookie in self.cookies:
                    driver.add_cookie(cookie)
            driver.get(url)
            self.__init_scale_css(driver)
            await sleep(self.wait_time)
           
            self.__hide_global_items(driver)
            driver.execute_script("!!document.activeElement ? document.activeElement.blur() : 0")

            if self.test is True: 
                driver.save_screenshot(f"web{self.__web}.png")
                self.__web += 1
            await sleep(2.0)
            elements, main = self.__get_tweets(driver, self.show_parent_tweets if show_parent_tweets is None else show_parent_tweets, self.parent_tweets_limit if parent_tweets_limit is None else parent_tweets_limit, self.show_mentions_count if show_mentions_count is None else show_mentions_count)
            if len(elements) == 0:
                raise Exception("Tweets not found")
            else:
                for i, element in enumerate(elements):
                    if i == main:
                        self.__code_main_footer_items_new(element, self.mode if mode is None else mode)
                    else:
                        try:
                            driver.execute_script(self.__code_footer_items(self.mode if mode is None else mode), element.find_element(By.XPATH, ".//div[@role = 'group']"), element.find_element(By.CSS_SELECTOR, ".r-1hdv0qi:first-of-type"))
                        except:
                            pass
                    
                    self.__hide_media(element, self.hide_link_previews, self.hide_photos, self.hide_videos, self.hide_gifs, self.hide_quotes)
                    if i == len(elements)-1:
                        self.__margin_tweet(self.mode if mode is None else mode, element)
                        
            if len(elements) == 1:
                driver.execute_script("window.scrollTo(0, 0);")
                x, y, width, height = driver.execute_script("var rect = arguments[0].getBoundingClientRect(); return [rect.x, rect.y, rect.width, rect.height];", elements[0])
                await sleep(0.1)
                if scale != 1.0:
                    driver.save_screenshot(path)
                else:
                    elements[0].screenshot(path)
                if radius > 0 or scale != 1.0:
                    im = Image.open(path)
                    if scale != 1.0:
                        im = im.crop((x, y, x+width, y+height))
                    if radius > 0:
                        im = add_corners(im, radius)
                    im.save(path)
                    im.close()
            else:
                filenames = []
                for element in elements:
                    filename = "tmp_%s_tweetcapture.png" % element.id
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    x, y, width, height = driver.execute_script("var rect = arguments[0].getBoundingClientRect(); return [rect.x, rect.y, rect.width, rect.height];", element)
                    await sleep(0.1)
                    if scale != 1.0:
                        driver.save_screenshot(filename)
                        im = Image.open(filename)
                        im = im.crop((x, y, x+width, y+height))
                        im.save(filename)
                        im.close()
                    else:
                        element.screenshot(filename)
                    filenames.append(filename)
                width = 0
                height = 0
                images = []
                for filename in filenames:
                    im = Image.open(filename)
                    if width == 0:
                        width = im.size[0]
                    height += im.size[1]
                    images.append(im)
                c = (255,255,255)
                if self.night_mode == 1:
                    c = (21,32,43)
                elif self.night_mode == 2:
                    c = (0,0,0)
                new_im = Image.new('RGB', (width,height), c)
                y = 0
                for im in images:
                    new_im.paste(im, (0,y))
                    y += im.size[1]
                    im.close()
                    remove(im.filename)
                
                if radius > 0:
                    new_im = add_corners(new_im, self.radius)
                new_im.save(path, quality=100)
                new_im.close()
  
            driver.quit()
        except Exception as err:
            driver.quit()
            raise err
        return path
        
    def set_wait_time(self, time):
        if 1.0 <= time <= 10.0: 
            self.wait_time = time

    def get_night_mode(self):
        return self.night_mode

    def set_night_mode(self, night_mode):
        if 0 <= night_mode <= 2:
            self.night_mode = night_mode

    def set_mode(self, mode):
        self.mode = mode

    def add_chrome_argument(self, option):
        self.chrome_opts.append(option)

    def set_lang(self, lang):
        self.lang = lang

    def set_chromedriver_path(self, path):
        self.driver_path = path
    
    def set_cookies(self, cookies):
        if isinstance(cookies, list):
            self.cookies = cookies

    def set_scale(self, scale):
        if isinstance(scale, float):
            if scale > 0.0 and scale <= 14.0:
                self.scale = scale

    def __init_scale_css(self, driver):
        driver.execute_script("""
            var style = document.createElement('style');
            style.innerHTML = ".r-1ye8kvj { max-width: 40rem !important; } .r-rthrr5 { width: 100% !important; } body { scale: """+str(self.scale)+""" !important; transform-origin: 0 0 !important; }";
            document.head.appendChild(style);
        """)

    def __hide_global_items(self, driver):
        HIDE_ITEMS_XPATH = [
            '/html/body/div/div/div/div[1]',
            '/html/body/div/div/div/div[2]/header', '/html/body/div/div/div/div[2]/main/div/div/div/div/div/div[1]',
            ".//ancestor::div[@data-testid = 'tweetButtonInline']/../../../../../../../../../../.."
        ]
        for item in HIDE_ITEMS_XPATH:
            try:
                element = driver.find_element(By.XPATH, item)
                driver.execute_script("""
                arguments[0].style.display="none";
                """, element)
            except:
                continue

    def __margin_tweet(self, mode, base):
        if mode == 0:
            try:
                base.parent.execute_script(
                    """arguments[0].childNodes[0].style.paddingBottom = '35px';""", base.find_element(By.TAG_NAME, "article"))
            except:
                pass

    def __code_footer_items(self, mode):
        if mode == 0:
            return """
            arguments[0].style.display="none";
            arguments[1].style.display="none";
            """
        else:
            return """
            arguments[1].style.display="none";
            """
    
    def hide_all_media(self):
        self.hide_link_previews = True
        self.hide_photos = True
        self.hide_videos = True
        self.hide_gifs = True
        self.hide_quotes = True  

    def hide_media(self, link_previews=None, photos=None, videos=None, gifs=None, quotes=None):
        if link_previews is not None: self.hide_link_previews = link_previews
        if photos is not None: self.hide_photos = photos
        if videos is not None: self.hide_videos = videos
        if gifs is not None: self.hide_gifs = gifs
        if quotes is not None: self.hide_quotes = quotes

    def __hide_media(self, element, link_previews, photo, video, gif, quote):
        LINKPREVIEW_XPATH = ".//ancestor::div[@data-testid = 'card.layoutLarge.media']/ancestor::div[contains(@id, 'id__')][1]"
        MEDIA_XPATH = ".//ancestor::div[@data-testid = 'tweetPhoto']/ancestor::div[contains(@id, 'id__')]/div[1]"
        QUOTE_XPATH = ".//ancestor::div[contains(@class, 'r-desppf')]/ancestor::div[contains(@id, 'id__')][1]"
        media_elements = element.find_elements(By.XPATH, MEDIA_XPATH)
        if link_previews is True:
            link_preview_elements = element.find_elements(By.XPATH, LINKPREVIEW_XPATH)
            for link_preview_element in link_preview_elements:
                element.parent.execute_script("""
                arguments[0].style.display="none";
                """, link_preview_element)
        if quote is True:
            quote_elements = element.find_elements(By.XPATH, QUOTE_XPATH)
            for quote_element in quote_elements:
                element.parent.execute_script("""
                arguments[0].style.display="none";
                """, quote_element)
        if len(media_elements) > 0:
            for el in media_elements:
                if video is True:
                    sel = el.find_elements(By.XPATH, ".//video[contains(@src, 'blob:')]")
                    if len(sel) > 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue
                    sel = el.find_elements(By.XPATH, ".//source[contains(@src, 'blob:')]")
                    if len(sel) > 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue
                if gif is True:
                    sel = el.find_elements(By.XPATH, ".//video[not(contains(@src, 'blob:'))]")
                    if len(sel) > 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue
                if gif is True:
                    sel = el.find_elements(By.XPATH, ".//video[not(contains(@src, 'blob:'))]")
                    if len(sel) > 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue
                if photo is True:
                    sel = el.find_elements(By.XPATH, ".//div[contains(@data-testid, 'videoPlayer')]")
                    if len(sel) == 0:
                        element.parent.execute_script("""
                        arguments[0].style.display="none";
                        """, el)
                        continue


    def __code_main_footer_items_new(self, element, mode):
        XPATHS = [
            ".//ancestor::time/ancestor::a[contains(@aria-describedby, 'id__')]", # 0 time
            ".//div[@role = 'group'][contains(@id, 'id__')]", # 1 action buttons
            ".//div[@role = 'group'][not(contains(@id, 'id__'))]", # 2 tweet rt/like/bookmark counts
            ".//div[contains(@data-testid, 'caret')]", # 3 tweet caret button
            "((//ancestor::span)/..)[contains(@role, 'button')]", # 4 translate button
            ".//div[contains(@data-testid, 'caret')]/../../../../..", # 5 tweet caret button / subscribe-follow button
            ".//ancestor::time/../../..//span[contains(text(), '·')]/..", # 6 separator between time and views
            ".//ancestor::time/../../../div[3]", # 7 views
            ".//ancestor::time/../../../../..", # 8 time & views outer
            ".//ancestor::time/../../../../../..", # 9 time & views outer (with margin)
            ".//div[@role = 'group'][contains(@id, 'id__')]/../../../div[contains(@class, 'r-j5o65s')]", # 10 border line
        ]

        newInfoMode = True
        try:
            if len(element.find_elements(By.XPATH, ".//div[@role = 'separator']")) > 0:
                newInfoMode = False
        except:
            pass
        
        hides = []
        if mode == 0: # hide everything
            hides = [0,1,2,3,4,5,6,7,9]
            if newInfoMode is True: hides.append(10)
        elif mode == 1: # show tweet rt/likes
            hides = [0,3,4,5,6]
            if newInfoMode is False: hides.append(1)
        elif mode == 2: # show tweet rt/likes & timestasmp
            hides = [3,4,5]
            if newInfoMode is False: hides.append(1)
        elif mode == 3: # show everything
            hides = [3,4,5]
        elif mode == 4: # show timestamp
            hides = [1,2,3,4,5,6,7]

        viewsVisible = False
        try:
            if len(element.find_elements(By.XPATH, "((//ancestor::time)/..)[contains(@aria-describedby, 'id__')]/../../div")) > 1:
                viewsVisible = True
        except:
            pass

        # if time hidden and views not there, hide outer (to clear gaps)
        if (mode != 0) and (0 in hides) and (viewsVisible is False):
            hides.append(8)

        for i in hides:
            els = element.find_elements(By.XPATH, XPATHS[i])
            if len(els) > 0:
                for el in els:
                    element.parent.execute_script("""
                    arguments[0].style.display="none";
                    """, el)
        
        brdr = element.find_elements(By.XPATH, XPATHS[2])
        if len(brdr) == 1:
            element.parent.execute_script("""
            arguments[0].style.borderBottom="none";
            """, brdr[0])

    # Return: (elements, main_element_index)
    def __get_tweets(self, driver, show_parents, parent_tweets_limit, show_mentions_count):
        els = driver.find_elements(By.XPATH, "(//ancestor::article)/..")
        elements = []
        for element in els:
            if len(element.find_elements(By.XPATH, ".//article[contains(@data-testid, 'tweet')]")) > 0:
                source = element.get_attribute("innerHTML")
                # sponsored tweet pass
                if source.find("M19.498 3h-15c-1.381 0-2.5 1.12-2.5 2.5v13c0 1.38") != -1 or source.find('css-1dbjc4n r-1s2bzr4" id="id__jrl5cg7nxl"') != -1:
                    continue
                elements.append(element)
        length = len(elements)
        if length > 0:
            if length == 1:
                return elements, 0
            else:
                main_element = -1
                for i, element in enumerate(elements):
                    main_tweet_details = element.find_elements(By.XPATH, ".//div[contains(@class, 'r-1471scf')]")
                    if len(main_tweet_details) == 1:
                        main_element = i
                        break
                if main_element == -1:
                    return [], -1
                else:
                    r = main_element+1
                    r2 = r+show_mentions_count
                    s1 = 0
                    if parent_tweets_limit > 0 and len(elements[s1:main_element]) > parent_tweets_limit:
                        s1 = main_element - parent_tweets_limit
                    if show_parents and show_mentions_count > 0:
                        if len(elements[r:]) > show_mentions_count:      
                            return (elements[s1:r] + elements[r:r2]), main_element
                        return elements[s1:], main_element
                    elif show_parents:
                        if main_element == 0:
                            return elements[0:1], 0
                        else:
                            return elements[s1:r], main_element
                    elif show_mentions_count > 0:
                        if len(elements[r:]) > show_mentions_count:
                            return elements[main_element:1] + elements[r:r2], 0
                        return elements[main_element:], 0
                    else:
                        return elements[main_element:r], 0
        return [], -1
    
    def set_gui(self, gui):
        self.gui = True if gui is True else False

    # ==================== Video Capture Methods ====================

    def enable_video_capture(self, output_dir: str, x_display: str = ":99", 
                             max_duration: int = 120, with_audio: bool = True):
        """
        Enable video capture for tweets containing videos.
        
        Args:
            output_dir: Directory to save captured videos
            x_display: X display for screen capture (Linux only)
            max_duration: Maximum video duration in seconds
            with_audio: Whether to capture audio
        """
        self.capture_videos = True
        self.video_output_dir = output_dir
        self.x_display = x_display
        self.video_max_duration = max_duration
        self.video_with_audio = with_audio
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def disable_video_capture(self):
        """Disable video capture."""
        self.capture_videos = False

    def detect_videos(self, element) -> int:
        """
        Detect the number of videos in a tweet element.
        
        Args:
            element: Selenium WebElement representing the tweet
            
        Returns:
            Number of videos found
        """
        # Look for video players in the tweet
        video_players = element.find_elements(By.CSS_SELECTOR, '[data-testid="videoPlayer"]')
        logger.info(f"Found {len(video_players)} video players")
        return len(video_players)

    def get_video_elements(self, element) -> list:
        """
        Get all video player elements in a tweet.
        
        Args:
            element: Selenium WebElement representing the tweet
            
        Returns:
            List of video player WebElements
        """
        return element.find_elements(By.CSS_SELECTOR, '[data-testid="videoPlayer"]')

    def _get_video_duration_from_player(self, driver, video_player) -> float:
        """
        Try to extract video duration from the player element.
        
        Args:
            driver: Selenium WebDriver
            video_player: Video player WebElement
            
        Returns:
            Duration in seconds, or default if unable to determine
        """
        try:
            # Try to find the video element and get its duration
            video_element = video_player.find_element(By.TAG_NAME, 'video')
            duration = driver.execute_script("""
                var video = arguments[0];
                if (video.duration && !isNaN(video.duration) && isFinite(video.duration)) {
                    return video.duration;
                }
                return null;
            """, video_element)
            
            if duration:
                return min(float(duration), self.video_max_duration)
        except:
            pass
        
        # Try to find duration text in the player controls
        try:
            duration_elements = video_player.find_elements(By.CSS_SELECTOR, '[data-testid="progressBarTime"]')
            if duration_elements:
                # Usually the last one is total duration
                duration_text = duration_elements[-1].text
                return self._parse_duration_text(duration_text)
        except:
            pass
        
        # Default duration if we can't determine it
        return 30.0

    def _parse_duration_text(self, duration_text: str) -> float:
        """
        Parse duration text like "1:30" or "10:45" to seconds.
        
        Args:
            duration_text: Duration string in MM:SS or HH:MM:SS format
            
        Returns:
            Duration in seconds
        """
        try:
            parts = duration_text.strip().split(':')
            if len(parts) == 2:
                minutes, seconds = int(parts[0]), int(parts[1])
                return minutes * 60 + seconds
            elif len(parts) == 3:
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except:
            pass
        return 30.0  # Default

    def _click_video_play_button(self, driver, video_player) -> bool:
        """
        Click the play button on a video player.
        
        Args:
            driver: Selenium WebDriver
            video_player: Video player WebElement
            
        Returns:
            True if play button was clicked, False otherwise
        """
        try:
            # Try multiple selectors for the play button
            play_button_selectors = [
                '[data-testid="playButton"]',
                '[aria-label="Play"]',
                '[aria-label="Play video"]',
                'button[aria-label*="Play"]',
                '.PlayButton',
            ]
            
            for selector in play_button_selectors:
                try:
                    play_button = video_player.find_element(By.CSS_SELECTOR, selector)
                    if play_button.is_displayed():
                        play_button.click()
                        return True
                except NoSuchElementException:
                    continue
            
            # Try clicking the video player itself (some videos auto-play on click)
            video_player.click()
            return True
            
        except Exception as e:
            print(f"Could not click play button: {e}")
            return False

    def _wait_for_video_to_start(self, driver, video_player, timeout: int = 10) -> bool:
        """
        Wait for a video to start playing.
        
        Args:
            driver: Selenium WebDriver
            video_player: Video player WebElement
            timeout: Maximum seconds to wait
            
        Returns:
            True if video started playing, False otherwise
        """
        try:
            video_element = video_player.find_element(By.TAG_NAME, 'video')
            
            # Wait for the video to start playing
            for _ in range(timeout * 2):
                is_playing = driver.execute_script("""
                    var video = arguments[0];
                    return !video.paused && !video.ended && video.currentTime > 0;
                """, video_element)
                
                if is_playing:
                    return True
                sync_time.sleep(0.5)
            
            return False
        except:
            # If we can't find the video element, assume it might be playing
            sync_time.sleep(2)
            return True

    def _wait_for_video_to_end(self, driver, video_player, max_duration: float) -> None:
        """
        Wait for a video to finish playing or until max duration.
        
        Args:
            driver: Selenium WebDriver
            video_player: Video player WebElement
            max_duration: Maximum seconds to wait
        """
        start_time = sync_time.time()
        
        try:
            video_element = video_player.find_element(By.TAG_NAME, 'video')
            
            while (sync_time.time() - start_time) < max_duration:
                try:
                    # Only check for 'ended' to avoid stopping on buffer pauses
                    ended = driver.execute_script("""
                        var video = arguments[0];
                        return video.ended;
                    """, video_element)
                    
                    if ended:
                        # Add a 1.5s buffer to ensure we captured the very end
                        sync_time.sleep(1.5)
                        return
                except:
                    pass
                
                sync_time.sleep(0.5)
        except:
            # If we can't monitor the video, just wait for max duration
            sync_time.sleep(max_duration)

    def _capture_single_video(self, driver, tweet_element, video_player, 
                              video_index: int, tweet_id: str) -> str:
        """
        Capture a single video from a tweet.
        
        Args:
            driver: Selenium WebDriver
            tweet_element: The tweet element containing the video
            video_player: The video player element
            video_index: Index of this video (for filename)
            tweet_id: Tweet ID for filename
            
        Returns:
            Path to the captured video file, or None if capture failed
        """
        if not check_ffmpeg_available():
            print("FFmpeg is not available. Cannot capture video.")
            return None
        
        # Generate output filename
        random_suffix = random.randint(1, 1000000000)
        filename = f"{tweet_id}_video_{video_index}_{random_suffix}.mp4"
        output_path = os.path.join(self.video_output_dir, filename)
        
        try:
            # Match static screenshot logic: scroll PAGE to top
            driver.execute_script("window.scrollTo(0, 0);")
            sync_time.sleep(0.5)
            
            # Get the screen position of the TWEET element
            # In Kiosk mode with scrollTo(0,0), getBoundingClientRect is absolute screen position
            region = get_element_screen_position(driver, tweet_element, use_viewport_coords=True)
            
            # #region agent log
            _ndjson_log(
                hypothesisId="H_CROP_MATH",
                location="tweetcapture/screenshot.py:TweetCapture._capture_single_video",
                message="Initial region computed (match static screenshot logic)",
                data={"tweet_id": tweet_id, "video_index": video_index, "region_px": list(region)},
            )
            # #endregion
            
            # Get video duration
            duration = self._get_video_duration_from_player(driver, video_player)
            
            # Create recording manager
            recording_manager = VideoRecordingManager(
                output_dir=self.video_output_dir,
                display=self.x_display
            )
            
            # Start the recording session
            session = recording_manager.record_with_callback(
                region=region,
                filename=filename,
                with_audio=self.video_with_audio
            )
            
            # Start recording
            if not session.start():
                print("Failed to start video recording")
                return None
            
            # Small delay to ensure recording has started
            sync_time.sleep(0.3)
            
            # Click play button
            self._click_video_play_button(driver, video_player)
            
            # Wait for video to start
            self._wait_for_video_to_start(driver, video_player)

            # Re-check region in case of layout shifts
            region2 = get_element_screen_position(driver, tweet_element, use_viewport_coords=True)
            # #region agent log
            _ndjson_log(
                hypothesisId="H_CROP_MATH",
                location="tweetcapture/screenshot.py:TweetCapture._capture_single_video",
                message="Region after playback start (tweet element)",
                data={"tweet_id": tweet_id, "video_index": video_index, "region_px": list(region2)},
            )
            # #endregion
            
            # Wait for video to end (or max duration)
            self._wait_for_video_to_end(driver, video_player, duration)
            
            # Stop recording
            result_path = session.stop()
            
            if result_path and os.path.exists(result_path):
                # #region agent log
                stats = _ffprobe_basic_stats(result_path)
                _ndjson_log(
                    hypothesisId="H_STUTTER",
                    location="tweetcapture/screenshot.py:TweetCapture._capture_single_video",
                    message="ffprobe stats for recorded video",
                    data={"path": result_path, "ffprobe": stats},
                )
                # #endregion
                # Check if compression is needed for Telegram (50MB limit)
                file_size_mb = os.path.getsize(result_path) / (1024 * 1024)
                if file_size_mb > 50:
                    compressed_path = result_path.replace('.mp4', '_compressed.mp4')
                    compressed = compress_video_for_telegram(result_path, compressed_path)
                    if compressed and compressed != result_path:
                        # Remove original, keep compressed
                        os.remove(result_path)
                        return compressed
                
                return result_path
            
            return None
            
        except Exception as e:
            print(f"Error capturing video: {e}")
            return None

    async def screenshot_with_videos(self, url, screenshot_path=None, video_output_dir=None,
                                     mode=None, night_mode=None, show_parent_tweets=None,
                                     parent_tweets_limit=None, show_mentions_count=None,
                                     overwrite=None, radius=None, scale=None):
        """
        Capture a tweet screenshot and all embedded videos.
        
        Args:
            url: Tweet URL
            screenshot_path: Path for the screenshot
            video_output_dir: Directory to save videos (overrides instance setting)
            mode, night_mode, etc.: Same as screenshot() method
            
        Returns:
            dict with:
                - screenshot_path: Path to the screenshot
                - video_paths: List of paths to captured videos
                - has_videos: Boolean indicating if videos were found
        """
        # #region agent log
        print(f"[DEBUG] screenshot_with_videos called, url={url}, capture_videos={self.capture_videos}, video_output_dir={self.video_output_dir}")
        # #endregion
        if is_valid_tweet_url(url) is False:
            raise Exception("Invalid tweet url")

        if not isinstance(screenshot_path, str) or len(screenshot_path) == 0:
            screenshot_path = get_tweet_file_name(url)

        if exists(screenshot_path):
            if (self.overwrite if overwrite is None else overwrite) is False:
                raise Exception("File already exists")
            else:
                remove(screenshot_path)

        # Set video output directory if provided
        if video_output_dir:
            self.video_output_dir = video_output_dir
            if not os.path.exists(video_output_dir):
                os.makedirs(video_output_dir)

        url = is_valid_tweet_url(url)
        if self.lang:
            url += "?lang=" + self.lang

        radius = self.radius if radius is None else radius
        scale = self.scale if scale is None else scale
        
        # For video capture, we need GUI mode (non-headless)
        use_gui = self.gui or self.capture_videos
        
        driver = await get_driver(self.chrome_opts, self.driver_path, use_gui, scale)
        if driver is None:
            raise Exception("webdriver cannot be initialized")
        
        video_paths = []
        
        try:
            driver.get(url)
            driver.add_cookie(
                {"name": "night_mode", "value": str(self.night_mode if night_mode is None else night_mode)})
            if self.cookies:
                for cookie in self.cookies:
                    driver.add_cookie(cookie)
            driver.get(url)
            self.__init_scale_css(driver)
            await sleep(self.wait_time)
           
            self.__hide_global_items(driver)
            driver.execute_script("!!document.activeElement ? document.activeElement.blur() : 0")

            if self.test is True: 
                driver.save_screenshot(f"web{self.__web}.png")
                self.__web += 1
            await sleep(2.0)
            
            elements, main = self.__get_tweets(
                driver, 
                self.show_parent_tweets if show_parent_tweets is None else show_parent_tweets, 
                self.parent_tweets_limit if parent_tweets_limit is None else parent_tweets_limit, 
                self.show_mentions_count if show_mentions_count is None else show_mentions_count
            )
            
            if len(elements) == 0:
                raise Exception("Tweets not found")
            
            # Get the main tweet element
            main_element = elements[main] if main >= 0 and main < len(elements) else elements[0]
            
            # Detect and capture videos from the main tweet
            # #region agent log
            print(f"[DEBUG] Checking video capture: capture_videos={self.capture_videos}, video_output_dir={self.video_output_dir}")
            # #endregion
            if self.capture_videos and self.video_output_dir:
                logger.info("Capturing videos")
                # First detect how many videos are in the tweet
                video_count = self.detect_videos(main_element)
                # #region agent log
                print(f"[DEBUG] Video count detected: {video_count}")
                # #endregion
                
                if video_count > 0:
                    # Get the actual video player elements for capture
                    video_players = self.get_video_elements(main_element)
                    # Extract tweet ID from URL for filenames
                    tweet_id = url.split('/status/')[-1].split('?')[0].split('/')[0]
                    
                    for idx, video_player in enumerate(video_players):
                        video_path = self._capture_single_video(
                            driver, main_element, video_player, idx, tweet_id
                        )
                        if video_path:
                            video_paths.append(video_path)
            
            # Now take the screenshot (process elements as in original screenshot method)
            for i, element in enumerate(elements):
                if i == main:
                    self.__code_main_footer_items_new(element, self.mode if mode is None else mode)
                else:
                    try:
                        driver.execute_script(
                            self.__code_footer_items(self.mode if mode is None else mode), 
                            element.find_element(By.XPATH, ".//div[@role = 'group']"), 
                            element.find_element(By.CSS_SELECTOR, ".r-1hdv0qi:first-of-type")
                        )
                    except:
                        pass
                
                self.__hide_media(element, self.hide_link_previews, self.hide_photos, 
                                 self.hide_videos, self.hide_gifs, self.hide_quotes)
                if i == len(elements)-1:
                    self.__margin_tweet(self.mode if mode is None else mode, element)
                    
            if len(elements) == 1:
                driver.execute_script("window.scrollTo(0, 0);")
                x, y, width, height = driver.execute_script(
                    "var rect = arguments[0].getBoundingClientRect(); return [rect.x, rect.y, rect.width, rect.height];", 
                    elements[0]
                )
                await sleep(0.1)
                if scale != 1.0:
                    driver.save_screenshot(screenshot_path)
                else:
                    elements[0].screenshot(screenshot_path)
                if radius > 0 or scale != 1.0:
                    im = Image.open(screenshot_path)
                    if scale != 1.0:
                        im = im.crop((x, y, x+width, y+height))
                    if radius > 0:
                        im = add_corners(im, radius)
                    im.save(screenshot_path)
                    im.close()
            else:
                filenames = []
                for element in elements:
                    filename = "tmp_%s_tweetcapture.png" % element.id
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    x, y, width, height = driver.execute_script(
                        "var rect = arguments[0].getBoundingClientRect(); return [rect.x, rect.y, rect.width, rect.height];", 
                        element
                    )
                    await sleep(0.1)
                    if scale != 1.0:
                        driver.save_screenshot(filename)
                        im = Image.open(filename)
                        im = im.crop((x, y, x+width, y+height))
                        im.save(filename)
                        im.close()
                    else:
                        element.screenshot(filename)
                    filenames.append(filename)
                width = 0
                height = 0
                images = []
                for filename in filenames:
                    im = Image.open(filename)
                    if width == 0:
                        width = im.size[0]
                    height += im.size[1]
                    images.append(im)
                c = (255,255,255)
                if self.night_mode == 1:
                    c = (21,32,43)
                elif self.night_mode == 2:
                    c = (0,0,0)
                new_im = Image.new('RGB', (width,height), c)
                y = 0
                for im in images:
                    new_im.paste(im, (0,y))
                    y += im.size[1]
                    im.close()
                    remove(im.filename)
                
                if radius > 0:
                    new_im = add_corners(new_im, self.radius)
                new_im.save(screenshot_path, quality=100)
                new_im.close()
  
            driver.quit()
            
        except Exception as err:
            driver.quit()
            raise err
        
        return {
            'screenshot_path': screenshot_path,
            'video_paths': video_paths,
            'has_videos': len(video_paths) > 0
        }