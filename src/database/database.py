import os
import json
import datetime as dt
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager


class Database:
    def __init__(self):
        self.connection_pool = self._create_connection_pool()
        self.init_db()

    def _create_connection_pool(self):
        """Create a threaded connection pool for PostgreSQL."""
        try:
            db_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                user=os.getenv('DB_USER', 'zam'),
                password=os.getenv('DB_PASSWORD', ''),
                database=os.getenv('DB_NAME', 'zam_db')
            )
            print(f"Connected to PostgreSQL database at {os.getenv('DB_HOST', 'localhost')}")
            return db_pool
        except psycopg2.Error as e:
            print(f"Error creating connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for getting a connection from the pool."""
        conn = self.connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.connection_pool.putconn(conn)

    def init_db(self):
        """Initialize database tables if they don't exist."""
        print('Initializing the database...')
        # Tables are created via init.sql in Docker, but we verify connectivity here
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                print('- Database connection verified!')
        except psycopg2.Error as e:
            print(f"Database initialization error: {e}")

    def close(self):
        """Close the connection pool."""
        if self.connection_pool:
            self.connection_pool.closeall()

    # ==================== Error Logging ====================

    def error_log(self, error):
        """Log an error to the database."""
        error_text = str(error)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                time_now = dt.datetime.now()
                cursor.execute(
                    'INSERT INTO errors (error, time) VALUES (%s, %s)',
                    (error_text, time_now)
                )
            print(f"Error logged: {error}")
        except psycopg2.Error as e:
            print(f"Failed to log error: {e}")

    # ==================== Tweet Logging ====================

    def tweet_log(self, args):
        """Log a processed tweet."""
        try:
            tweet_id = args['tweet_id']
            tweet_text = args['tweet_text']
            user_name = args['user_name']
            status = args['status']
            admin = args.get('admin', False)
            time_now = dt.datetime.now()

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO tweets (tweet_id, tweet_text, user_name, status, time, admin) VALUES (%s, %s, %s, %s, %s, %s)',
                    (tweet_id, tweet_text, user_name, status, time_now, str(admin))
                )
        except Exception as e:
            self.error_log(e)

    def check_tweet_existence(self, tweet_id):
        """Check if a tweet has already been successfully processed."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT status FROM tweets WHERE tweet_id = %s',
                    (tweet_id,)
                )
                row = cursor.fetchone()
                if row and row[0] == 'Success':
                    return True
                return False
        except psycopg2.Error as e:
            self.error_log(e)
            return False

    def get_tweet_by_tweet_id(self, tweet_id):
        """Get a tweet by its ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM tweets WHERE tweet_id = %s',
                    (tweet_id,)
                )
                return cursor.fetchone()
        except psycopg2.Error as e:
            self.error_log(e)
            return None

    # ==================== Tweets Line (Scheduled Posts) ====================

    def add_tweet_to_line(self, args):
        """Add a tweet to the scheduled posting line."""
        try:
            tweet_id = args['tweet_id']
            tweet_text = args['tweet_text']
            media_list = args.get('media_list', '')
            media_list = json.dumps(media_list)

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO tweets_line (tweet_id, tweet_text, media) VALUES (%s, %s, %s)',
                    (tweet_id, tweet_text, media_list)
                )
        except Exception as e:
            self.error_log(e)

    def remove_tweet_from_line(self, tweet_id):
        """Remove a tweet from the scheduled line."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM tweets_line WHERE tweet_id = %s',
                    (tweet_id,)
                )
        except Exception as e:
            self.error_log(e)

    def get_tweet_from_line(self, tweet_id):
        """Get a specific tweet from the scheduled line."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT * FROM tweets_line WHERE tweet_id = %s',
                    (tweet_id,)
                )
                return cursor.fetchone()
        except Exception as e:
            self.error_log(e)
            return None

    def set_sending_time_for_tweet_in_line(self, tweet_id, sending_time, tweet_text, entities, query):
        """Set the scheduled sending time for a tweet in the line."""
        try:
            entities_json = json.dumps(entities)
            query_json = json.dumps(query)

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE tweets_line SET sending_time = %s, tweet_text = %s, entities = %s, query = %s WHERE tweet_id = %s',
                    (sending_time, tweet_text, entities_json, query_json, tweet_id)
                )
        except Exception as e:
            self.error_log(e)

    def get_tweets_line(self):
        """Get all tweets in the scheduled line."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tweets_line')
                return cursor.fetchall()
        except Exception as e:
            self.error_log(e)
            return []

    def remove_old_tweets_in_line(self, num_tweets_to_preserve=1000):
        """Remove old tweets from the line, keeping only the most recent ones."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM tweets_line')
                num_tweets = cursor.fetchone()[0]

                if num_tweets > num_tweets_to_preserve:
                    # Delete oldest tweets beyond the limit
                    cursor.execute('''
                        DELETE FROM tweets_line 
                        WHERE id IN (
                            SELECT id FROM tweets_line 
                            ORDER BY id ASC 
                            LIMIT %s
                        )
                    ''', (num_tweets - num_tweets_to_preserve,))
        except Exception as e:
            self.error_log(e)

    # ==================== States (Chat State Management) ====================

    def set_state(self, chat_id, state):
        """Set the state for a chat."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO states (chat_id, state) VALUES (%s, %s)
                       ON CONFLICT (chat_id) DO UPDATE SET state = EXCLUDED.state''',
                    (chat_id, state)
                )
        except Exception as e:
            self.error_log(e)

    def get_state(self, chat_id):
        """Get the state for a chat."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT state FROM states WHERE chat_id = %s',
                    (chat_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            self.error_log(e)
            return None

    # ==================== Time Counter ====================

    def get_time_counter_message_id(self):
        """Get the message ID for the time counter."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT message_id FROM time_counter LIMIT 1')
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            self.error_log(e)
            return None

    def set_time_counter_message_id(self, message_id):
        """Set the message ID for the time counter."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Clear existing and insert new
                cursor.execute('DELETE FROM time_counter')
                cursor.execute(
                    'INSERT INTO time_counter (message_id) VALUES (%s)',
                    (message_id,)
                )
        except Exception as e:
            self.error_log(e)

    # ==================== Tweet Queue (Priority-based Processing) ====================

    def add_to_queue(self, tweet_url, tweet_id, user_name, chat_id, bot_type, priority=0):
        """Add a tweet to the processing queue."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO tweet_queue 
                       (tweet_url, tweet_id, user_name, chat_id, bot_type, priority, status, added_time) 
                       VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
                       RETURNING id''',
                    (tweet_url, tweet_id, user_name, chat_id, bot_type, priority)
                )
                queue_id = cursor.fetchone()[0]
                return queue_id
        except Exception as e:
            self.error_log(e)
            return None

    def get_next_pending(self):
        """Get the next pending item from the queue (highest priority first)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, tweet_url, tweet_id, user_name, chat_id, bot_type, priority, added_time
                    FROM tweet_queue 
                    WHERE status = 'pending'
                    ORDER BY priority DESC, added_time ASC
                    LIMIT 1
                ''')
                return cursor.fetchone()
        except Exception as e:
            self.error_log(e)
            return None

    def mark_processing(self, queue_id):
        """Mark a queue item as being processed."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tweet_queue SET status = 'processing' WHERE id = %s",
                    (queue_id,)
                )
        except Exception as e:
            self.error_log(e)

    def mark_completed(self, queue_id):
        """Mark a queue item as completed."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tweet_queue SET status = 'completed', processed_time = NOW() WHERE id = %s",
                    (queue_id,)
                )
        except Exception as e:
            self.error_log(e)

    def mark_failed(self, queue_id, error_message):
        """Mark a queue item as failed with an error message."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tweet_queue SET status = 'failed', processed_time = NOW(), error_message = %s WHERE id = %s",
                    (error_message, queue_id)
                )
        except Exception as e:
            self.error_log(e)

    def get_queue_position(self, queue_id):
        """Get the position of an item in the queue (among pending items)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Get the item's priority and added_time
                cursor.execute(
                    'SELECT priority, added_time FROM tweet_queue WHERE id = %s',
                    (queue_id,)
                )
                item = cursor.fetchone()
                if not item:
                    return None

                priority, added_time = item

                # Count items ahead in queue (higher priority, or same priority but earlier)
                cursor.execute('''
                    SELECT COUNT(*) FROM tweet_queue 
                    WHERE status = 'pending' 
                    AND (priority > %s OR (priority = %s AND added_time < %s))
                ''', (priority, priority, added_time))

                position = cursor.fetchone()[0] + 1  # +1 because position is 1-indexed
                return position
        except Exception as e:
            self.error_log(e)
            return None

    def get_pending_count(self):
        """Get the total number of pending items in the queue."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tweet_queue WHERE status = 'pending'")
                return cursor.fetchone()[0]
        except Exception as e:
            self.error_log(e)
            return 0

    def check_tweet_in_queue(self, tweet_id):
        """Check if a tweet is already in the queue (pending or processing)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, status FROM tweet_queue WHERE tweet_id = %s AND status IN ('pending', 'processing')",
                    (tweet_id,)
                )
                return cursor.fetchone()
        except Exception as e:
            self.error_log(e)
            return None

    # ==================== User Rate Limiting ====================

    def get_user_tweet_count_last_hour(self, user_name):
        """Get the number of tweets a user has submitted in the last hour."""
        try:
            time_1_hour_ago = dt.datetime.now() - dt.timedelta(hours=1)
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM tweets WHERE user_name = %s AND time > %s',
                    (user_name, time_1_hour_ago)
                )
                return cursor.fetchone()[0]
        except Exception as e:
            self.error_log(e)
            return 0
