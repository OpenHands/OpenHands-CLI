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


@pytest.mark.parametrize(
    "has_api_key,api_key_value,expected_result,expected_error,error_message",
    [
        (False, None, None, CloudConversationError, "User not authenticated"),
        (True, None, None, CloudConversationError, "Invalid API key"),
        (True, "valid-api-key", "valid-api-key", None, None),
    ],
)
def test_check_user_authentication(
    has_api_key, api_key_value, expected_result, expected_error, error_message
):
    """Test authentication check with various API key scenarios."""
    with patch("openhands_cli.cloud.conversation.TokenStorage") as mock_storage_class:
        mock_storage = Mock()
        mock_storage.has_api_key.return_value = has_api_key
        mock_storage.get_api_key.return_value = api_key_value
        mock_storage_class.return_value = mock_storage

        if expected_error:
            with pytest.raises(expected_error, match=error_message):
                check_user_authentication("https://example.com")
        else:
            result = check_user_authentication("https://example.com")
            assert result == expected_result


@pytest.mark.parametrize(
    "remote_url,branch_name,branch_success,expected_repo,expected_branch,test_description",
    [
        (
            "git@github.com:username/repo.git\n",
            "main\n",
            True,
            "username/repo",
            "main",
            "GitHub SSH URL with successful branch detection",
        ),
        (
            "https://github.com/username/repo.git\n",
            "develop\n",
            True,
            "username/repo",
            "develop",
            "GitHub HTTPS URL with successful branch detection",
        ),
        (
            "git@github.com:username/repo.git\n",
            None,
            False,
            "username/repo",
            None,
            "successful remote URL but branch detection fails",
        ),
    ],
)
def test_extract_repository_from_cwd_success_cases(
    remote_url,
    branch_name,
    branch_success,
    expected_repo,
    expected_branch,
    test_description,
):
    """Test repository extraction from various URL formats and branch scenarios."""
    with patch("subprocess.run") as mock_run:
        # Mock the remote URL call (always successful for these cases)
        remote_mock = Mock()
        remote_mock.returncode = 0
        remote_mock.stdout = remote_url

        # Mock the branch call
        branch_mock = Mock()
        branch_mock.returncode = 0 if branch_success else 1
        if branch_success:
            branch_mock.stdout = branch_name

        mock_run.side_effect = [remote_mock, branch_mock]

        repository, branch = extract_repository_from_cwd()
        assert repository == expected_repo, f"Failed for {test_description}"
        assert branch == expected_branch, f"Failed for {test_description}"


@pytest.mark.parametrize(
    "mock_setup,test_description",
    [
        (
            lambda mock_run: setattr(mock_run.return_value, "returncode", 1),
            "not in a git repository",
        ),
        (
            lambda mock_run: None,  # Will use side_effect instead
            "subprocess fails with FileNotFoundError",
        ),
    ],
)
def test_extract_repository_from_cwd_error_cases(mock_setup, test_description):
    """Test repository extraction error scenarios."""
    if "FileNotFoundError" in test_description:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            repository, branch = extract_repository_from_cwd()
            assert repository is None, f"Failed for {test_description}"
            assert branch is None, f"Failed for {test_description}"
    else:
        with patch("subprocess.run") as mock_run:
            mock_setup(mock_run)
            repository, branch = extract_repository_from_cwd()
            assert repository is None, f"Failed for {test_description}"
            assert branch is None, f"Failed for {test_description}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_side_effect,expected_result,expected_exception,exception_message",
    [
        (None, True, None, None),  # Success case - return_value will be set
        (
            "UnauthenticatedError",
            False,
            None,
            None,
        ),  # Unauthenticated case - returns False
        (
            Exception("Network error"),
            None,
            CloudConversationError,
            "Failed to validate token: Network error",
        ),  # Other error case
    ],
)
async def test_validate_token(
    mock_side_effect, expected_result, expected_exception, exception_message
):
    """Test token validation with various scenarios."""
    from unittest.mock import AsyncMock

    from openhands_cli.auth.api_client import UnauthenticatedError

    with patch(
        "openhands_cli.cloud.conversation.OpenHandsApiClient"
    ) as mock_client_class:
        mock_client = Mock()

        if mock_side_effect == "UnauthenticatedError":
            mock_client.get_user_info = AsyncMock(
                side_effect=UnauthenticatedError("Invalid token")
            )
        elif mock_side_effect is None:
            mock_client.get_user_info = AsyncMock(return_value={"id": "user123"})
        else:
            mock_client.get_user_info = AsyncMock(side_effect=mock_side_effect)

        mock_client_class.return_value = mock_client

        if expected_exception:
            with pytest.raises(expected_exception, match=exception_message):
                await validate_token("https://example.com", "test-token")
        else:
            result = await validate_token("https://example.com", "test-token")
            assert result is expected_result
            mock_client.get_user_info.assert_called_once()


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
