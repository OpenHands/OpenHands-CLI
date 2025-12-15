"""Unit tests for HTTP client functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from openhands_cli.auth.http_client import AuthHttpError, BaseHttpClient


class TestBaseHttpClient:
    """Test cases for BaseHttpClient class."""

    def test_init(self):
        """Test BaseHttpClient initialization."""
        server_url = "https://api.example.com/"
        client = BaseHttpClient(server_url, timeout=60.0)

        assert client.server_url == "https://api.example.com"
        assert client.timeout.connect == 60.0

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from server URL."""
        client = BaseHttpClient("https://api.example.com/")
        assert client.server_url == "https://api.example.com"

    def test_build_url(self):
        """Test URL building from endpoint."""
        client = BaseHttpClient("https://api.example.com")

        assert (
            client._build_url("/oauth/token") == "https://api.example.com/oauth/token"
        )
        assert client._build_url("oauth/token") == "https://api.example.com/oauth/token"

    def test_extract_error_detail_with_json(self):
        """Test error detail extraction from JSON response."""
        client = BaseHttpClient("https://api.example.com")

        # Mock response with JSON error
        response = httpx.Response(
            status_code=400,
            json={"detail": "Invalid request"},
        )
        response._content = json.dumps({"detail": "Invalid request"}).encode()

        detail = client._extract_error_detail(response)
        assert detail == "Invalid request"

    def test_extract_error_detail_without_detail_field(self):
        """Test error detail extraction when detail field is missing."""
        client = BaseHttpClient("https://api.example.com")

        # Mock response with JSON but no detail field
        response = httpx.Response(
            status_code=400,
            json={"error": "bad_request"},
        )
        response._content = json.dumps({"error": "bad_request"}).encode()

        detail = client._extract_error_detail(response)
        assert detail == "400"

    def test_extract_error_detail_invalid_json(self):
        """Test error detail extraction with invalid JSON."""
        client = BaseHttpClient("https://api.example.com")

        # Mock response with invalid JSON
        response = httpx.Response(status_code=500)
        response._content = b"Internal Server Error"

        detail = client._extract_error_detail(response)
        assert detail == "HTTP 500"

    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test successful HTTP request."""
        client = BaseHttpClient("https://api.example.com")

        # Create a proper mock response with request set
        mock_request = httpx.Request("GET", "https://api.example.com/test")
        mock_response = httpx.Response(status_code=200, request=mock_request)
        mock_response._content = b'{"success": true}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.request.return_value = mock_response

            response = await client._make_request("GET", "/test")

            assert response == mock_response
            mock_client.request.assert_called_once_with(
                method="GET",
                url="https://api.example.com/test",
                headers=None,
            )

    @pytest.mark.asyncio
    async def test_make_request_with_headers_and_json(self):
        """Test HTTP request with headers and JSON data."""
        client = BaseHttpClient("https://api.example.com")

        # Create a proper mock response with request set
        mock_request = httpx.Request("POST", "https://api.example.com/test")
        mock_response = httpx.Response(status_code=201, request=mock_request)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.request.return_value = mock_response

            headers = {"Authorization": "Bearer token"}
            json_data = {"key": "value"}

            response = await client._make_request(
                "POST", "/test", headers=headers, json_data=json_data
            )

            assert response == mock_response
            mock_client.request.assert_called_once_with(
                method="POST",
                url="https://api.example.com/test",
                headers=headers,
                json=json_data,
            )

    @pytest.mark.asyncio
    async def test_make_request_http_status_error(self):
        """Test HTTP request with status error."""
        client = BaseHttpClient("https://api.example.com")

        mock_response = httpx.Response(status_code=404)
        mock_response._content = json.dumps({"detail": "Not found"}).encode()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.request.return_value = mock_response

            # Mock raise_for_status to raise HTTPStatusError
            mock_request = MagicMock()
            mock_response.raise_for_status = lambda: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "404", request=mock_request, response=mock_response
                )
            )

            with pytest.raises(AuthHttpError, match="HTTP 404: Not found"):
                await client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_network_error(self):
        """Test HTTP request with network error."""
        client = BaseHttpClient("https://api.example.com")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(AuthHttpError, match="Network error: Connection failed"):
                await client._make_request("GET", "/test")

    @pytest.mark.asyncio
    async def test_make_request_no_raise_for_status(self):
        """Test HTTP request without raising for status errors."""
        client = BaseHttpClient("https://api.example.com")

        mock_response = httpx.Response(status_code=400)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.request.return_value = mock_response

            response = await client._make_request(
                "GET", "/test", raise_for_status=False
            )

            assert response == mock_response

    @pytest.mark.asyncio
    async def test_get_method(self):
        """Test GET method wrapper."""
        client = BaseHttpClient("https://api.example.com")

        with patch.object(client, "_make_request") as mock_make_request:
            mock_response = httpx.Response(status_code=200)
            mock_make_request.return_value = mock_response

            headers = {"Accept": "application/json"}
            response = await client.get("/test", headers=headers)

            assert response == mock_response
            mock_make_request.assert_called_once_with(
                "GET", "/test", headers, raise_for_status=True
            )

    @pytest.mark.asyncio
    async def test_post_method(self):
        """Test POST method wrapper."""
        client = BaseHttpClient("https://api.example.com")

        with patch.object(client, "_make_request") as mock_make_request:
            mock_response = httpx.Response(status_code=201)
            mock_make_request.return_value = mock_response

            headers = {"Content-Type": "application/json"}
            json_data = {"test": "data"}
            response = await client.post("/test", headers=headers, json_data=json_data)

            assert response == mock_response
            mock_make_request.assert_called_once_with(
                "POST", "/test", headers, json_data, None, True
            )

    @pytest.mark.asyncio
    async def test_post_method_with_raise_for_status_false(self):
        """Test POST method with raise_for_status=False."""
        client = BaseHttpClient("https://api.example.com")

        with patch.object(client, "_make_request") as mock_make_request:
            mock_response = httpx.Response(status_code=400)
            mock_make_request.return_value = mock_response

            response = await client.post("/test", raise_for_status=False)

            assert response == mock_response
            mock_make_request.assert_called_once_with(
                "POST", "/test", None, None, None, False
            )

    @pytest.mark.asyncio
    async def test_make_request_with_form_data(self):
        """Test HTTP request with form data."""
        client = BaseHttpClient("https://api.example.com")

        # Create a proper mock response with request set
        mock_request = httpx.Request("POST", "https://api.example.com/test")
        mock_response = httpx.Response(status_code=200, request=mock_request)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.request.return_value = mock_response

            form_data = {"device_code": "test123"}

            response = await client._make_request("POST", "/test", form_data=form_data)

            assert response == mock_response
            mock_client.request.assert_called_once_with(
                method="POST",
                url="https://api.example.com/test",
                headers=None,
                data=form_data,
            )

    @pytest.mark.asyncio
    async def test_post_method_with_form_data(self):
        """Test POST method wrapper with form data."""
        client = BaseHttpClient("https://api.example.com")

        with patch.object(client, "_make_request") as mock_make_request:
            mock_response = httpx.Response(status_code=200)
            mock_make_request.return_value = mock_response

            form_data = {"device_code": "test123"}
            response = await client.post("/test", form_data=form_data)

            assert response == mock_response
            mock_make_request.assert_called_once_with(
                "POST", "/test", None, None, form_data, True
            )
