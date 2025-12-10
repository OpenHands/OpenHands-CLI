"""OAuth 2.0 Device Flow client implementation for OpenHands CLI."""

import asyncio
import json
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import httpx
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML


class DeviceFlowError(Exception):
    """Base exception for device flow errors."""
    pass


class DeviceFlowClient:
    """OAuth 2.0 Device Flow client for CLI authentication."""
    
    def __init__(self, server_url: str):
        """Initialize the device flow client.
        
        Args:
            server_url: Base URL of the OpenHands server
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = httpx.Timeout(30.0)  # 30 second timeout
    
    async def start_device_flow(self) -> Tuple[str, str, str, int]:
        """Start the OAuth 2.0 Device Flow.
        
        Returns:
            Tuple of (device_code, user_code, verification_uri, interval)
            
        Raises:
            DeviceFlowError: If the device flow initiation fails
        """
        url = urljoin(self.server_url, "/oauth/device/authorize")
        
        # No data needed since endpoints are already authenticated
        data = {}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=data)
                response.raise_for_status()
                
                result = response.json()
                
                return (
                    result["device_code"],
                    result["user_code"],
                    result["verification_uri"],
                    result["interval"]
                )
                
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", str(e))
            except (json.JSONDecodeError, AttributeError):
                error_detail = str(e)
            
            raise DeviceFlowError(f"Failed to start device flow: {error_detail}")
        
        except httpx.RequestError as e:
            raise DeviceFlowError(f"Network error during device flow initiation: {str(e)}")
    
    async def poll_for_token(self, device_code: str, interval: int) -> Dict[str, str]:
        """Poll for the API key after user authorization.
        
        Args:
            device_code: The device code from start_device_flow
            interval: Polling interval in seconds
            
        Returns:
            Dictionary containing access_token (API key), token_type, etc.
            
        Raises:
            DeviceFlowError: If polling fails or user denies access
        """
        url = urljoin(self.server_url, "/oauth/device/token")
        
        data = {
            "device_code": device_code
        }
        
        max_attempts = 120  # 10 minutes with 5-second intervals
        attempt = 0
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while attempt < max_attempts:
                try:
                    response = await client.post(url, json=data)
                    
                    if response.status_code == 200:
                        # Success! We got the tokens
                        return response.json()
                    
                    # Handle error responses
                    try:
                        error_data = response.json()
                        error = error_data.get("error", "unknown_error")
                        error_description = error_data.get("error_description", "")
                        
                        if error == "authorization_pending":
                            # User hasn't completed authorization yet, keep polling
                            pass
                        elif error == "slow_down":
                            # Server wants us to slow down, increase interval
                            interval = min(interval * 2, 30)  # Cap at 30 seconds
                        elif error == "expired_token":
                            raise DeviceFlowError("Device code has expired. Please try again.")
                        elif error == "access_denied":
                            raise DeviceFlowError("User denied the authorization request.")
                        else:
                            raise DeviceFlowError(f"Authorization error: {error} - {error_description}")
                    
                    except json.JSONDecodeError:
                        raise DeviceFlowError(f"Unexpected response from server: {response.status_code}")
                
                except httpx.RequestError as e:
                    raise DeviceFlowError(f"Network error during token polling: {str(e)}")
                
                # Wait before next poll
                await asyncio.sleep(interval)
                attempt += 1
        
        raise DeviceFlowError("Timeout waiting for user authorization. Please try again.")
    
    async def authenticate(self) -> Dict[str, str]:
        """Complete OAuth 2.0 Device Flow authentication.
        
        Returns:
            Dictionary containing access_token (API key), token_type, etc.
            
        Raises:
            DeviceFlowError: If authentication fails
        """
        print_formatted_text(HTML("<cyan>Starting OpenHands authentication...</cyan>"))
        
        # Step 1: Start device flow
        try:
            device_code, user_code, verification_uri, interval = await self.start_device_flow()
        except DeviceFlowError as e:
            print_formatted_text(HTML(f"<red>Error: {str(e)}</red>"))
            raise
        
        # Step 2: Display instructions to user
        print_formatted_text(HTML("\n<yellow>To authenticate, please follow these steps:</yellow>"))
        print_formatted_text(HTML(f"<white>1. Open your web browser and go to: <b>{verification_uri}</b></white>"))
        print_formatted_text(HTML(f"<white>2. Enter this code: <b>{user_code}</b></white>"))
        print_formatted_text(HTML("<white>3. Follow the instructions to complete authentication</white>"))
        print_formatted_text(HTML("\n<cyan>Waiting for authentication to complete...</cyan>"))
        
        # Step 3: Poll for token
        try:
            tokens = await self.poll_for_token(device_code, interval)
            print_formatted_text(HTML("<green>✓ Authentication successful!</green>"))
            return tokens
        except DeviceFlowError as e:
            print_formatted_text(HTML(f"<red>Error: {str(e)}</red>"))
            raise


async def authenticate_with_device_flow(server_url: str) -> Dict[str, str]:
    """Convenience function to authenticate using device flow.
    
    Args:
        server_url: OpenHands server URL
        
    Returns:
        Dictionary containing authentication tokens
        
    Raises:
        DeviceFlowError: If authentication fails
    """
    client = DeviceFlowClient(server_url)
    return await client.authenticate()