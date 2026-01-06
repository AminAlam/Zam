<div align="center">
  <br/>
<h1>Zam</h1>
  
<br/>
<img src="https://img.shields.io/badge/Python-14354C?style=for-the-badge&logo=python&logoColor=white" alt="built with Python3" />
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
<img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/800px-Telegram_logo.svg.png" style="width:3%" />
</div>

----------

Zam: A Telegram Bot for capturing and posting tweets to Telegram channels

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
Zam is a Telegram bot that captures tweets as screenshots and allows admins to schedule them for posting to a Telegram channel. It uses a priority-based queue system where admin requests are processed before user suggestions.
</p>

> **Note:** Looking for the Twitter API version? The legacy code that uses the Twitter/X API (Tweepy) is available in the [`legacy` branch](https://github.com/AminAlam/Zam/tree/legacy). This version uses screenshot capture instead, as the Twitter API became restricted/expensive after the X acquisition.

----------
## Features

- 📸 **Tweet Screenshot Capture**: Captures tweets as high-quality screenshots using headless Chrome
- 🔄 **Priority Queue System**: Admin tweets are processed before user suggestions
- ⏰ **Scheduled Posting**: Schedule tweets for later posting with flexible timing options
- 🐳 **Docker Containerized**: Easy deployment with Docker Compose
- 🗄️ **PostgreSQL Database**: Reliable data storage with connection pooling
- 👥 **Multi-Bot Architecture**: Separate bots for admins and user suggestions
- 🚦 **Rate Limiting**: Configurable hourly limits for user suggestions
- 🇮🇷 **Persian Calendar Support**: Displays dates in Persian/Jalali calendar

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
   docker-compose up --build -d
   ```

4. **View logs**
   ```bash
   docker-compose logs -f app
   ```

5. **Stop the application**
   ```bash
   docker-compose down
   ```

### Manual Installation (Development)

1. **Clone the repository**
   ```bash
   git clone https://github.com/AminAlam/Zam.git
   cd Zam
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Chromium** (required for tweet-capture)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install chromium chromium-driver
   
   # macOS
   brew install chromium
   ```

4. **Set up PostgreSQL database**
   ```bash
   # Create database and run init.sql
   psql -U postgres -c "CREATE DATABASE zam_db;"
   psql -U postgres -d zam_db -f src/database/init.sql
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

6. **Run the application**
   ```bash
   python src/main.py
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

----------
## Usage

### Command Line Options

```bash
python src/main.py --help

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
docker-compose run app python src/main.py --time_diff 3:30 --user_tweet_limit 5
```

### Bot Commands

**Admin Bot:**
- Send a tweet URL (twitter.com or x.com) to add it to the queue
- `/queue` - View current queue status
- `/start` - Start the bot

**Suggestions Bot:**
- Send a tweet URL to suggest it for the channel
- `/start` - Start the bot

### How It Works

1. **Submit a Tweet**: Send a tweet URL to either the admin or suggestions bot
2. **Queue Processing**: The tweet is added to a priority queue (admin tweets have higher priority)
3. **Screenshot Capture**: A background worker captures the tweet as a screenshot
4. **Admin Review**: The captured tweet is sent to the admin channel with scheduling options
5. **Schedule or Post**: Admins can schedule the tweet or post it immediately
6. **Channel Posting**: At the scheduled time, the tweet is posted to the main channel

----------
## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │              App Container                       │    │
│  │  ┌─────────────┐  ┌─────────────────────────┐   │    │
│  │  │ Admin Bot   │  │ Suggestions Bot         │   │    │
│  │  └──────┬──────┘  └───────────┬─────────────┘   │    │
│  │         │                     │                  │    │
│  │         └──────────┬──────────┘                  │    │
│  │                    ▼                             │    │
│  │         ┌─────────────────────┐                  │    │
│  │         │   Queue Worker      │                  │    │
│  │         │  (Priority-based)   │                  │    │
│  │         └──────────┬──────────┘                  │    │
│  │                    ▼                             │    │
│  │         ┌─────────────────────┐                  │    │
│  │         │   Tweet Capture     │                  │    │
│  │         │  (Headless Chrome)  │                  │    │
│  │         └─────────────────────┘                  │    │
│  └─────────────────────────────────────────────────┘    │
│                          │                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │           PostgreSQL Container                   │    │
│  │  ┌─────────────────────────────────────────┐    │    │
│  │  │  Tables: tweets, tweet_queue, states,   │    │    │
│  │  │          tweets_line, errors            │    │    │
│  │  └─────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

----------
## License

This project is open source and available under the MIT License.
