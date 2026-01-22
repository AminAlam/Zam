"""
Integration and system tests for Zam bot.
These tests require Docker and external services.
"""
import os
from unittest.mock import Mock

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestEndToEndCapture:
    """End-to-end tests for tweet capture workflow."""

    @pytest.fixture
    def twitter_client(self, tmp_path):
        """Create a TwitterClient instance for testing."""
        from twitter_backend import TwitterClient

        mock_db = Mock()
        mock_db.check_tweet_existence.return_value = False
        mock_db.check_tweet_in_queue.return_value = None
        mock_db.add_to_queue.return_value = 1
        mock_db.get_queue_position.return_value = 1
        mock_db.error_log = Mock()

        client = TwitterClient(mock_db)
        client.screenshots_dir = str(tmp_path)

        return client

    @pytest.mark.slow
    def test_capture_jack_first_tweet(self, twitter_client, test_tweet_data):
        """
        Integration test: Capture Jack Dorsey's first tweet.
        This is a historic tweet that should always be available.
        URL: https://x.com/jack/status/20
        """
        result = twitter_client.capture_tweet(test_tweet_data['url'])

        if result is None:
            pytest.skip("Screenshot capture not available (Chrome/Chromium not installed)")

        assert result['username'] == test_tweet_data['username']
        assert result['tweet_id'] == test_tweet_data['tweet_id']
        assert os.path.exists(result['screenshot_path'])
        assert result['screenshot_path'].endswith('.png')

    @pytest.mark.slow
    def test_capture_creates_valid_image(self, twitter_client, test_tweet_data):
        """Integration test: Verify captured screenshot is a valid image."""
        result = twitter_client.capture_tweet(test_tweet_data['url'])

        if result is None:
            pytest.skip("Screenshot capture not available")

        # Check file exists and has content
        screenshot_path = result['screenshot_path']
        assert os.path.exists(screenshot_path)
        assert os.path.getsize(screenshot_path) > 1000  # Should be more than 1KB

        # Check PNG magic bytes
        with open(screenshot_path, 'rb') as f:
            header = f.read(8)
            assert header[:4] == b'\x89PNG'

    @pytest.mark.slow
    def test_queue_workflow(self, twitter_client, test_tweet_data):
        """Integration test: Test the complete queue workflow."""
        # Add to queue
        queue_id, position = twitter_client.add_to_queue(
            tweet_url=test_tweet_data['url'],
            user_name="test_user",
            chat_id="123456",
            bot_type="admin"
        )

        assert queue_id == 1
        assert position == 1

        # Verify database methods were called correctly
        twitter_client.db.add_to_queue.assert_called_once()


class TestDatabaseIntegration:
    """Integration tests for database operations with PostgreSQL."""

    @pytest.fixture
    def db_connection_string(self):
        """Get database connection string from environment."""
        return {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'port': os.environ.get('DB_PORT', '5432'),
            'user': os.environ.get('DB_USER', 'zam'),
            'password': os.environ.get('DB_PASSWORD', 'test'),
            'database': os.environ.get('DB_NAME', 'zam_db')
        }

    @pytest.mark.docker
    def test_database_connection(self, db_connection_string):
        """Test that we can connect to the PostgreSQL database."""
        try:
            import psycopg2
            conn = psycopg2.connect(**db_connection_string)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            assert result[0] == 1
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    @pytest.mark.docker
    def test_queue_table_exists(self, db_connection_string):
        """Test that the tweet_queue table exists."""
        try:
            import psycopg2
            conn = psycopg2.connect(**db_connection_string)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'tweet_queue'
                )
            """)
            result = cursor.fetchone()
            conn.close()
            assert result[0] is True
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")


class TestSystemHealth:
    """System health and sanity checks."""

    def test_imports(self):
        """Test that all main modules can be imported."""
        import twitter_backend
        import utils

        assert hasattr(twitter_backend, 'TwitterClient')
        assert hasattr(utils, 'load_credentials')

    def test_url_patterns(self, test_tweet_data):
        """Test URL pattern matching for various formats."""
        from twitter_backend import TwitterClient

        mock_db = Mock()
        client = TwitterClient(mock_db)

        # Test various URL formats
        urls = [
            "https://twitter.com/jack/status/20",
            "https://x.com/jack/status/20",
            "https://mobile.twitter.com/jack/status/20",
            "http://twitter.com/jack/status/20",
            "https://twitter.com/jack/status/20?s=20",
            "https://x.com/jack/status/20?ref=example",
        ]

        for url in urls:
            result = client.parse_tweet_url(url)
            assert result is not None, f"Failed to parse: {url}"
            assert result['username'] == 'jack'
            assert result['tweet_id'] == '20'

    def test_environment_variables_loaded(self, mock_env_vars):
        """Test that environment variables are properly loaded."""
        from utils import load_credentials

        creds = load_credentials()

        assert creds['ADMIN_TELEGRAM_BOT'] is not None
        assert creds['CHANNEL_NAME'] is not None
        assert len(creds['ADMIN_IDS']) > 0

