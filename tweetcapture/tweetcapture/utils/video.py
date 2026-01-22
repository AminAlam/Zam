"""
Video recording utilities for capturing tweet videos using FFmpeg.
Supports screen recording of specific regions with audio capture.
"""

import json
import os
import signal
import subprocess
import time
from typing import Optional, Tuple


def _ndjson_log(hypothesisId: str, location: str, message: str, data: dict | None = None, runId: str = "pre-fix") -> None:
    """
    Debug-mode NDJSON logger (best-effort, no secrets).
    Writes to ZAM_DEBUG_LOG_PATH which is volume-mounted to host .cursor/debug.log.
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
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Never crash app due to logging
        pass


class ScreenRecorder:
    """
    FFmpeg-based screen recorder for capturing specific screen regions.
    Uses x11grab on Linux and gdigrab on Windows.
    """

    def __init__(self, output_path: str, region: Tuple[int, int, int, int],
                 display: str = ":99", fps: int = None, with_audio: bool = True):
        """
        Initialize the screen recorder.
        
        Args:
            output_path: Path to save the recorded video (MP4)
            region: Tuple of (x, y, width, height) defining the capture region
            display: X display to capture from (Linux only)
            fps: Frames per second (reads from ZAM_VIDEO_FPS env, default 15)
            with_audio: Whether to capture audio
        """
        self.output_path = output_path
        self.region = region
        self.display = display
        # Read FPS from environment variable, default to 15
        self.fps = fps if fps is not None else int(os.environ.get("ZAM_VIDEO_FPS", "15"))
        self.with_audio = with_audio
        self._process: Optional[subprocess.Popen] = None
        self._recording = False

    def _build_ffmpeg_command(self) -> list:
        """Build the FFmpeg command for screen recording."""
        x, y, width, height = self.region

        # Ensure dimensions are even (required by H.264)
        width = width if width % 2 == 0 else width + 1
        height = height if height % 2 == 0 else height + 1

        # Read configurable parameters from environment
        thread_queue = os.environ.get("ZAM_VIDEO_THREAD_QUEUE", "4096")
        crf = os.environ.get("ZAM_VIDEO_CRF", "32")

        cmd = ['ffmpeg', '-y']  # -y to overwrite output file

        # Check platform
        if os.name == 'nt':
            # Windows - use gdigrab
            cmd.extend([
                '-f', 'gdigrab',
                '-framerate', str(self.fps),
                '-offset_x', str(x),
                '-offset_y', str(y),
                '-video_size', f'{width}x{height}',
                '-i', 'desktop'
            ])

            if self.with_audio:
                # Windows audio capture (requires audio device)
                cmd.extend([
                    '-f', 'dshow',
                    '-i', 'audio=Stereo Mix'
                ])
        else:
            # Linux - use x11grab with settings optimized for Xvfb stability
            cmd.extend([
                '-f', 'x11grab',
                '-draw_mouse', '0',
                '-thread_queue_size', thread_queue,
                '-framerate', str(self.fps),
                '-video_size', f'{width}x{height}',
                '-i', f'{self.display}+{x},{y}'
            ])

            if self.with_audio:
                # Linux audio capture via PulseAudio
                cmd.extend([
                    '-f', 'pulse',
                    '-thread_queue_size', thread_queue,
                    '-ac', '2',
                    '-i', 'default'
                ])

        # Output settings - prioritize speed to avoid drops
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', crf,  # Configurable via ZAM_VIDEO_CRF env var
            '-pix_fmt', 'yuv420p',
        ])

        if self.with_audio:
            cmd.extend([
                '-c:a', 'aac',
                '-b:a', '128k'
            ])

        cmd.append(self.output_path)

        # #region agent log
        _ndjson_log(
            hypothesisId="H_AUDIO_OR_FFMPEG",
            location="tweetcapture/utils/video.py:ScreenRecorder._build_ffmpeg_command",
            message="Built ffmpeg command",
            data={"with_audio": self.with_audio, "display": self.display, "region": list(self.region), "cmd": cmd},
        )
        # #endregion

        return cmd

    def start(self) -> bool:
        """
        Start screen recording.
        
        Returns:
            True if recording started successfully, False otherwise
        """
        if self._recording:
            return False

        try:
            cmd = self._build_ffmpeg_command()

            # #region agent log
            print(f"[DEBUG] FFmpeg command: {' '.join(cmd)}")
            print(f"[DEBUG] Capture region: {self.region}, display: {self.display}")
            _ndjson_log(
                hypothesisId="H_AUDIO_OR_FFMPEG",
                location="tweetcapture/utils/video.py:ScreenRecorder.start",
                message="Starting ffmpeg",
                data={"with_audio": self.with_audio, "display": self.display, "region": list(self.region)},
            )
            # #endregion

            # Start FFmpeg process
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # Don't create a new process group on Windows
                preexec_fn=os.setsid if os.name != 'nt' else None
            )

            # #region agent log
            # Give FFmpeg a moment to start and check if it's still running
            time.sleep(0.5)
            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                print(f"[DEBUG] FFmpeg exited immediately with code {self._process.returncode}")
                # Print last 2000 chars to see actual error (not just version info)
                print(f"[DEBUG] FFmpeg stderr (last 2000 chars): {stderr[-2000:]}")
                _ndjson_log(
                    hypothesisId="H_AUDIO_OR_FFMPEG",
                    location="tweetcapture/utils/video.py:ScreenRecorder.start",
                    message="ffmpeg exited immediately",
                    data={"returncode": self._process.returncode, "stderr_tail": stderr[-2000:]},
                )
                return False
            print(f"[DEBUG] FFmpeg started successfully, pid={self._process.pid}")
            _ndjson_log(
                hypothesisId="H_AUDIO_OR_FFMPEG",
                location="tweetcapture/utils/video.py:ScreenRecorder.start",
                message="ffmpeg started",
                data={"pid": self._process.pid},
            )
            # #endregion

            self._recording = True
            return True

        except FileNotFoundError:
            print("FFmpeg not found. Please install FFmpeg.")
            return False
        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False

    def stop(self) -> Optional[str]:
        """
        Stop screen recording.
        
        Returns:
            Path to the recorded video if successful, None otherwise
        """
        if not self._recording or self._process is None:
            return None

        try:
            # #region agent log
            # Check if process already died
            poll_result = self._process.poll()
            if poll_result is not None:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                print(f"[DEBUG] FFmpeg already exited with code {poll_result}")
                print(f"[DEBUG] FFmpeg stderr: {stderr[:2000]}")
                self._recording = False
                self._process = None
                return None
            # #endregion

            # Send 'q' to FFmpeg to gracefully stop recording
            if self._process.stdin:
                self._process.stdin.write(b'q')
                self._process.stdin.flush()

            # Wait for process to finish (with timeout)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't stop gracefully
                if os.name != 'nt':
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                else:
                    self._process.kill()
                self._process.wait()

            self._recording = False
            self._process = None

            # Verify output file exists
            if os.path.exists(self.output_path):
                return self.output_path
            return None

        except Exception as e:
            print(f"Error stopping recording: {e}")
            self._recording = False
            return None

    def is_recording(self) -> bool:
        """Check if recording is in progress."""
        return self._recording


class VideoRecordingManager:
    """
    High-level manager for recording tweet videos.
    Handles the coordination between browser playback and screen recording.
    """

    def __init__(self, output_dir: str, display: str = ":99"):
        """
        Initialize the video recording manager.
        
        Args:
            output_dir: Directory to save recorded videos
            display: X display for screen capture (Linux)
        """
        self.output_dir = output_dir
        self.display = display

        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def record_video(self, region: Tuple[int, int, int, int],
                     duration: float, filename: str,
                     with_audio: bool = True) -> Optional[str]:
        """
        Record a video for a specified duration.
        
        Args:
            region: Screen region to capture (x, y, width, height)
            duration: Recording duration in seconds
            filename: Output filename (without directory)
            with_audio: Whether to capture audio
            
        Returns:
            Path to recorded video if successful, None otherwise
        """
        output_path = os.path.join(self.output_dir, filename)

        recorder = ScreenRecorder(
            output_path=output_path,
            region=region,
            display=self.display,
            with_audio=with_audio
        )

        if not recorder.start():
            return None

        # Wait for the specified duration
        time.sleep(duration)

        return recorder.stop()

    def record_with_callback(self, region: Tuple[int, int, int, int],
                             filename: str, with_audio: bool = True) -> 'RecordingSession':
        """
        Start a recording session that can be stopped manually.
        
        Args:
            region: Screen region to capture
            filename: Output filename
            with_audio: Whether to capture audio
            
        Returns:
            RecordingSession object to control the recording
        """
        output_path = os.path.join(self.output_dir, filename)

        recorder = ScreenRecorder(
            output_path=output_path,
            region=region,
            display=self.display,
            with_audio=with_audio
        )

        return RecordingSession(recorder)


class RecordingSession:
    """
    Represents an active recording session that can be controlled externally.
    """

    def __init__(self, recorder: ScreenRecorder):
        self.recorder = recorder
        self._started = False

    def start(self) -> bool:
        """Start the recording session."""
        if self._started:
            return False
        self._started = self.recorder.start()
        return self._started

    def stop(self) -> Optional[str]:
        """Stop the recording session and return the video path."""
        if not self._started:
            return None
        result = self.recorder.stop()
        self._started = False
        return result

    def is_recording(self) -> bool:
        """Check if the session is currently recording."""
        return self.recorder.is_recording()


def get_element_screen_position(driver, element, use_viewport_coords: bool = True) -> Tuple[int, int, int, int]:
    """
    Get the screen position of a Selenium WebElement.
    
    In Xvfb environments, browser window position APIs return unreliable values.
    When use_viewport_coords is True (default), we assume the browser content
    area starts at the top-left of the X display (which is true when maximized
    in headless/Xvfb mode with no visible chrome).
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to get position of
        use_viewport_coords: If True, use viewport-relative coords (for Xvfb)
        
    Returns:
        Tuple of (x, y, width, height) in screen coordinates
    """
    # Get element position + window metrics in CSS px and convert to device px (x11grab works in device px)
    m = driver.execute_script("""
        const r = arguments[0].getBoundingClientRect();
        return {
          rect: {x: r.x, y: r.y, width: r.width, height: r.height},
          dpr: window.devicePixelRatio || 1,
          screenX: window.screenX || window.screenLeft || 0,
          screenY: window.screenY || window.screenTop || 0,
          outerHeight: window.outerHeight || 0,
          innerHeight: window.innerHeight || 0
        };
    """, element)

    rect = m["rect"]
    dpr = float(m.get("dpr", 1) or 1)
    chrome_height_css = float(m.get("outerHeight", 0) - m.get("innerHeight", 0))

    if use_viewport_coords:
        # In kiosk/app mode, viewport starts at (0,0) on the screen.
        # Elements are scrolled into view, so we use the viewport-relative coordinates.
        screen_x = int(rect["x"] * dpr)
        screen_y = int(rect["y"] * dpr)
    else:
        # Screen-relative: account for browser window position + top chrome
        # window.screenX/Y and chrome height can be unreliable in some headless environments.
        screen_x = int((float(m.get("screenX", 0)) + rect["x"]) * dpr)
        screen_y = int((float(m.get("screenY", 0)) + chrome_height_css + rect["y"]) * dpr)

    # Ensure coordinates are non-negative and within screen bounds
    screen_x = max(0, screen_x)
    screen_y = max(0, screen_y)

    # Width and height must be even for H.264
    width = int(rect["width"] * dpr)
    height = int(rect["height"] * dpr)
    if width % 2 != 0: width += 1
    if height % 2 != 0: height += 1

    # #region agent log
    _ndjson_log(
        hypothesisId="H_CROP_MATH",
        location="tweetcapture/utils/video.py:get_element_screen_position",
        message="Computed capture region",
        data={
            "use_viewport_coords": use_viewport_coords,
            "rect_css": rect,
            "dpr": dpr,
            "screenX_css": m.get("screenX"),
            "screenY_css": m.get("screenY"),
            "chrome_height_css": chrome_height_css,
            "region_px": [screen_x, screen_y, width, height],
        },
    )
    # #endregion

    return (screen_x, screen_y, width, height)


def check_ffmpeg_available() -> bool:
    """
    Check if FFmpeg is available on the system.
    
    Returns:
        True if FFmpeg is available, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_video_duration(video_path: str) -> Optional[float]:
    """
    Get the duration of a video file using FFprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Duration in seconds, or None if unable to determine
    """
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return float(result.stdout.strip())
        return None
    except (FileNotFoundError, ValueError):
        return None


def _ffprobe_basic_stats(video_path: str) -> dict:
    """
    Best-effort: return basic playback stats to diagnose stutter (fps/duration).
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate,r_frame_rate,nb_frames",
                "-show_entries", "format=duration",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {"error": "ffprobe_failed", "stderr_tail": (result.stderr or "")[-500:]}
        return json.loads(result.stdout or "{}")
    except Exception as e:
        return {"error": "ffprobe_exception", "detail": str(e)[:200]}


def compress_video_for_telegram(input_path: str, output_path: str,
                                 max_size_mb: int = 50) -> Optional[str]:
    """
    Compress a video to fit within Telegram's file size limit.
    
    Args:
        input_path: Path to input video
        output_path: Path for compressed output
        max_size_mb: Maximum file size in MB (Telegram limit is 50MB)
        
    Returns:
        Path to compressed video if successful, None otherwise
    """
    try:
        # Get input file size
        input_size = os.path.getsize(input_path) / (1024 * 1024)  # MB

        if input_size <= max_size_mb:
            # No compression needed
            return input_path

        # Calculate target bitrate
        duration = get_video_duration(input_path)
        if duration is None:
            duration = 60  # Assume 60 seconds if unknown

        # Target size in bits, with some margin
        target_size_bits = (max_size_mb * 0.9) * 8 * 1024 * 1024
        target_bitrate = int(target_size_bits / duration)

        # Run compression
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-b:v', f'{target_bitrate}',
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '96k',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        return None

    except Exception as e:
        print(f"Video compression failed: {e}")
        return None

