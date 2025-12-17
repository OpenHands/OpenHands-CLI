"""Base HTTP client for OpenHands authentication services."""

import json
from typing import Any
from urllib.parse import urljoin

import httpx


class AuthHttpError(Exception):
    """Base exception for HTTP authentication errors."""

    pass


class BaseHttpClient:
    """Base HTTP client with common functionality for authentication services."""

    def __init__(self, server_url: str, timeout: float = 30.0):
        """Initialize the HTTP client.

        Args:
            server_url: Base URL of the OpenHands server
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout)

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Full URL
        """
        return urljoin(self.server_url, endpoint)

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extract error detail from HTTP response.

        Args:
            response: HTTP response object

        Returns:
            Error detail string
        """
        try:
            error_data = response.json()
            return error_data.get("detail", str(response.status_code))
        except (json.JSONDecodeError, AttributeError):
            return f"HTTP {response.status_code}"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        raise_for_status: bool = True,
    ) -> httpx.Response:
        """Make HTTP request with common error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            headers: Optional request headers
            json_data: Optional JSON data for request body
            form_data: Optional form data for request body (form-urlencoded)
            raise_for_status: Whether to raise exception for HTTP errors

        Returns:
            HTTP response object

        Raises:
            AuthHttpError: If request fails
        """
        url = self._build_url(endpoint)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Prepare request parameters
                request_kwargs = {
                    "method": method,
                    "url": url,
                    "headers": headers,
                }

                # Add either JSON or form data, but not both
                if json_data is not None:
                    request_kwargs["json"] = json_data
                elif form_data is not None:
                    request_kwargs["data"] = form_data

                response = await client.request(**request_kwargs)

                if raise_for_status:
                    response.raise_for_status()

                return response

        except httpx.HTTPStatusError as e:
            error_detail = self._extract_error_detail(e.response)
            raise AuthHttpError(f"HTTP {e.response.status_code}: {error_detail}")

        except httpx.RequestError as e:
            raise AuthHttpError(f"Network error: {str(e)}")

    async def get(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        raise_for_status: bool = True,
    ) -> httpx.Response:
        """Make GET request.

        Args:
            endpoint: API endpoint path
            headers: Optional request headers
            raise_for_status: Whether to raise exception for HTTP errors

        Returns:
            HTTP response object
        """
        return await self._make_request(
            "GET", endpoint, headers, raise_for_status=raise_for_status
        )

    async def post(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        json_data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        raise_for_status: bool = True,
    ) -> httpx.Response:
        """Make POST request.

        Args:
            endpoint: API endpoint path
            headers: Optional request headers
            json_data: Optional JSON data for request body
            form_data: Optional form data for request body (form-urlencoded)
            raise_for_status: Whether to raise exception for HTTP errors

        Returns:
            HTTP response object
        """
        return await self._make_request(
            "POST", endpoint, headers, json_data, form_data, raise_for_status
        )
