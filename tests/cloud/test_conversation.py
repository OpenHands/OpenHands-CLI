"""Tests for cloud conversation functionality (updated for simplified code)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from openhands_cli.cloud.conversation import (
    CloudConversationError,
    create_cloud_conversation,
    extract_repository_from_cwd,
    is_token_valid,
    require_api_key,
)


# ----------------------------
# require_api_key
# ----------------------------


@pytest.mark.parametrize(
    "has_api_key,stored_key,expect_exc,exc_msg",
    [
        (False, None, True, "User not authenticated"),
        (True, None, True, "Invalid API key"),
        (True, "valid-api-key", False, None),
    ],
)
def test_require_api_key(has_api_key, stored_key, expect_exc, exc_msg):
    with (
        patch("openhands_cli.cloud.conversation.TokenStorage") as mock_store_cls,
        patch(
            "openhands_cli.cloud.conversation._print_login_instructions"
        ) as mock_print,
    ):
        store = Mock()
        store.has_api_key.return_value = has_api_key
        store.get_api_key.return_value = stored_key
        mock_store_cls.return_value = store

        if expect_exc:
            with pytest.raises(CloudConversationError, match=exc_msg):
                require_api_key()
            mock_print.assert_called_once()  # UX helper called for both failure paths
        else:
            assert require_api_key() == "valid-api-key"
            mock_print.assert_not_called()


# ----------------------------
# is_token_valid
# ----------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "side_effect,expected,expect_exc,exc_msg",
    [
        (None, True, False, None),
        ("UnauthenticatedError", False, False, None),
        (
            Exception("Network error"),
            None,
            True,
            "Failed to validate token: Network error",
        ),
    ],
)
async def test_is_token_valid(side_effect, expected, expect_exc, exc_msg):
    from unittest.mock import AsyncMock

    from openhands_cli.auth.api_client import UnauthenticatedError

    with patch(
        "openhands_cli.cloud.conversation.OpenHandsApiClient"
    ) as mock_client_cls:
        client = Mock()

        if side_effect is None:
            client.get_user_info = AsyncMock(return_value={"id": "user"})
        elif side_effect == "UnauthenticatedError":
            client.get_user_info = AsyncMock(
                side_effect=UnauthenticatedError("bad token")
            )
        else:
            client.get_user_info = AsyncMock(side_effect=side_effect)

        mock_client_cls.return_value = client

        if expect_exc:
            with pytest.raises(CloudConversationError, match=exc_msg):
                await is_token_valid("https://example.com", "token")
        else:
            assert await is_token_valid("https://example.com", "token") is expected

        client.get_user_info.assert_called_once()


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
async def test_create_cloud_conversation_logs_out_on_invalid_token():
    # Behavior: invalid token -> logout_command called + CloudConversationError raised.
    with (
        patch("openhands_cli.cloud.conversation.require_api_key", return_value="key"),
        patch(
            "openhands_cli.cloud.conversation.is_token_valid",
            return_value=False,
        ),
        patch("openhands_cli.cloud.conversation.logout_command") as mock_logout,
    ):
        with pytest.raises(
            CloudConversationError, match="Authentication expired - user logged out"
        ):
            await create_cloud_conversation("https://server", "hello")

        mock_logout.assert_called_once_with("https://server")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "repo_branch,expected_payload",
    [
        ((None, None), {"initial_user_msg": "hi"}),
        (("owner/repo", None), {"initial_user_msg": "hi", "repository": "owner/repo"}),
        (
            ("owner/repo", "main"),
            {
                "initial_user_msg": "hi",
                "repository": "owner/repo",
                "selected_branch": "main",
            },
        ),
    ],
)
async def test_create_cloud_conversation_payload_includes_repo_and_branch(
    repo_branch, expected_payload
):
    from unittest.mock import AsyncMock

    with (
        patch("openhands_cli.cloud.conversation.require_api_key", return_value="key"),
        patch(
            "openhands_cli.cloud.conversation.is_token_valid",
            return_value=True,
        ),
        patch(
            "openhands_cli.cloud.conversation.extract_repository_from_cwd",
            return_value=repo_branch,
        ),
        patch("openhands_cli.cloud.conversation.OpenHandsApiClient") as mock_client_cls,
    ):
        client = Mock()
        resp = Mock()
        resp.json.return_value = {"conversation_id": "c1"}
        client.create_conversation = AsyncMock(return_value=resp)
        mock_client_cls.return_value = client

        result = await create_cloud_conversation("https://server", "hi")
        assert result["conversation_id"] == "c1"
        client.create_conversation.assert_called_once_with(json_data=expected_payload)


@pytest.mark.asyncio
async def test_create_cloud_conversation_propagates_api_error_as_cloud_error():
    from unittest.mock import AsyncMock

    with (
        patch("openhands_cli.cloud.conversation.require_api_key", return_value="key"),
        patch(
            "openhands_cli.cloud.conversation.is_token_valid",
            return_value=True,
        ),
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
            await create_cloud_conversation("https://server", "hi")
