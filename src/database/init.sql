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
    admin TEXT,
    ocr_author TEXT,           -- OCR-detected author name
    ocr_text TEXT              -- OCR-detected tweet text
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
    error_message TEXT,
    batch_id TEXT,                        -- Groups multiple tweets from same submission
    batch_total INTEGER DEFAULT 1,        -- Total items in this batch
    ocr_author TEXT,                      -- OCR-detected author name
    ocr_text TEXT                         -- OCR-detected tweet text
);

-- Index for efficient queue processing: get pending items ordered by priority and time
CREATE INDEX IF NOT EXISTS idx_queue_status_priority ON tweet_queue(status, priority DESC, added_time ASC);
CREATE INDEX IF NOT EXISTS idx_queue_tweet_id ON tweet_queue(tweet_id);
CREATE INDEX IF NOT EXISTS idx_queue_batch_id ON tweet_queue(batch_id);

-- User feedback table: stores user messages/suggestions/bug reports
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255),
    chat_id VARCHAR(255),
    category VARCHAR(50),  -- 'suggestion', 'bug', 'question'
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON user_feedback(user_name);
CREATE INDEX IF NOT EXISTS idx_feedback_category ON user_feedback(category);

-- Migration: Add new columns to existing tables if they don't exist
-- These ALTER statements will fail silently if columns already exist

DO $$ 
BEGIN
    -- Add OCR columns to tweets table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tweets' AND column_name='ocr_author') THEN
        ALTER TABLE tweets ADD COLUMN ocr_author TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tweets' AND column_name='ocr_text') THEN
        ALTER TABLE tweets ADD COLUMN ocr_text TEXT;
    END IF;
    
    -- Add batch columns to tweet_queue table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tweet_queue' AND column_name='batch_id') THEN
        ALTER TABLE tweet_queue ADD COLUMN batch_id TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tweet_queue' AND column_name='batch_total') THEN
        ALTER TABLE tweet_queue ADD COLUMN batch_total INTEGER DEFAULT 1;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tweet_queue' AND column_name='ocr_author') THEN
        ALTER TABLE tweet_queue ADD COLUMN ocr_author TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='tweet_queue' AND column_name='ocr_text') THEN
        ALTER TABLE tweet_queue ADD COLUMN ocr_text TEXT;
    END IF;
END $$;
