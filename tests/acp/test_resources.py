"""Tests for ACP resource conversion utilities."""

import base64

from acp.schema import (
    BlobResourceContents,
    EmbeddedResourceContentBlock,
    TextResourceContents,
)

from openhands.sdk import ImageContent, TextContent
from openhands_cli.acp_impl.utils.resources import _materialize_embedded_resource


def test_materialize_text_resource():
    """Test converting text resource to TextContent."""
    text_resource = TextResourceContents(
        uri="file:///example.txt",
        mimeType="text/plain",
        text="Hello, world!",
    )
    block = EmbeddedResourceContentBlock(
        type="resource",
        resource=text_resource,
    )

    result = _materialize_embedded_resource(block)

    assert isinstance(result, TextContent)
    assert "Hello, world!" in result.text
    assert "file:///example.txt" in result.text
    assert "text/plain" in result.text


def test_materialize_supported_image_blob():
    """Test converting supported image blob to ImageContent."""
    # Test with all supported image formats
    supported_types = ["image/png", "image/jpeg", "image/gif", "image/webp"]
    test_data = base64.b64encode(b"fake_image_data").decode("utf-8")

    for mime_type in supported_types:
        blob_resource = BlobResourceContents(
            uri="file:///example.png",
            mimeType=mime_type,
            blob=test_data,
        )
        block = EmbeddedResourceContentBlock(
            type="resource",
            resource=blob_resource,
        )

        result = _materialize_embedded_resource(block)

        assert isinstance(result, ImageContent)
        assert len(result.image_urls) == 1
        assert result.image_urls[0].startswith(f"data:{mime_type};base64,")
        assert test_data in result.image_urls[0]


def test_materialize_unsupported_image_blob():
    """Test that unsupported image formats fall back to disk storage."""
    # Test with unsupported image formats
    unsupported_types = ["image/tiff", "image/svg+xml", "image/bmp"]
    test_data = base64.b64encode(b"fake_image_data").decode("utf-8")

    for mime_type in unsupported_types:
        blob_resource = BlobResourceContents(
            uri="file:///example.tiff",
            mimeType=mime_type,
            blob=test_data,
        )
        block = EmbeddedResourceContentBlock(
            type="resource",
            resource=blob_resource,
        )

        result = _materialize_embedded_resource(block)

        assert isinstance(result, TextContent)
        assert "unsupported format" in result.text
        assert mime_type in result.text
        assert "Saved to file:" in result.text
        assert "Supported formats:" in result.text


def test_materialize_non_image_blob():
    """Test converting non-image blob to TextContent with file path."""
    test_data = base64.b64encode(b"binary data").decode("utf-8")
    blob_resource = BlobResourceContents(
        uri="file:///example.bin",
        mimeType="application/octet-stream",
        blob=test_data,
    )
    block = EmbeddedResourceContentBlock(
        type="resource",
        resource=blob_resource,
    )

    result = _materialize_embedded_resource(block)

    assert isinstance(result, TextContent)
    assert "binary context (non-image)" in result.text
    assert "Saved to file:" in result.text
    # Should not mention unsupported format for non-images
    assert "unsupported format" not in result.text.lower()
