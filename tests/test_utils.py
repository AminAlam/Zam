"""
Unit tests for utility functions.
"""
import datetime as dt


class TestLoadCredentials:
    """Tests for credential loading functionality."""

    def test_load_credentials_from_env(self, mock_env_vars):
        """Test loading credentials from environment variables."""
        from src.utils import load_credentials

        creds = load_credentials()

        assert creds['ADMIN_TELEGRAM_BOT'] == 'test_admin_token'
        assert creds['SUGGESTIONS_TELEGRAM_BOT'] == 'test_suggestions_token'
        assert creds['MAIN_CHANNEL_CHAT_ID'] == '-1001234567890'
        assert creds['ADMIN_CHAT_ID'] == '-1009876543210'
        assert creds['SUGGESTIONS_CHAT_ID'] == '-1001111111111'
        assert creds['CHANNEL_NAME'] == '@TestChannel'

    def test_load_credentials_admin_ids_parsing(self, mock_env_vars):
        """Test that ADMIN_IDS are correctly parsed as a list."""
        from src.utils import load_credentials

        creds = load_credentials()

        assert isinstance(creds['ADMIN_IDS'], list)
        assert len(creds['ADMIN_IDS']) == 3
        assert 'admin1' in creds['ADMIN_IDS']
        assert 'admin2' in creds['ADMIN_IDS']
        assert 'admin3' in creds['ADMIN_IDS']

    def test_load_credentials_empty_admin_ids(self, monkeypatch):
        """Test handling of empty ADMIN_IDS."""
        monkeypatch.setenv('ADMIN_IDS', '')
        monkeypatch.setenv('ADMIN_TELEGRAM_BOT', 'token')
        monkeypatch.setenv('SUGGESTIONS_TELEGRAM_BOT', 'token')
        monkeypatch.setenv('MAIN_CHANNEL_CHAT_ID', 'id')
        monkeypatch.setenv('ADMIN_CHAT_ID', 'id')
        monkeypatch.setenv('SUGGESTIONS_CHAT_ID', 'id')
        monkeypatch.setenv('CHANNEL_NAME', '@test')

        from src.utils import load_credentials

        creds = load_credentials()

        assert creds['ADMIN_IDS'] == []


class TestDateConversion:
    """Tests for date conversion utilities."""

    def test_convert_tweet_time_to_desired_time(self):
        """Test converting tweet time with timezone offset."""
        from src.utils import covert_tweet_time_to_desired_time

        date_str = "2024-01-15 12:00:00"
        time_diff = {'hours': '3', 'minutes': '30'}

        result = covert_tweet_time_to_desired_time(date_str, time_diff)

        # Result should include Persian date and time
        assert '15:30:00' in result  # Time should be offset by 3:30
        assert '/' in result  # Persian date format

    def test_convert_tweet_time_zero_offset(self):
        """Test date conversion with zero offset."""
        from src.utils import covert_tweet_time_to_desired_time

        date_str = "2024-01-15 12:00:00"
        time_diff = {'hours': '0', 'minutes': '0'}

        result = covert_tweet_time_to_desired_time(date_str, time_diff)

        assert '12:00:00' in result


class TestTimeCounterMessage:
    """Tests for time counter message formatting."""

    def test_form_time_counter_message(self):
        """Test time counter message formatting."""
        from src.utils import form_time_counter_message

        diff_time = dt.timedelta(days=100, hours=5, minutes=30)
        message_txt = "minutes since the event."

        result = form_time_counter_message(diff_time, message_txt)

        assert "100 days" in result
        assert "5 hours" in result
        assert "30" in result
        assert "minutes since the event" in result


class TestParseText:
    """Tests for text parsing utility."""

    def test_parse_text_removes_tco_links(self):
        """Test that t.co links are removed from text."""
        from src.utils import parse_text

        text = "Check this out https://t.co/abcd123456"
        result = parse_text(text)

        assert "t.co" not in result

    def test_parse_text_converts_urls_to_links(self):
        """Test that URLs are converted to HTML links."""
        from src.utils import parse_text

        text = "Visit https://example.com for more"
        result = parse_text(text)

        assert '<a href="https://example.com">' in result
        assert 'Link</a>' in result

    def test_parse_text_converts_mentions_to_links(self):
        """Test that @mentions are converted to Twitter links."""
        from src.utils import parse_text

        text = "Thanks @jack for the tweet!"
        result = parse_text(text)

        assert '<a href="https://twitter.com/jack">' in result
        assert 'jack</a>' in result


class TestDeletedSnapshots:
    """Tests for screenshot cleanup utility."""

    def test_deleted_snapshots_removes_local_files(self, tmp_path):
        """Test that local screenshot files are deleted."""
        from src.utils import deleted_snapshots

        # Create a temporary file
        test_file = tmp_path / "test_screenshot.png"
        test_file.write_text("dummy content")

        media_list = [[str(test_file), 'photo']]

        assert test_file.exists()
        deleted_snapshots(media_list)
        assert not test_file.exists()

    def test_deleted_snapshots_ignores_urls(self):
        """Test that URL media items are not processed."""
        from src.utils import deleted_snapshots

        media_list = [['https://example.com/image.png', 'photo']]

        # Should not raise any errors
        deleted_snapshots(media_list)

    def test_deleted_snapshots_handles_empty_list(self):
        """Test handling of empty media list."""
        from src.utils import deleted_snapshots

        # Should not raise any errors
        deleted_snapshots([])
        deleted_snapshots(None)

