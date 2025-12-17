"""Tests for cloud conversation functionality."""

from unittest.mock import Mock, patch

import pytest

from openhands_cli.cloud.conversation import (
    CloudConversationError,
    check_user_authentication,
    create_cloud_conversation,
    extract_repository_from_cwd,
    validate_token,
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
        # Mock the remote URL call
        remote_mock = Mock()
        remote_mock.returncode = 0
        remote_mock.stdout = "git@github.com:username/repo.git\n"

        # Mock the branch call
        branch_mock = Mock()
        branch_mock.returncode = 0
        branch_mock.stdout = "main\n"

        mock_run.side_effect = [remote_mock, branch_mock]

        repository, branch = extract_repository_from_cwd()
        assert repository == "username/repo"
        assert branch == "main"


def test_extract_repository_from_cwd_github_https():
    """Test repository extraction from GitHub HTTPS URL."""
    with patch("subprocess.run") as mock_run:
        # Mock the remote URL call
        remote_mock = Mock()
        remote_mock.returncode = 0
        remote_mock.stdout = "https://github.com/username/repo.git\n"

        # Mock the branch call
        branch_mock = Mock()
        branch_mock.returncode = 0
        branch_mock.stdout = "develop\n"

        mock_run.side_effect = [remote_mock, branch_mock]

        repository, branch = extract_repository_from_cwd()
        assert repository == "username/repo"
        assert branch == "develop"


def test_extract_repository_from_cwd_branch_detection_fails():
    """Test repository extraction when branch detection fails."""
    with patch("subprocess.run") as mock_run:
        # Mock the remote URL call (success)
        remote_mock = Mock()
        remote_mock.returncode = 0
        remote_mock.stdout = "git@github.com:username/repo.git\n"

        # Mock the branch call (failure)
        branch_mock = Mock()
        branch_mock.returncode = 1

        mock_run.side_effect = [remote_mock, branch_mock]

        repository, branch = extract_repository_from_cwd()
        assert repository == "username/repo"
        assert branch is None


def test_extract_repository_from_cwd_not_git_repo():
    """Test repository extraction when not in a git repository."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1

        repository, branch = extract_repository_from_cwd()
        assert repository is None
        assert branch is None


def test_extract_repository_from_cwd_subprocess_error():
    """Test repository extraction when subprocess fails."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        repository, branch = extract_repository_from_cwd()
        assert repository is None
        assert branch is None


@pytest.mark.asyncio
async def test_validate_token_success():
    """Test successful token validation."""
    with patch(
        "openhands_cli.cloud.conversation.OpenHandsApiClient"
    ) as mock_client_class:
        mock_client = Mock()
        mock_client.get_user_info = Mock(return_value={"id": "user123"})
        mock_client_class.return_value = mock_client

        result = await validate_token("https://example.com", "valid-token")
        assert result is True
        mock_client.get_user_info.assert_called_once()


@pytest.mark.asyncio
async def test_validate_token_unauthenticated():
    """Test token validation with unauthenticated error."""
    from openhands_cli.auth.api_client import UnauthenticatedError

    with patch(
        "openhands_cli.cloud.conversation.OpenHandsApiClient"
    ) as mock_client_class:
        mock_client = Mock()
        mock_client.get_user_info.side_effect = UnauthenticatedError("Invalid token")
        mock_client_class.return_value = mock_client

        result = await validate_token("https://example.com", "invalid-token")
        assert result is False


@pytest.mark.asyncio
async def test_validate_token_other_error():
    """Test token validation with other errors."""
    with patch(
        "openhands_cli.cloud.conversation.OpenHandsApiClient"
    ) as mock_client_class:
        mock_client = Mock()
        mock_client.get_user_info.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        with pytest.raises(
            CloudConversationError, match="Failed to validate token: Network error"
        ):
            await validate_token("https://example.com", "token")


@pytest.mark.asyncio
async def test_create_cloud_conversation_token_validation_failure():
    """Test that token validation failure logs out user and raises error."""

    with patch(
        "openhands_cli.cloud.conversation.check_user_authentication"
    ) as mock_auth:
        mock_auth.return_value = "invalid-api-key"

        with patch("openhands_cli.cloud.conversation.validate_token") as mock_validate:
            mock_validate.return_value = False

            with patch(
                "openhands_cli.cloud.conversation.logout_command"
            ) as mock_logout:
                with patch("openhands_cli.cloud.conversation.console") as mock_console:
                    with pytest.raises(
                        CloudConversationError,
                        match="Authentication expired - user logged out",
                    ):
                        await create_cloud_conversation(
                            server_url="https://test.com",
                            initial_user_msg="Test message",
                        )

                    # Verify logout was called
                    mock_logout.assert_called_once_with("https://test.com")

                    # Verify appropriate messages were printed
                    print_calls = [
                        str(call) for call in mock_console.print.call_args_list
                    ]
                    assert any(
                        "connection with OpenHands Cloud has expired" in call
                        for call in print_calls
                    )
                    assert any("Logging you out" in call for call in print_calls)
                    assert any("openhands login" in call for call in print_calls)


@pytest.mark.asyncio
async def test_create_cloud_conversation_repository_extraction_error():
    """Test that repository extraction errors are logged but don't fail creation."""
    from unittest.mock import AsyncMock

    with patch(
        "openhands_cli.cloud.conversation.check_user_authentication"
    ) as mock_auth:
        mock_auth.return_value = "test-api-key"

        with patch("openhands_cli.cloud.conversation.validate_token") as mock_validate:
            mock_validate.return_value = True

            with patch(
                "openhands_cli.cloud.conversation.OpenHandsApiClient"
            ) as mock_client_class:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.json.return_value = {
                    "id": "test-id",
                    "url": "https://example.com",
                }
                mock_client.create_conversation = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                with patch(
                    "openhands_cli.cloud.conversation.extract_repository_from_cwd"
                ) as mock_extract:
                    mock_extract.side_effect = Exception("Git command failed")

                    with patch(
                        "openhands_cli.cloud.conversation.console"
                    ) as mock_console:
                        result = await create_cloud_conversation(
                            server_url="https://test.com",
                            initial_user_msg="Test message",
                        )

                        # Verify the warning was printed
                        warning_calls = [
                            call
                            for call in mock_console.print.call_args_list
                            if "Warning: Could not detect repository" in str(call)
                        ]
                        assert len(warning_calls) > 0, (
                            "Expected warning message not found"
                        )

                        # Verify conversation was still created successfully
                        assert result["id"] == "test-id"

                        # Verify API was called without repository
                        mock_client.create_conversation.assert_called_once_with(
                            json_data={"initial_user_msg": "Test message"},
                        )


@pytest.mark.asyncio
async def test_create_cloud_conversation_with_repository_and_branch():
    """Test that repository and branch are included when detected."""
    from unittest.mock import AsyncMock

    with patch(
        "openhands_cli.cloud.conversation.check_user_authentication"
    ) as mock_auth:
        mock_auth.return_value = "test-api-key"

        with patch("openhands_cli.cloud.conversation.validate_token") as mock_validate:
            mock_validate.return_value = True

            with patch(
                "openhands_cli.cloud.conversation.OpenHandsApiClient"
            ) as mock_client_class:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.json.return_value = {
                    "conversation_id": "test-conversation-id",
                    "url": "https://example.com",
                }
                mock_client.create_conversation = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                with patch(
                    "openhands_cli.cloud.conversation.extract_repository_from_cwd"
                ) as mock_extract:
                    mock_extract.return_value = ("username/repo", "feature-branch")

                    with patch("openhands_cli.cloud.conversation.console"):
                        result = await create_cloud_conversation(
                            server_url="https://test.com",
                            initial_user_msg="Test message",
                        )

                        # Verify conversation was created successfully
                        assert result["conversation_id"] == "test-conversation-id"

                        # Verify API was called with repository and selected_branch
                        mock_client.create_conversation.assert_called_once_with(
                            json_data={
                                "initial_user_msg": "Test message",
                                "repository": "username/repo",
                                "selected_branch": "feature-branch",
                            },
                        )


@pytest.mark.asyncio
async def test_create_cloud_conversation_with_repository_only():
    """Test that only repository is included when branch detection fails."""
    from unittest.mock import AsyncMock

    with patch(
        "openhands_cli.cloud.conversation.check_user_authentication"
    ) as mock_auth:
        mock_auth.return_value = "test-api-key"

        with patch("openhands_cli.cloud.conversation.validate_token") as mock_validate:
            mock_validate.return_value = True

            with patch(
                "openhands_cli.cloud.conversation.OpenHandsApiClient"
            ) as mock_client_class:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.json.return_value = {
                    "conversation_id": "test-conversation-id",
                    "url": "https://example.com",
                }
                mock_client.create_conversation = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                with patch(
                    "openhands_cli.cloud.conversation.extract_repository_from_cwd"
                ) as mock_extract:
                    mock_extract.return_value = ("username/repo", None)

                    with patch("openhands_cli.cloud.conversation.console"):
                        result = await create_cloud_conversation(
                            server_url="https://test.com",
                            initial_user_msg="Test message",
                        )

                        # Verify conversation was created successfully
                        assert result["conversation_id"] == "test-conversation-id"

                        # Verify API was called with repository but no selected_branch
                        mock_client.create_conversation.assert_called_once_with(
                            json_data={
                                "initial_user_msg": "Test message",
                                "repository": "username/repo",
                            },
                        )
