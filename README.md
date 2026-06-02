<div align="center">
  <br/>
<h1>Zam</h1>
  
<br/>
<img src="https://img.shields.io/badge/Python-14354C?style=for-the-badge&logo=python&logoColor=white" alt="built with Python3" />
<img src="https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white" alt="uv" />
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
<img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
<img src="https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram" />
</div>

----------

Zam: A Telegram Bot for fetching and posting tweets to Telegram channels

<table border="0">
 <tr>
    <td><p align="justify">This program is dedicated to <a href="https://en.wikipedia.org/wiki/Ruhollah_Zam">Roohollah Zam</a>. 
      He was an Iranian activist and journalist. Zam played a high-profile role in the 2017–2018 Iranian protests, to which he devoted special coverage at the time. In June 2020, an Iran court found him guilty of "corruption on earth" for running a popular anti-government forum, which officials said had incited the 2017–2018 Iranian protests. He was sentenced to death by the regime court and was executed on 12 December 2020.
      </p>
</td>
    <td><img src="https://cdn.vox-cdn.com/thumbor/MZpfWZ4-9fV_LDEJihk5TAt_ILw=/0x0:3270x2142/1820x1213/filters:focal(1646x1148:2168x1670):format(webp)/cdn.vox-cdn.com/uploads/chorus_image/image/68502792/GettyImages_1223515476.0.jpg" alt="Roohollah Zam" width=800 /></td>
 </tr>
</table>


----------
## Table of contents			
   * [Overview](#overview)
   * [Features](#features)
   * [Installation](#installation)
   * [Configuration](#configuration)
   * [Usage](#usage)
   * [Architecture](#architecture)

----------
## Overview
<p align="justify">
Zam is a Telegram bot that fetches tweets via the <a href="https://scrapebadger.com">ScrapeBadger</a> API and posts them to a Telegram channel with their native media (photos and videos). Admins can schedule posts, and user suggestions are supported through a separate bot. The system uses a priority-based queue where admin requests are processed before user suggestions.
</p>

> **Note:** The bot supports two capture methods controlled by the `ZAM_CAPTURE_METHOD` env var: `scrapebadger` (default, API-based) fetches tweet data and media via the ScrapeBadger API with video downloads powered by yt-dlp. `screenshot` (legacy) captures tweets as screenshots using headless Chrome. The API method is faster, more reliable, and produces higher-quality results. Looking for the old Twitter API (Tweepy) version? It's in the [`legacy` branch](https://github.com/AminAlam/Zam/tree/legacy).

----------
## Features

### Core Features
- 🌐 **API-Based Tweet Fetching**: Fetches tweet text and metadata via the ScrapeBadger API — no browser rendering needed
- 📸 **Native Media Delivery**: Downloads and sends tweet photos and videos directly to Telegram (no screenshots)
- 🎬 **Video Downloads**: Automatically downloads tweet videos using yt-dlp with quality selection and auth support
- ✔️ **Verified Badge**: Displays author display names with a blue verified badge for verified accounts
- 🕐 **Accurate Timestamps**: Shows the tweet's original post time converted to Tehran timezone (Asia/Tehran via IANA tz database)
- 🔄 **Priority Queue System**: Admin tweets are processed before user suggestions
- ⏰ **Smart Auto-Scheduling**: Intelligent scheduling algorithm with peak hour optimization and minimum gap enforcement
- 🐳 **Docker Containerized**: Easy deployment with Docker Compose
- 🗄️ **PostgreSQL Database**: Reliable data storage with connection pooling
- 👥 **Multi-Bot Architecture**: Separate bots for admins and user suggestions
- 🚦 **Rate Limiting**: Configurable hourly limits for user suggestions
- 🇮🇷 **Persian Calendar Support**: Displays dates in Persian/Jalali calendar
- 📸 **Screenshot Fallback**: Falls back to headless Chrome screenshot capture if the API is unavailable

### Admin Bot Features
- 📊 **Monitoring Dashboard** (`/stats`): Real-time statistics including queue status, scheduled posts, and peak hour availability
- ⏰ **Manual & Auto Scheduling**: Choose specific times or let the smart algorithm pick optimal slots
- 📈 **Visual Progress Bars**: See hourly slot availability at a glance

### Suggestions Bot Features
- 🎯 **Interactive Menu**: User-friendly button-based navigation
- 📤 **Tweet Submission**: Easy tweet URL submission with queue position feedback
- 💬 **Categorized Feedback**: Users can send suggestions, bug reports, or questions to admins
- 📊 **Submission Tracking**: Users can view their remaining hourly submissions

----------
## Installation

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/AminAlam/Zam.git
   cd Zam
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your credentials (see [Configuration](#configuration) section).

3. **Build and start the containers**
   ```bash
   docker compose up --build -d
   ```

4. **View logs**
   ```bash
   docker compose logs -f app
   ```

5. **Stop the application**
   ```bash
   docker compose down
   ```

### Manual Installation (Development)

This project uses [uv](https://docs.astral.sh/uv/) for fast, reliable Python package management.

1. **Install uv** (if not already installed)
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Or with Homebrew
   brew install uv
   
   # Or with pip
   pip install uv
   ```

2. **Clone the repository**
   ```bash
   git clone https://github.com/AminAlam/Zam.git
   cd Zam
   ```

3. **Install dependencies**
   ```bash
   # Install all dependencies (including dev)
   uv sync
   
   # Or without dev dependencies
   uv sync --no-dev
   ```

4. **Install Chromium** (required for tweet-capture)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install chromium chromium-driver
   
   # macOS
   brew install chromium
   ```

5. **Set up PostgreSQL database**
   ```bash
   # Create database and run init.sql
   psql -U postgres -c "CREATE DATABASE zam_db;"
   psql -U postgres -d zam_db -f src/database/init.sql
   ```

6. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

7. **Run the application**
   ```bash
   uv run python -m src.main
   ```

### Common uv Commands

```bash
# Sync dependencies from lockfile
uv sync

# Add a new dependency
uv add <package>

# Add a dev dependency  
uv add --dev <package>

# Update all dependencies
uv lock --upgrade

# Run any command in the virtual environment
uv run <command>

# Run tests
uv run pytest

# Run the linter
uv run ruff check .
```

----------
## Configuration

Create a `.env` file in the project root with the following variables:

### Database Configuration
```bash
DB_HOST=db              # Use 'localhost' for manual installation
DB_PORT=5432
DB_USER=zam
DB_PASSWORD=your_secure_password
DB_NAME=zam_db
```

### Telegram Bot Tokens
Get bot tokens from [@BotFather](https://t.me/BotFather) on Telegram.

```bash
ADMIN_TELEGRAM_BOT=your_admin_bot_token
SUGGESTIONS_TELEGRAM_BOT=your_suggestions_bot_token
```

### Telegram Channel/Chat IDs
Get chat IDs by forwarding a message from the channel to [@userinfobot](https://t.me/userinfobot).

```bash
MAIN_CHANNEL_CHAT_ID=your_main_channel_id
ADMIN_CHAT_ID=your_admin_chat_id
SUGGESTIONS_CHAT_ID=your_suggestions_chat_id
```

### Channel Info
```bash
CHANNEL_NAME=@YourChannelName
ADMIN_IDS=admin1,admin2,admin3    # Telegram usernames without @
```

### Tweet Capture
```bash
# Capture method: "scrapebadger" (default) or "screenshot" (legacy Chromium)
ZAM_CAPTURE_METHOD=scrapebadger

# ScrapeBadger API key (required for scrapebadger method)
# Get one at https://scrapebadger.com
SCRAPEBADGER_API_KEY=sb_live_your_api_key

# Twitter/X auth token (optional, helps yt-dlp with protected/age-restricted videos)
# Get from browser DevTools > Application > Cookies > x.com > auth_token
AUTH_TOKEN=your_twitter_auth_token
```

----------
## Usage

### Command Line Options

```bash
uv run python -m src.main --help

Usage: main.py [OPTIONS]

  Zam: A Telegram Bot for posting tweets in a Telegram channel

Options:
  --time_diff TEXT              Difference between server time and target 
                                timezone. Format: HOURS:MINUTES (default: 3:30)
  --mahsa_message BOOLEAN       Enable Mahsa Amini memorial timer message
  --reference_snapshot BOOLEAN  Include snapshots of quoted/replied tweets
  --num_tweets_to_preserve INTEGER RANGE
                                Number of tweets to keep in database [500-5000]
  --user_tweet_limit INTEGER RANGE
                                Hourly limit per user for suggestions [0-120]
                                Set to 0 for unlimited
  --help                        Show this message and exit
```

### Docker with Options

```bash
# Run with custom options
docker compose run app uv run python -m src.main --time_diff 3:30 --user_tweet_limit 5
```

### Bot Commands

**Admin Bot:**
- Send a tweet URL (twitter.com or x.com) to add it to the queue
- `/start` - Start the bot
- `/queue` - View current queue status
- `/stats` - View comprehensive channel statistics:
  ```
  📊 Channel Statistics
  
  📝 Queue Status:
     • Pending captures: 3
     • Currently processing: 1
  
  📅 Scheduled Posts:
     • Awaiting posting: 8
     • Next post: 20:15 (in 12 min)
  
  📈 Today's Activity:
     • Posts sent: 24
  
  ⏰ Next 6 Hours Availability:
  20:00 ████████░░ 4/6
  21:00 ██████░░░░ 3/6
  22:00 ██░░░░░░░░ 1/6
  23:00 ░░░░░░░░░░ FULL
  ```

**Suggestions Bot:**
- `/start` - Open the interactive menu with options:
  - 📤 **Submit Tweet**: Send a tweet URL to suggest for the channel
  - 💬 **Send Feedback**: Send a message to admins (categorized as suggestion, bug report, or question)
  - 📊 **My Remaining Submissions**: Check your hourly submission limit status

### How It Works

1. **Submit a Tweet**: Send a tweet URL to either the admin or suggestions bot
2. **Queue Processing**: The tweet is added to a priority queue (admin tweets have higher priority)
3. **Fetch & Download**: A background worker fetches the tweet via ScrapeBadger API (text, author, media metadata, quoted tweets) and downloads photos directly; videos are downloaded via yt-dlp
4. **Admin Review**: The tweet text and native media are sent to the admin channel with scheduling options
5. **Schedule or Post**: Admins can schedule the tweet manually or use **Auto timing** for smart scheduling
6. **Channel Posting**: At the scheduled time, the tweet is posted to the main channel with all media attached

### Smart Auto-Scheduling

The "Auto timing" feature uses an intelligent algorithm to schedule tweets:

- **Peak Hour Optimization**: More tweets are scheduled during high-engagement hours (8 PM - 1 AM)
- **Quiet Hour Reduction**: Fewer tweets during low-activity hours (2 AM - 6 AM)
- **Minimum Gap Enforcement**: Ensures at least 5 minutes between consecutive tweets
- **Next-Day Rollover**: Automatically schedules for tomorrow if today's slots are full

**Hour Weight Distribution:**
| Period | Hours | Relative Weight |
|--------|-------|-----------------|
| Quiet | 2-6 AM | Low (0.3x) |
| Morning | 7-11 AM | Medium (0.7x) |
| Afternoon | 12-7 PM | Normal (0.8x) |
| **Evening** | 8-10 PM | **High (1.5x)** |
| **Night** | 11 PM-1 AM | **High (1.3x)** |

----------
## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Docker Compose                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            App Container (uv + Python 3.11)               │   │
│  │  ┌─────────────┐  ┌─────────────────────────┐            │   │
│  │  │ Admin Bot   │  │ Suggestions Bot         │            │   │
│  │  └──────┬──────┘  └───────────┬─────────────┘            │   │
│  │         └──────────┬──────────┘                           │   │
│  │                    ▼                                      │   │
│  │         ┌─────────────────────┐                           │   │
│  │         │   Queue Worker      │                           │   │
│  │         │  (Priority-based)   │                           │   │
│  │         └──────────┬──────────┘                           │   │
│  │                    ▼                                      │   │
│  │  ┌──────────────────────────┐  ┌───────────────────────┐ │   │
│  │  │  ScrapeBadger API Client │  │  Screenshot Capture   │ │   │
│  │  │  (tweet text & photos)   │  │  (Headless Chrome)    │ │   │
│  │  └────────────┬─────────────┘  │  [fallback]           │ │   │
│  │               │                └───────────────────────┘ │   │
│  │               ▼                                          │   │
│  │  ┌──────────────────────────┐                            │   │
│  │  │  yt-dlp Video Downloader │                            │   │
│  │  │  (tweet videos → MP4)    │                            │   │
│  │  └──────────────────────────┘                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          │                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           PostgreSQL Container                            │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │  Tables: tweets, tweet_queue, states,            │    │   │
│  │  │  tweets_line, errors, user_feedback              │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
Zam/
├── pyproject.toml            # Project configuration & dependencies
├── .python-version           # Python version specification
├── Dockerfile                # Docker build with uv
├── docker-compose.yml        # Container orchestration
├── src/                      # Main application code
│   ├── main.py               # Entry point
│   ├── telegram_backend.py   # Telegram bot handlers & scheduling
│   ├── twitter_backend.py    # Tweet capture dispatcher & queue
│   ├── scrapebadger_client.py # ScrapeBadger API client (fetch tweets & download photos)
│   ├── video_downloader.py   # yt-dlp wrapper (download tweet videos)
│   ├── configs.py            # Centralized configuration classes
│   ├── utils.py              # Utility functions
│   ├── ocr.py                # OCR text extraction (legacy fallback)
│   ├── migrations.py         # Database migrations
│   └── database/             # Database module
│       ├── database.py       # Database operations
│       └── init.sql          # Schema definitions
├── tweetcapture/             # Local tweet screenshot package (legacy fallback)
│   ├── pyproject.toml        # Package configuration
│   └── tweetcapture/         # Package source
└── tests/                    # Test suite
```

----------
## Testing

### Running Tests Locally

```bash
# Run all unit tests
uv run pytest tests/ -m "not integration and not slow"

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Run integration tests (requires Chrome/Chromium)
uv run pytest tests/test_integration.py -m "integration"

# Run all tests
uv run pytest
```

### Test Structure

- `tests/test_twitter_backend.py` - URL parsing, queue management tests
- `tests/test_utils.py` - Utility function tests
- `tests/test_database.py` - Database operation tests
- `tests/test_integration.py` - End-to-end integration tests

### GitHub Actions

Tests run automatically on pull requests with the following workflow:
1. **Approval Gate**: PRs require manual approval before tests run (protects against malicious code)
2. **Unit Tests**: Fast tests that don't require external services
3. **Integration Tests**: Tests with PostgreSQL and Chrome for screenshot capture
4. **Docker Build**: Verifies the Docker image builds correctly

The test suite uses Jack Dorsey's first tweet (`https://x.com/jack/status/20`) as a stable reference for screenshot capture tests.

----------
## License

This project is open source and available under the MIT License.
