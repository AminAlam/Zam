"""
Unit tests for database module.
Tests database operations with mocked PostgreSQL connection.
"""
from unittest.mock import Mock, patch


class TestDatabaseConnection:
    """Tests for database connection functionality."""

    @patch('src.database.database.pool.ThreadedConnectionPool')
    def test_database_initialization(self, mock_pool, mock_env_vars):
        """Test database initialization creates connection pool."""
        from src.database.database import Database

        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance

        # Mock the connection for init_db
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool_instance.getconn.return_value = mock_conn

        db = Database()

        mock_pool.assert_called_once()
        assert db.connection_pool == mock_pool_instance


class TestQueueOperations:
    """Tests for queue management operations."""

    def test_add_to_queue(self):
        """Test adding a tweet to the queue."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = [42]  # Return queue_id
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            queue_id = db.add_to_queue(
                tweet_url="https://twitter.com/jack/status/20",
                tweet_id="20",
                user_name="test_user",
                chat_id="123456",
                bot_type="admin",
                priority=10
            )

            assert queue_id == 42
            mock_cursor.execute.assert_called()

    def test_get_next_pending(self):
        """Test getting next pending item from queue."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = (
                1, 'https://twitter.com/jack/status/20', '20',
                'user', '123', 'admin', 10, '2024-01-01 12:00:00'
            )
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            item = db.get_next_pending()

            assert item is not None
            assert item[0] == 1
            assert item[1] == 'https://twitter.com/jack/status/20'

    def test_mark_completed(self):
        """Test marking a queue item as completed."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            db.mark_completed(42)

            # Verify the UPDATE query was executed
            calls = mock_cursor.execute.call_args_list
            update_calls = [c for c in calls if 'completed' in str(c).lower()]
            assert len(update_calls) > 0

    def test_mark_failed(self):
        """Test marking a queue item as failed."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            db.mark_failed(42, "Test error message")

            # Verify the UPDATE query was executed with error message
            calls = mock_cursor.execute.call_args_list
            update_calls = [c for c in calls if 'failed' in str(c).lower()]
            assert len(update_calls) > 0

    def test_get_queue_position(self):
        """Test getting queue position for an item."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            # First call returns item data, second returns count
            mock_cursor.fetchone.side_effect = [(10, '2024-01-01 12:00:00'), [2]]
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            position = db.get_queue_position(42)

            assert position == 3  # 2 items ahead + 1


class TestTweetOperations:
    """Tests for tweet-related database operations."""

    def test_check_tweet_existence_exists(self):
        """Test checking if a tweet exists (positive case)."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = ['Success']
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            exists = db.check_tweet_existence("20")

            assert exists is True

    def test_check_tweet_existence_not_exists(self):
        """Test checking if a tweet exists (negative case)."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            exists = db.check_tweet_existence("20")

            assert exists is False

    def test_tweet_log(self):
        """Test logging a processed tweet."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            db.tweet_log({
                'tweet_id': '20',
                'tweet_text': 'Test tweet',
                'user_name': 'test_user',
                'status': 'Success',
                'admin': True
            })

            # Verify INSERT was called
            assert mock_cursor.execute.called


class TestErrorLogging:
    """Tests for error logging functionality."""

    def test_error_log(self):
        """Test logging an error."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            db.error_log(Exception("Test error"))

            # Verify INSERT was called with error details
            assert mock_cursor.execute.called


class TestRateLimiting:
    """Tests for user rate limiting functionality."""

    def test_get_user_tweet_count_last_hour(self):
        """Test getting user's tweet count in last hour."""
        with patch('src.database.database.pool.ThreadedConnectionPool') as mock_pool:
            from src.database.database import Database

            mock_pool_instance = Mock()
            mock_pool.return_value = mock_pool_instance

            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = [5]
            mock_conn.cursor.return_value = mock_cursor
            mock_pool_instance.getconn.return_value = mock_conn

            db = Database()

            count = db.get_user_tweet_count_last_hour("test_user")

            assert count == 5

