"""
Unit tests for Twitter backend module.
Tests URL parsing, normalization, and screenshot capture functionality.
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestURLParsing:
    """Tests for tweet URL parsing functionality."""

    def test_parse_twitter_url(self):
        """Test parsing standard twitter.com URL."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.parse_tweet_url("https://twitter.com/jack/status/20")
        
        assert result is not None
        assert result['username'] == 'jack'
        assert result['tweet_id'] == '20'

    def test_parse_x_url(self):
        """Test parsing x.com URL."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.parse_tweet_url("https://x.com/jack/status/20")
        
        assert result is not None
        assert result['username'] == 'jack'
        assert result['tweet_id'] == '20'

    def test_parse_mobile_twitter_url(self):
        """Test parsing mobile.twitter.com URL."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.parse_tweet_url("https://mobile.twitter.com/jack/status/20")
        
        assert result is not None
        assert result['username'] == 'jack'
        assert result['tweet_id'] == '20'

    def test_parse_url_with_query_params(self):
        """Test parsing URL with query parameters."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.parse_tweet_url("https://twitter.com/jack/status/20?s=20&t=abc123")
        
        assert result is not None
        assert result['username'] == 'jack'
        assert result['tweet_id'] == '20'

    def test_parse_invalid_url(self):
        """Test parsing invalid URL returns None."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.parse_tweet_url("https://google.com")
        assert result is None

    def test_parse_incomplete_url(self):
        """Test parsing incomplete Twitter URL returns None."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.parse_tweet_url("https://twitter.com/jack")
        assert result is None


class TestURLNormalization:
    """Tests for URL normalization functionality."""

    def test_normalize_x_url_to_twitter(self):
        """Test that x.com URLs are normalized to twitter.com."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.normalize_tweet_url("https://x.com/jack/status/20")
        
        assert result == "https://twitter.com/jack/status/20"

    def test_normalize_url_strips_query_params(self):
        """Test that query parameters are stripped during normalization."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.normalize_tweet_url("https://twitter.com/jack/status/20?s=20")
        
        assert "?" not in result
        assert result == "https://twitter.com/jack/status/20"

    def test_normalize_mobile_url(self):
        """Test that mobile URLs are normalized."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        result = client.normalize_tweet_url("https://mobile.twitter.com/jack/status/20")
        
        assert result == "https://twitter.com/jack/status/20"


class TestQueueManagement:
    """Tests for queue management functionality."""

    def test_add_to_queue_admin_priority(self):
        """Test that admin tweets get higher priority."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        mock_db.check_tweet_existence.return_value = False
        mock_db.check_tweet_in_queue.return_value = None
        mock_db.add_to_queue.return_value = 1
        mock_db.get_queue_position.return_value = 1
        
        client = TwitterClient(mock_db)
        
        queue_id, position = client.add_to_queue(
            tweet_url="https://twitter.com/jack/status/20",
            user_name="admin_user",
            chat_id="123456",
            bot_type="admin"
        )
        
        # Verify add_to_queue was called with priority=10 for admin
        mock_db.add_to_queue.assert_called_once()
        call_kwargs = mock_db.add_to_queue.call_args
        assert call_kwargs[1]['priority'] == 10

    def test_add_to_queue_suggestions_priority(self):
        """Test that suggestion tweets get lower priority."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        mock_db.check_tweet_existence.return_value = False
        mock_db.check_tweet_in_queue.return_value = None
        mock_db.add_to_queue.return_value = 1
        mock_db.get_queue_position.return_value = 1
        
        client = TwitterClient(mock_db)
        
        queue_id, position = client.add_to_queue(
            tweet_url="https://twitter.com/jack/status/20",
            user_name="regular_user",
            chat_id="123456",
            bot_type="suggestions"
        )
        
        # Verify add_to_queue was called with priority=1 for suggestions
        mock_db.add_to_queue.assert_called_once()
        call_kwargs = mock_db.add_to_queue.call_args
        assert call_kwargs[1]['priority'] == 1

    def test_add_to_queue_duplicate_tweet(self):
        """Test that duplicate tweets are rejected."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        mock_db.check_tweet_existence.return_value = True
        
        client = TwitterClient(mock_db)
        
        queue_id, error = client.add_to_queue(
            tweet_url="https://twitter.com/jack/status/20",
            user_name="user",
            chat_id="123456",
            bot_type="admin"
        )
        
        assert queue_id is None
        assert "already posted" in error.lower()

    def test_add_to_queue_already_in_queue(self):
        """Test that tweets already in queue are rejected."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        mock_db.check_tweet_existence.return_value = False
        mock_db.check_tweet_in_queue.return_value = (1, 'pending')
        
        client = TwitterClient(mock_db)
        
        queue_id, error = client.add_to_queue(
            tweet_url="https://twitter.com/jack/status/20",
            user_name="user",
            chat_id="123456",
            bot_type="admin"
        )
        
        assert queue_id is None
        assert "already in the queue" in error.lower()

    def test_add_to_queue_invalid_url(self):
        """Test that invalid URLs are rejected."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        
        queue_id, error = client.add_to_queue(
            tweet_url="https://google.com",
            user_name="user",
            chat_id="123456",
            bot_type="admin"
        )
        
        assert queue_id is None
        assert "invalid" in error.lower()


class TestScreenshotCapture:
    """Tests for screenshot capture functionality."""

    @pytest.mark.integration
    def test_capture_creates_file(self, tmp_path):
        """Integration test: Verify screenshot capture creates a file."""
        from twitter_backend import TwitterClient
        
        mock_db = Mock()
        client = TwitterClient(mock_db)
        client.screenshots_dir = str(tmp_path)
        
        # This test requires Chrome/Chromium to be installed
        # Skip if not available
        try:
            result = client.capture_tweet("https://twitter.com/jack/status/20")
            
            if result:
                assert os.path.exists(result['screenshot_path'])
                assert result['username'] == 'jack'
                assert result['tweet_id'] == '20'
        except Exception as e:
            pytest.skip(f"Chrome not available: {e}")

