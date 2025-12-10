"""Logout command implementation for OpenHands CLI."""

from typing import Optional

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.auth.token_storage import get_token_storage, TokenStorageError


def logout_command(server_url: Optional[str] = None) -> bool:
    """Execute the logout command.
    
    Args:
        server_url: OpenHands server URL to log out from (None for all servers)
        
    Returns:
        True if logout was successful, False otherwise
    """
    try:
        token_storage = get_token_storage()
        
        if server_url:
            # Log out from specific server
            print_formatted_text(HTML(f"<cyan>Logging out from {server_url}...</cyan>"))
            
            if token_storage.remove_tokens(server_url):
                print_formatted_text(HTML(f"<green>✓ Successfully logged out from {server_url}</green>"))
                return True
            else:
                print_formatted_text(HTML(f"<yellow>You were not logged in to {server_url}</yellow>"))
                return True
        else:
            # Log out from all servers
            servers = token_storage.list_servers()
            
            if not servers:
                print_formatted_text(HTML("<yellow>You are not logged in to any servers.</yellow>"))
                return True
            
            print_formatted_text(HTML("<cyan>Logging out from all servers...</cyan>"))
            
            for server in servers:
                print_formatted_text(HTML(f"<white>  - {server}</white>"))
            
            token_storage.clear_all_tokens()
            print_formatted_text(HTML("<green>✓ Successfully logged out from all servers</green>"))
            return True
            
    except TokenStorageError as e:
        print_formatted_text(HTML(f"<red>Failed to log out: {str(e)}</red>"))
        return False
    
    except Exception as e:
        print_formatted_text(HTML(f"<red>Unexpected error during logout: {str(e)}</red>"))
        return False


def run_logout_command(server_url: Optional[str] = None) -> bool:
    """Run the logout command.
    
    Args:
        server_url: OpenHands server URL to log out from (None for all servers)
        
    Returns:
        True if logout was successful, False otherwise
    """
    return logout_command(server_url)