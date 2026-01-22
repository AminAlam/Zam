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
    # X11 libraries for screen capture (client-side only, Xvfb runs in separate service)
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
COPY pyproject.toml README.md ./

# Copy tweetcapture library
COPY tweetcapture/ ./tweetcapture/

# Install dependencies using uv
RUN uv sync --no-dev --no-install-project

# Copy source code
COPY src/ ./src/

# Install the project itself
RUN uv sync --no-dev

# Create simplified entrypoint script
# Xvfb and PulseAudio are now running in a separate service
RUN echo '#!/bin/bash\n\
# Clean up any stale lock files (defensive, should not be needed with separate service)\n\
rm -f /tmp/.X99-lock 2>/dev/null || true\n\
\n\
# Wait for X display to be available (should already be ready via healthcheck)\n\
echo "Waiting for X display :99..."\n\
for i in {1..30}; do\n\
  if [ -S /tmp/.X11-unix/X99 ]; then\n\
    echo "X display :99 is ready"\n\
    break\n\
  fi\n\
  echo "Waiting for X display... ($i/30)"\n\
  sleep 1\n\
done\n\
\n\
if [ ! -S /tmp/.X11-unix/X99 ]; then\n\
  echo "ERROR: X display :99 not available after 30 seconds"\n\
  exit 1\n\
fi\n\
\n\
# Run the main application using uv\n\
exec uv run python -m src.main\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
