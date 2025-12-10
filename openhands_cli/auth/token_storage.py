"""Secure token storage for OpenHands CLI authentication."""

import json
import os
import stat
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class TokenStorageError(Exception):
    """Exception raised for token storage errors."""
    pass


class TokenStorage:
    """Secure local storage for authentication tokens."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize token storage.
        
        Args:
            config_dir: Directory to store tokens (defaults to ~/.openhands)
        """
        if config_dir is None:
            config_dir = Path.home() / ".openhands"
        
        self.config_dir = config_dir
        self.config_dir.mkdir(mode=0o700, exist_ok=True)  # Secure permissions
        
        self.token_file = self.config_dir / "auth_tokens.enc"
        self.key_file = self.config_dir / "auth_key.key"
        
        # Ensure secure permissions on config directory
        self._secure_directory()
    
    def _secure_directory(self) -> None:
        """Ensure the config directory has secure permissions."""
        try:
            # Set directory permissions to 700 (owner read/write/execute only)
            os.chmod(self.config_dir, stat.S_IRWXU)
        except OSError as e:
            raise TokenStorageError(f"Failed to secure config directory: {e}")
    
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key for token storage."""
        if self.key_file.exists():
            try:
                with open(self.key_file, 'rb') as f:
                    return f.read()
            except OSError as e:
                raise TokenStorageError(f"Failed to read encryption key: {e}")
        else:
            # Generate a new key
            key = Fernet.generate_key()
            try:
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                # Secure permissions on key file
                os.chmod(self.key_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
                return key
            except OSError as e:
                raise TokenStorageError(f"Failed to create encryption key: {e}")
    
    def _encrypt_data(self, data: Dict) -> bytes:
        """Encrypt token data."""
        try:
            key = self._get_or_create_key()
            fernet = Fernet(key)
            json_data = json.dumps(data).encode('utf-8')
            return fernet.encrypt(json_data)
        except Exception as e:
            raise TokenStorageError(f"Failed to encrypt token data: {e}")
    
    def _decrypt_data(self, encrypted_data: bytes) -> Dict:
        """Decrypt token data."""
        try:
            key = self._get_or_create_key()
            fernet = Fernet(key)
            json_data = fernet.decrypt(encrypted_data)
            return json.loads(json_data.decode('utf-8'))
        except Exception as e:
            raise TokenStorageError(f"Failed to decrypt token data: {e}")
    
    def store_tokens(self, server_url: str, tokens: Dict[str, str]) -> None:
        """Store authentication tokens for a server.
        
        Args:
            server_url: The server URL these tokens are for
            tokens: Dictionary containing access_token, refresh_token, etc.
        """
        try:
            # Load existing tokens
            all_tokens = {}
            if self.token_file.exists():
                try:
                    with open(self.token_file, 'rb') as f:
                        encrypted_data = f.read()
                    all_tokens = self._decrypt_data(encrypted_data)
                except (OSError, TokenStorageError):
                    # If we can't read existing tokens, start fresh
                    all_tokens = {}
            
            # Add/update tokens for this server
            all_tokens[server_url] = tokens
            
            # Encrypt and save
            encrypted_data = self._encrypt_data(all_tokens)
            with open(self.token_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Secure permissions on token file
            os.chmod(self.token_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
            
        except OSError as e:
            raise TokenStorageError(f"Failed to store tokens: {e}")
    
    def get_tokens(self, server_url: str) -> Optional[Dict[str, str]]:
        """Get stored authentication tokens for a server.
        
        Args:
            server_url: The server URL to get tokens for
            
        Returns:
            Dictionary containing tokens, or None if not found
        """
        if not self.token_file.exists():
            return None
        
        try:
            with open(self.token_file, 'rb') as f:
                encrypted_data = f.read()
            
            all_tokens = self._decrypt_data(encrypted_data)
            return all_tokens.get(server_url)
            
        except (OSError, TokenStorageError):
            return None
    
    def remove_tokens(self, server_url: str) -> bool:
        """Remove stored tokens for a server.
        
        Args:
            server_url: The server URL to remove tokens for
            
        Returns:
            True if tokens were removed, False if they didn't exist
        """
        if not self.token_file.exists():
            return False
        
        try:
            with open(self.token_file, 'rb') as f:
                encrypted_data = f.read()
            
            all_tokens = self._decrypt_data(encrypted_data)
            
            if server_url not in all_tokens:
                return False
            
            del all_tokens[server_url]
            
            # Save updated tokens
            if all_tokens:
                encrypted_data = self._encrypt_data(all_tokens)
                with open(self.token_file, 'wb') as f:
                    f.write(encrypted_data)
            else:
                # No tokens left, remove the file
                self.token_file.unlink()
            
            return True
            
        except (OSError, TokenStorageError):
            return False
    
    def clear_all_tokens(self) -> None:
        """Remove all stored tokens."""
        try:
            if self.token_file.exists():
                self.token_file.unlink()
            if self.key_file.exists():
                self.key_file.unlink()
        except OSError as e:
            raise TokenStorageError(f"Failed to clear tokens: {e}")
    
    def list_servers(self) -> list[str]:
        """List all servers with stored tokens.
        
        Returns:
            List of server URLs with stored tokens
        """
        if not self.token_file.exists():
            return []
        
        try:
            with open(self.token_file, 'rb') as f:
                encrypted_data = f.read()
            
            all_tokens = self._decrypt_data(encrypted_data)
            return list(all_tokens.keys())
            
        except (OSError, TokenStorageError):
            return []


# Global token storage instance
_token_storage: Optional[TokenStorage] = None


def get_token_storage() -> TokenStorage:
    """Get the global token storage instance."""
    global _token_storage
    if _token_storage is None:
        _token_storage = TokenStorage()
    return _token_storage