FROM python:3.11-slim

# Install Chromium and dependencies for tweet-capture
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-noto \
    fonts-noto-core \
    fonts-freefont-ttf \
    fonts-dejavu-core \
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
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome/Chromium environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-dev-shm-usage"

# Ensure Python output is not buffered (important for Docker logs)
ENV PYTHONUNBUFFERED=1

# Tell webdriver-manager to use system chromedriver
ENV WDM_LOCAL=1
ENV WDM_SKIP_CACHE=true

WORKDIR /app

# Create screenshots directory
RUN mkdir -p /app/screenshots

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "src/main.py"]
