"""Tests for ACP resource conversion utilities."""

import base64
import io

from acp.schema import (
    BlobResourceContents,
    EmbeddedResourceContentBlock,
    TextResourceContents,
)
from PIL import Image

from openhands.sdk import ImageContent, TextContent
from openhands_cli.acp_impl.utils.resources import (
    _convert_image_to_supported_format,
    _materialize_embedded_resource,
)


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


def test_materialize_unsupported_image_blob_with_conversion():
    """Test that unsupported image formats are automatically converted."""
    # Create a real BMP image
    img = Image.new("RGB", (10, 10), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="BMP")
    buffer.seek(0)
    bmp_data = base64.b64encode(buffer.read()).decode("utf-8")

    blob_resource = BlobResourceContents(
        uri="file:///example.bmp",
        mimeType="image/bmp",
        blob=bmp_data,
    )
    block = EmbeddedResourceContentBlock(
        type="resource",
        resource=blob_resource,
    )

    result = _materialize_embedded_resource(block)

    # Should be converted to ImageContent with PNG format
    assert isinstance(result, ImageContent)
    assert len(result.image_urls) == 1
    assert result.image_urls[0].startswith("data:image/png;base64,")


def test_materialize_corrupted_image_blob():
    """Test that corrupted image data falls back to disk storage."""
    # Use invalid image data that can't be converted
    invalid_data = base64.b64encode(b"not_a_real_image").decode("utf-8")

    blob_resource = BlobResourceContents(
        uri="file:///example.bmp",
        mimeType="image/bmp",
        blob=invalid_data,
    )
    block = EmbeddedResourceContentBlock(
        type="resource",
        resource=blob_resource,
    )

    result = _materialize_embedded_resource(block)

    # Should fall back to disk storage
    assert isinstance(result, TextContent)
    assert "unsupported format" in result.text
    assert "image/bmp" in result.text
    assert "conversion failed" in result.text.lower()
    assert "Saved to file:" in result.text


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


def test_convert_image_to_supported_format_bmp():
    """Test converting BMP to PNG."""
    # Create a real BMP image
    img = Image.new("RGB", (10, 10), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="BMP")
    buffer.seek(0)
    bmp_data = buffer.read()

    result = _convert_image_to_supported_format(bmp_data, "image/bmp")

    assert result is not None
    mime_type, converted_data = result
    assert mime_type == "image/png"
    assert len(converted_data) > 0

    # Verify it's valid base64 PNG data
    decoded = base64.b64decode(converted_data)
    converted_img = Image.open(io.BytesIO(decoded))
    assert converted_img.format == "PNG"


def test_convert_image_to_supported_format_with_transparency():
    """Test converting image with transparency preserves alpha channel."""
    # Create an image with transparency
    img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    # Pretend it's TIFF
    png_data = buffer.read()

    result = _convert_image_to_supported_format(png_data, "image/tiff")

    assert result is not None
    mime_type, converted_data = result
    assert mime_type == "image/png"  # Should use PNG to preserve transparency


def test_convert_image_to_supported_format_invalid_data():
    """Test that invalid image data returns None."""
    invalid_data = b"not_a_real_image"

    result = _convert_image_to_supported_format(invalid_data, "image/bmp")

    assert result is None
