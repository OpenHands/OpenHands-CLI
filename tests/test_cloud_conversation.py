"""Tests for cloud conversation functionality."""

import pytest
from unittest.mock import Mock, patch

from openhands_cli.cloud.conversation import (
    CloudConversationError,
    check_user_authentication,
    extract_repository_from_cwd,
)


def test_check_user_authentication_no_api_key():
    """Test authentication check when no API key is stored."""
    with patch("openhands_cli.cloud.conversation.TokenStorage") as mock_storage_class:
        mock_storage = Mock()
        mock_storage.has_api_key.return_value = False
        mock_storage_class.return_value = mock_storage
        
        with pytest.raises(CloudConversationError, match="User not authenticated"):
            check_user_authentication("https://example.com")


def test_check_user_authentication_invalid_api_key():
    """Test authentication check when API key is invalid."""
    with patch("openhands_cli.cloud.conversation.TokenStorage") as mock_storage_class:
        mock_storage = Mock()
        mock_storage.has_api_key.return_value = True
        mock_storage.get_api_key.return_value = None
        mock_storage_class.return_value = mock_storage
        
        with pytest.raises(CloudConversationError, match="Invalid API key"):
            check_user_authentication("https://example.com")


def test_check_user_authentication_valid_api_key():
    """Test authentication check when API key is valid."""
    with patch("openhands_cli.cloud.conversation.TokenStorage") as mock_storage_class:
        mock_storage = Mock()
        mock_storage.has_api_key.return_value = True
        mock_storage.get_api_key.return_value = "valid-api-key"
        mock_storage_class.return_value = mock_storage
        
        result = check_user_authentication("https://example.com")
        assert result == "valid-api-key"


def test_extract_repository_from_cwd_github_ssh():
    """Test repository extraction from GitHub SSH URL."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "git@github.com:username/repo.git\n"
        
        result = extract_repository_from_cwd()
        assert result == "username/repo"


def test_extract_repository_from_cwd_github_https():
    """Test repository extraction from GitHub HTTPS URL."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "https://github.com/username/repo.git\n"
        
        result = extract_repository_from_cwd()
        assert result == "username/repo"


def test_extract_repository_from_cwd_not_git_repo():
    """Test repository extraction when not in a git repository."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        
        result = extract_repository_from_cwd()
        assert result is None


def test_extract_repository_from_cwd_subprocess_error():
    """Test repository extraction when subprocess fails."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = extract_repository_from_cwd()
        assert result is None