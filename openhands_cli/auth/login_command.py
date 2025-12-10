"""Login command implementation for OpenHands CLI."""

import asyncio
from typing import Dict

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.device_flow import authenticate_with_device_flow, DeviceFlowError
from openhands_cli.auth.token_storage import get_token_storage, TokenStorageError


async def login_command(server_url: str) -> bool:
    """Execute the login command.
    
    Args:
        server_url: OpenHands server URL to authenticate with
        
    Returns:
        True if login was successful, False otherwise
    """
    print_formatted_text(HTML(f"<cyan>Logging in to OpenHands at {server_url}...</cyan>"))
    
    try:
        # Check if we already have tokens
        token_storage = get_token_storage()
        existing_tokens = token_storage.get_tokens(server_url)
        
        if existing_tokens:
            print_formatted_text(HTML("<yellow>You are already logged in to this server.</yellow>"))
            print_formatted_text(HTML("<white>Use 'openhands logout' to log out first if you want to re-authenticate.</white>"))
            return True
        
        # Perform device flow authentication
        tokens = await authenticate_with_device_flow(server_url)
        
        # Store the tokens securely
        token_storage.store_tokens(server_url, tokens)
        
        print_formatted_text(HTML(f"<green>✓ Successfully logged in to {server_url}</green>"))
        print_formatted_text(HTML("<white>Your authentication tokens have been stored securely.</white>"))
        print_formatted_text(HTML("<white>You can now use OpenHands CLI with cloud features.</white>"))
        
        return True
        
    except DeviceFlowError as e:
        print_formatted_text(HTML(f"<red>Authentication failed: {str(e)}</red>"))
        return False
    
    except TokenStorageError as e:
        print_formatted_text(HTML(f"<red>Failed to store authentication tokens: {str(e)}</red>"))
        print_formatted_text(HTML("<yellow>Authentication was successful but tokens could not be saved.</yellow>"))
        return False
    
    except Exception as e:
        print_formatted_text(HTML(f"<red>Unexpected error during login: {str(e)}</red>"))
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