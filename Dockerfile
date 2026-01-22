FROM python:3.11-slim

# Install uv for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Chromium, FFmpeg, Xvfb, PulseAudio, and other dependencies
RUN apt-get update && apt-get install -y \
    # Browser and driver
    chromium \
    chromium-driver \
    # Fonts for proper text rendering (including Persian/Arabic)
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto \
    fonts-noto-core \
    fonts-freefont-ttf \
    fonts-dejavu-core \
    fonts-farsiweb \
    fonts-hosny-amiri \
    # Browser dependencies
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # Video capture dependencies
    ffmpeg \
    xvfb \
    pulseaudio \
    pulseaudio-utils \
    # X11 libraries for screen capture
    x11-utils \
    x11-xserver-utils \
    # Tesseract OCR and language packs
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fas \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome/Chromium environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_DRIVER=/usr/bin/chromedriver
ENV CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-dev-shm-usage"

# Set display for Xvfb (virtual framebuffer)
ENV DISPLAY=:99

# Ensure Python output is not buffered (important for Docker logs)
ENV PYTHONUNBUFFERED=1

# Tell webdriver-manager to use system chromedriver
ENV WDM_LOCAL=1
ENV WDM_SKIP_CACHE=true

# Enable uv to use system Python
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# Create directories for screenshots and videos
RUN mkdir -p /app/screenshots /app/videos

# Copy project files for uv
COPY pyproject.toml uv.lock* README.md ./

# Copy tweetcapture library
COPY tweetcapture/ ./tweetcapture/

# Install dependencies using uv
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ ./src/

# Install the project itself
RUN uv sync --frozen --no-dev

# Create entrypoint script to start Xvfb and PulseAudio
RUN echo '#!/bin/bash\n\
# Clean up stale X lock files from previous runs\n\
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 2>/dev/null || true\n\
\n\
# Start Xvfb (virtual framebuffer) - use 1280x1200 to accommodate tall tweets\n\
Xvfb :99 -screen 0 1280x1200x24 &\n\
sleep 1\n\
\n\
# Start PulseAudio for audio capture (optional, may fail in some environments)\n\
pulseaudio --start --exit-idle-time=-1 2>/dev/null || true\n\
# Create a predictable sink/source for capturing browser audio (best-effort)\n\
pactl load-module module-null-sink sink_name=zam sink_properties=device.description=zam 2>/dev/null || true\n\
pactl set-default-sink zam 2>/dev/null || true\n\
pactl set-default-source zam.monitor 2>/dev/null || true\n\
\n\
# Run the main application using uv\n\
exec uv run python -m src.main\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
