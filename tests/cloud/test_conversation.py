"""Tests for cloud conversation functionality (updated for simplified code)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from openhands_cli.auth.utils import (
    AuthenticationError,
    ensure_valid_auth,
    is_token_valid,
)
from openhands_cli.cloud.conversation import (
    CloudConversationError,
    create_cloud_conversation,
    extract_repository_from_cwd,
)


# ----------------------------
# is_token_valid
# ----------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect,expected",
    [
        (None, True),
        ("UnauthenticatedError", False),
    ],
)
async def test_is_token_valid(side_effect, expected):
    from openhands_cli.auth.api_client import UnauthenticatedError

    with patch("openhands_cli.auth.api_client.OpenHandsApiClient") as mock_client_cls:
        client = Mock()

        if side_effect is None:
            client.get_user_info = AsyncMock(return_value={"id": "user"})
        elif side_effect == "UnauthenticatedError":
            client.get_user_info = AsyncMock(
                side_effect=UnauthenticatedError("bad token")
            )

        mock_client_cls.return_value = client

        assert await is_token_valid("https://example.com", "token") is expected
        client.get_user_info.assert_called_once()


@pytest.mark.asyncio
async def test_is_token_valid_propagates_other_exceptions():
    """Other exceptions (e.g., network errors) should propagate naturally."""
    with patch("openhands_cli.auth.api_client.OpenHandsApiClient") as mock_client_cls:
        client = Mock()
        client.get_user_info = AsyncMock(side_effect=Exception("Network error"))
        mock_client_cls.return_value = client

        with pytest.raises(Exception, match="Network error"):
            await is_token_valid("https://example.com", "token")


# ----------------------------
# ensure_valid_auth
# ----------------------------


@pytest.mark.asyncio
async def test_ensure_valid_auth_returns_existing_valid_key():
    """If API key exists and is valid, return it without calling login."""
    with (
        patch("openhands_cli.auth.token_storage.TokenStorage") as mock_store_cls,
        patch(
            "openhands_cli.auth.utils.is_token_valid",
            return_value=True,
        ),
        patch("openhands_cli.auth.login_command.login_command") as mock_login,
    ):
        store = Mock()
        store.get_api_key.return_value = "valid-key"
        mock_store_cls.return_value = store

        result = await ensure_valid_auth("https://server")
        assert result == "valid-key"
        mock_login.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_valid_auth_runs_login_when_no_key():
    """If no API key exists, run login command."""
    with (
        patch("openhands_cli.auth.token_storage.TokenStorage") as mock_store_cls,
        patch(
            "openhands_cli.auth.utils.is_token_valid",
            return_value=True,
        ),
        patch(
            "openhands_cli.auth.login_command.login_command",
            return_value=True,
        ) as mock_login,
    ):
        store = Mock()
        store.get_api_key.side_effect = [None, "new-key"]
        mock_store_cls.return_value = store

        result = await ensure_valid_auth("https://server")
        assert result == "new-key"
        mock_login.assert_called_once_with("https://server")


@pytest.mark.asyncio
async def test_ensure_valid_auth_runs_login_when_token_invalid():
    """If token is invalid, run login command."""
    with (
        patch("openhands_cli.auth.token_storage.TokenStorage") as mock_store_cls,
        patch(
            "openhands_cli.auth.utils.is_token_valid",
            return_value=False,
        ),
        patch(
            "openhands_cli.auth.login_command.login_command",
            return_value=True,
        ) as mock_login,
    ):
        store = Mock()
        store.get_api_key.side_effect = ["expired-key", "new-key"]
        mock_store_cls.return_value = store

        result = await ensure_valid_auth("https://server")
        assert result == "new-key"
        mock_login.assert_called_once_with("https://server")


@pytest.mark.asyncio
async def test_ensure_valid_auth_raises_on_login_failure():
    """If login fails, raise AuthenticationError."""
    with (
        patch("openhands_cli.auth.token_storage.TokenStorage") as mock_store_cls,
        patch(
            "openhands_cli.auth.utils.is_token_valid",
            return_value=False,
        ),
        patch(
            "openhands_cli.auth.login_command.login_command",
            return_value=False,
        ),
    ):
        store = Mock()
        store.get_api_key.return_value = "expired-key"
        mock_store_cls.return_value = store

        with pytest.raises(AuthenticationError, match="Login failed"):
            await ensure_valid_auth("https://server")


# ----------------------------
# extract_repository_from_cwd
# ----------------------------


@pytest.mark.parametrize(
    "remote,expected_repo",
    [
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("https://gitlab.com/owner/repo.git", "owner/repo"),
    ],
)
def test_extract_repository_from_cwd_parses_repo_and_branch(remote, expected_repo):
    with (
        patch("openhands_cli.cloud.conversation._run_git") as run_git,
    ):
        run_git.side_effect = [remote, "feature-branch"]
        repo, branch = extract_repository_from_cwd()
        assert repo == expected_repo
        assert branch == "feature-branch"


@pytest.mark.parametrize(
    "remote,reason",
    [
        (None, "no origin remote"),
        ("https://bitbucket.org/owner/repo.git", "unsupported host"),
    ],
)
def test_extract_repository_from_cwd_returns_none_when_unusable(remote, reason):
    with (
        patch("openhands_cli.cloud.conversation._run_git") as run_git,
    ):
        run_git.side_effect = [
            remote
        ]  # only remote called; branch should not be needed
        repo, branch = extract_repository_from_cwd()
        assert repo is None and branch is None, reason


def test_extract_repository_from_cwd_branch_missing_is_ok():
    with (
        patch("openhands_cli.cloud.conversation._run_git") as run_git,
    ):
        run_git.side_effect = ["https://github.com/owner/repo.git", None]
        repo, branch = extract_repository_from_cwd()
        assert repo == "owner/repo"
        assert branch is None


# ----------------------------
# create_cloud_conversation
# ----------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repo_branch,expected_payload",
    [
        (
            (None, None),
            {"initial_message": {"content": [{"type": "text", "text": "hi"}]}},
        ),
        (
            ("owner/repo", None),
            {
                "initial_message": {"content": [{"type": "text", "text": "hi"}]},
                "selected_repository": "owner/repo",
            },
        ),
        (
            ("owner/repo", "main"),
            {
                "initial_message": {"content": [{"type": "text", "text": "hi"}]},
                "selected_repository": "owner/repo",
                "selected_branch": "main",
            },
        ),
    ],
)
async def test_create_cloud_conversation_payload_includes_repo_and_branch(
    repo_branch, expected_payload
):
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=repo_branch,
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"id": "c1", "app_conversation_id": "ac1"}
        client.create_conversation = AsyncMock(return_value=resp)
        mock_client_cls.return_value = client

        result = await create_cloud_conversation("https://server", "key", "hi")
        assert result["id"] == "c1"
        client.create_conversation.assert_called_once_with(json_data=expected_payload)


@pytest.mark.asyncio
async def test_create_cloud_conversation_propagates_api_error_as_cloud_error():
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        client.create_conversation = AsyncMock(side_effect=Exception("boom"))
        mock_client_cls.return_value = client

        with pytest.raises(
            CloudConversationError, match=r"Failed to create conversation: boom"
        ):
            await create_cloud_conversation("https://server", "key", "hi")


@pytest.mark.asyncio
async def test_create_cloud_conversation_polls_for_app_conversation_id():
    """When app_conversation_id is None initially, poll start-tasks until ready."""
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"id": "t1", "app_conversation_id": None}
        client.create_conversation = AsyncMock(return_value=resp)
        client.get_start_task_status = AsyncMock(
            side_effect=[
                {"id": "t1", "status": "WORKING", "app_conversation_id": None},
                {"id": "t1", "status": "READY", "app_conversation_id": "ac1"},
            ]
        )
        mock_client_cls.return_value = client

        result = await create_cloud_conversation(
            "https://server", "key", "hi", poll_interval=0
        )
        assert result["id"] == "t1"
        assert client.get_start_task_status.call_count == 2


@pytest.mark.asyncio
async def test_create_cloud_conversation_raises_on_start_task_error():
    """When start-task status is ERROR, raise CloudConversationError."""
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"id": "t1", "app_conversation_id": None}
        client.create_conversation = AsyncMock(return_value=resp)
        client.get_start_task_status = AsyncMock(
            return_value={
                "id": "t1",
                "status": "ERROR",
                "detail": "sandbox failed",
                "app_conversation_id": None,
            }
        )
        mock_client_cls.return_value = client

        with pytest.raises(CloudConversationError, match="sandbox failed"):
            await create_cloud_conversation(
                "https://server", "key", "hi", poll_interval=0
            )


@pytest.mark.asyncio
async def test_create_cloud_conversation_polls_timeout_falls_back_to_task_id():
    """When polling exhausts all attempts, fall back to task_id for the URL."""
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"id": "t1", "app_conversation_id": None}
        client.create_conversation = AsyncMock(return_value=resp)
        client.get_start_task_status = AsyncMock(
            return_value={"id": "t1", "status": "WORKING", "app_conversation_id": None}
        )
        mock_client_cls.return_value = client

        result = await create_cloud_conversation(
            "https://server", "key", "hi", poll_interval=0, poll_max_attempts=2
        )
        assert result["id"] == "t1"
        assert client.get_start_task_status.call_count == 2


@pytest.mark.asyncio
async def test_create_cloud_conversation_timeout_shows_warning(capsys):
    """When polling times out, print a warning about the link."""
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"id": "t1", "app_conversation_id": None}
        client.create_conversation = AsyncMock(return_value=resp)
        client.get_start_task_status = AsyncMock(
            return_value={"id": "t1", "status": "WORKING", "app_conversation_id": None}
        )
        mock_client_cls.return_value = client

        await create_cloud_conversation(
            "https://server", "key", "hi", poll_interval=0, poll_max_attempts=1
        )
        output = capsys.readouterr().out
        assert "still initializing" in output


@pytest.mark.asyncio
async def test_create_cloud_conversation_poll_handles_none_task_info():
    """When get_start_task_status returns None, keep polling."""
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"id": "t1", "app_conversation_id": None}
        client.create_conversation = AsyncMock(return_value=resp)
        client.get_start_task_status = AsyncMock(
            side_effect=[
                None,
                {"id": "t1", "status": "READY", "app_conversation_id": "ac1"},
            ]
        )
        mock_client_cls.return_value = client

        result = await create_cloud_conversation(
            "https://server", "key", "hi", poll_interval=0
        )
        assert result["id"] == "t1"
        assert client.get_start_task_status.call_count == 2


@pytest.mark.asyncio
async def test_create_cloud_conversation_skips_polling_when_no_task_id():
    """When response has no id at all, skip polling entirely."""
    with (
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=(None, None),
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {}
        client.create_conversation = AsyncMock(return_value=resp)
        client.get_start_task_status = AsyncMock()
        mock_client_cls.return_value = client

        result = await create_cloud_conversation("https://server", "key", "hi")
        assert result == {}
        client.get_start_task_status.assert_not_called()
