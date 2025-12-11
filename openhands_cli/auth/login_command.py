"""Login command implementation for OpenHands CLI."""

import asyncio

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.api_client import ApiClientError, fetch_user_data_after_oauth
from openhands_cli.auth.device_flow import (
    DeviceFlowError,
    authenticate_with_device_flow,
)
from openhands_cli.auth.token_storage import TokenStorage, TokenStorageError


async def login_command(server_url: str) -> bool:
    """Execute the login command.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        True if login was successful, False otherwise
    """
    print_formatted_text(
        HTML(f"<cyan>Logging in to OpenHands at {server_url}...</cyan>")
    )

    try:
        # Check if we already have an API key
        token_storage = TokenStorage()
        existing_api_key = token_storage.get_api_key()

        if existing_api_key:
            print_formatted_text(
                HTML("<yellow>You are already logged in to this server.</yellow>")
            )
            print_formatted_text(
                HTML("<white>Pulling latest settings from remote...</white>")
            )

            # Pull settings from remote using existing API key
            try:
                await fetch_user_data_after_oauth(server_url, existing_api_key)
                print_formatted_text(
                    HTML("\n<green>✓ Settings synchronized successfully!</green>")
                )
            except ApiClientError as e:
                print_formatted_text(
                    HTML(
                        f"\n<yellow>Warning: Could not fetch user data: "
                        f"{str(e)}</yellow>"
                    )
                )
                print_formatted_text(
                    HTML(
                        "<white>You are still logged in, but settings could not "
                        "be synchronized.</white>"
                    )
                )

            return True

        # Perform device flow authentication
        tokens = await authenticate_with_device_flow(server_url)

        # Store the API key securely
        api_key = tokens.get("access_token")
        if api_key:
            token_storage.store_api_key(api_key)

        print_formatted_text(
            HTML(f"<green>✓ Successfully logged in to {server_url}</green>")
        )
        print_formatted_text(
            HTML("<white>Your authentication tokens have been stored securely.</white>")
        )

        # Fetch user data using the API key
        if api_key:
            try:
                await fetch_user_data_after_oauth(server_url, api_key)
                print_formatted_text(
                    HTML(
                        "\n<white>You can now use OpenHands CLI with cloud "
                        "features.</white>"
                    )
                )
            except ApiClientError as e:
                print_formatted_text(
                    HTML(
                        f"\n<yellow>Warning: Could not fetch user data: "
                        f"{str(e)}</yellow>"
                    )
                )
                print_formatted_text(
                    HTML(
                        "<white>Authentication was successful, but some user data "
                        "could not be retrieved.</white>"
                    )
                )
                print_formatted_text(
                    HTML(
                        "<white>You can still use OpenHands CLI with cloud "
                        "features.</white>"
                    )
                )
        else:
            print_formatted_text(
                HTML(
                    "\n<yellow>Warning: No access token found in OAuth "
                    "response.</yellow>"
                )
            )
            print_formatted_text(
                HTML(
                    "<white>You can still use OpenHands CLI with cloud "
                    "features.</white>"
                )
            )

        return True

    except DeviceFlowError as e:
        print_formatted_text(HTML(f"<red>Authentication failed: {str(e)}</red>"))
        return False

    except TokenStorageError as e:
        print_formatted_text(
            HTML(f"<red>Failed to store authentication tokens: {str(e)}</red>")
        )
        print_formatted_text(
            HTML(
                "<yellow>Authentication was successful but tokens could not be "
                "saved.</yellow>"
            )
        )
        return False

    except Exception as e:
        print_formatted_text(
            HTML(f"<red>Unexpected error during login: {str(e)}</red>")
        )
        return False


def run_login_command(server_url: str) -> bool:
    """Run the login command synchronously.

    Args:
        server_url: OpenHands server URL to authenticate with

    Returns:
        True if login was successful, False otherwise
    """
    try:
        return asyncio.run(login_command(server_url))
    except KeyboardInterrupt:
        print_formatted_text(HTML("\n<yellow>Login cancelled by user.</yellow>"))
        return False
