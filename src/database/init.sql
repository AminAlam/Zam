-- PostgreSQL Schema for Zam Telegram Bot
-- This file is automatically executed when the PostgreSQL container starts

-- Tweets table: stores all processed tweets
CREATE TABLE IF NOT EXISTS tweets (
    id SERIAL PRIMARY KEY,
    tweet_id TEXT NOT NULL,
    tweet_text TEXT NOT NULL,
    user_name TEXT NOT NULL,
    status TEXT NOT NULL,
    time TIMESTAMP NOT NULL,
    admin TEXT
);

CREATE INDEX IF NOT EXISTS idx_tweets_tweet_id ON tweets(tweet_id);

-- Errors table: stores error logs
CREATE TABLE IF NOT EXISTS errors (
    id SERIAL PRIMARY KEY,
    error TEXT NOT NULL,
    time TIMESTAMP NOT NULL
);

-- Tweets line table: stores scheduled tweets waiting to be posted
CREATE TABLE IF NOT EXISTS tweets_line (
    id SERIAL PRIMARY KEY,
    tweet_id TEXT NOT NULL,
    tweet_text TEXT,
    media TEXT,
    sending_time TIMESTAMP,
    entities TEXT,
    query TEXT
);

CREATE INDEX IF NOT EXISTS idx_tweets_line_sending_time ON tweets_line(sending_time);

-- States table: stores chat states for conversation handling
CREATE TABLE IF NOT EXISTS states (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL UNIQUE,
    state TEXT
);

-- Time counter table: stores message ID for the time counter feature
CREATE TABLE IF NOT EXISTS time_counter (
    message_id TEXT NOT NULL
);

-- Tweet Queue table: priority-based queue for tweet processing
CREATE TABLE IF NOT EXISTS tweet_queue (
    id SERIAL PRIMARY KEY,
    tweet_url TEXT NOT NULL,
    tweet_id TEXT,
    user_name TEXT,
    chat_id TEXT,
    bot_type TEXT NOT NULL,              -- 'admin' or 'suggestions'
    priority INTEGER DEFAULT 0,           -- higher value = processed first (admin=10, suggestions=1)
    status TEXT DEFAULT 'pending',        -- 'pending', 'processing', 'completed', 'failed'
    added_time TIMESTAMP DEFAULT NOW(),
    processed_time TIMESTAMP,
    error_message TEXT
);

-- Index for efficient queue processing: get pending items ordered by priority and time
CREATE INDEX IF NOT EXISTS idx_queue_status_priority ON tweet_queue(status, priority DESC, added_time ASC);
CREATE INDEX IF NOT EXISTS idx_queue_tweet_id ON tweet_queue(tweet_id);

