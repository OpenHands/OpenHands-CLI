"""Tests for ACP conversion utilities."""

import base64
import io

from acp.schema import (
    BlobResourceContents,
    EmbeddedResourceContentBlock,
    ImageContentBlock,
    ResourceContentBlock,
    TextContentBlock,
    TextResourceContents,
)
from PIL import Image

from openhands.sdk import ImageContent, TextContent
from openhands_cli.acp_impl.utils.convert import convert_acp_prompt_to_message_content


def test_convert_text_content():
    """Test converting ACP text content block to SDK format."""
    acp_prompt: list = [TextContentBlock(type="text", text="Hello, world!")]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert result[0].text == "Hello, world!"


def test_convert_multiple_text_blocks():
    """Test converting multiple ACP text content blocks."""
    acp_prompt: list = [
        TextContentBlock(type="text", text="First message"),
        TextContentBlock(type="text", text="Second message"),
        TextContentBlock(type="text", text="Third message"),
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 3
    assert all(isinstance(content, TextContent) for content in result)
    assert isinstance(result[0], TextContent)
    assert result[0].text == "First message"
    assert isinstance(result[1], TextContent)
    assert result[1].text == "Second message"
    assert isinstance(result[2], TextContent)
    assert result[2].text == "Third message"


def test_convert_image_content():
    """Test converting ACP image content block to SDK format."""
    # Base64 encoded 1x1 red pixel PNG
    test_image_data = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAF"
        "BQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    acp_prompt: list = [
        ImageContentBlock(
            type="image",
            data=test_image_data,
            mimeType="image/png",
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], ImageContent)
    assert len(result[0].image_urls) == 1
    assert result[0].image_urls[0].startswith("data:image/png;base64,")
    assert test_image_data in result[0].image_urls[0]


def test_convert_mixed_content():
    """Test converting mixed text and image content blocks."""
    test_image_data = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAF"
        "BQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    acp_prompt: list = [
        TextContentBlock(type="text", text="Look at this image:"),
        ImageContentBlock(
            type="image",
            data=test_image_data,
            mimeType="image/png",
        ),
        TextContentBlock(type="text", text="What do you see?"),
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 3
    assert isinstance(result[0], TextContent)
    assert result[0].text == "Look at this image:"
    assert isinstance(result[1], ImageContent)
    assert isinstance(result[2], TextContent)
    assert result[2].text == "What do you see?"


def test_convert_empty_prompt():
    """Test converting an empty prompt list."""
    acp_prompt = []

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert result == []


def test_convert_empty_text():
    """Test converting text block with empty string."""
    acp_prompt: list = [TextContentBlock(type="text", text="")]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert result[0].text == ""


def test_convert_image_with_different_mime_types():
    """Test converting images with various supported MIME types."""
    mime_types = ["image/png", "image/jpeg", "image/gif", "image/webp"]
    test_data = "dGVzdGRhdGE="  # base64 encoded "testdata"

    for mime_type in mime_types:
        acp_prompt: list = [
            ImageContentBlock(
                type="image",
                data=test_data,
                mimeType=mime_type,
            )
        ]

        result = convert_acp_prompt_to_message_content(acp_prompt)

        assert len(result) == 1
        assert isinstance(result[0], ImageContent)
        assert result[0].image_urls[0].startswith(f"data:{mime_type};base64,")


def test_convert_unsupported_image_mime_type_with_conversion():
    """Test that unsupported image formats are automatically converted."""
    # Create a real BMP image
    img = Image.new("RGB", (10, 10), color="green")
    buffer = io.BytesIO()
    img.save(buffer, format="BMP")
    buffer.seek(0)
    bmp_data = base64.b64encode(buffer.read()).decode("utf-8")

    acp_prompt: list = [
        ImageContentBlock(
            type="image",
            data=bmp_data,
            mimeType="image/bmp",
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], ImageContent)
    assert result[0].image_urls[0].startswith("data:image/png;base64,")


def test_convert_corrupted_image_falls_back():
    """Test that corrupted image data falls back to disk storage."""
    # Use invalid image data that can't be converted
    invalid_data = base64.b64encode(b"not_a_real_image").decode("utf-8")

    acp_prompt: list = [
        ImageContentBlock(
            type="image",
            data=invalid_data,
            mimeType="image/bmp",
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert "unsupported format" in result[0].text
    assert "image/bmp" in result[0].text
    assert "conversion failed" in result[0].text.lower()
    assert "Saved to file:" in result[0].text


def test_convert_resource_content_block():
    """Test converting ResourceContentBlock to TextContent."""
    acp_prompt: list = [
        ResourceContentBlock(
            type="resource_link",
            uri="file:///example.txt",
            name="example.txt",
            mimeType="text/plain",
            size=1234,
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert "file:///example.txt" in result[0].text
    assert "example.txt" in result[0].text
    assert "text/plain" in result[0].text
    assert "1234" in result[0].text
    assert "USER PROVIDED ADDITIONAL RESOURCE" in result[0].text


def test_convert_embedded_text_resource():
    """Test converting EmbeddedResourceContentBlock with text content."""
    text_resource = TextResourceContents(
        uri="file:///example.txt",
        mimeType="text/plain",
        text="Hello from embedded resource!",
    )
    acp_prompt: list = [
        EmbeddedResourceContentBlock(
            type="resource",
            resource=text_resource,
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert "Hello from embedded resource!" in result[0].text
    assert "file:///example.txt" in result[0].text
    assert "text/plain" in result[0].text
    assert "USER PROVIDED ADDITIONAL CONTEXT" in result[0].text


def test_convert_embedded_image_blob():
    """Test converting EmbeddedResourceContentBlock with image blob."""
    # Base64 encoded 1x1 red pixel PNG
    test_image_data = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAF"
        "BQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    blob_resource = BlobResourceContents(
        uri="file:///example.png",
        mimeType="image/png",
        blob=test_image_data,
    )
    acp_prompt: list = [
        EmbeddedResourceContentBlock(
            type="resource",
            resource=blob_resource,
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], ImageContent)
    assert len(result[0].image_urls) == 1
    assert result[0].image_urls[0].startswith("data:image/png;base64,")


def test_convert_embedded_unsupported_image_blob():
    """Test converting EmbeddedResourceContentBlock with unsupported image format."""
    # Create a real BMP image
    img = Image.new("RGB", (10, 10), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="BMP")
    buffer.seek(0)
    bmp_data = base64.b64encode(buffer.read()).decode("utf-8")

    blob_resource = BlobResourceContents(
        uri="file:///example.bmp",
        mimeType="image/bmp",
        blob=bmp_data,
    )
    acp_prompt: list = [
        EmbeddedResourceContentBlock(
            type="resource",
            resource=blob_resource,
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    # Should be converted to PNG
    assert isinstance(result[0], ImageContent)
    assert result[0].image_urls[0].startswith("data:image/png;base64,")


def test_convert_embedded_non_image_blob():
    """Test converting EmbeddedResourceContentBlock with non-image blob."""
    test_data = base64.b64encode(b"binary data").decode("utf-8")
    blob_resource = BlobResourceContents(
        uri="file:///example.bin",
        mimeType="application/octet-stream",
        blob=test_data,
    )
    acp_prompt: list = [
        EmbeddedResourceContentBlock(
            type="resource",
            resource=blob_resource,
        )
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert "binary context (non-image)" in result[0].text
    assert "Saved to file:" in result[0].text


def test_convert_mixed_content_with_resources():
    """Test converting mixed content including resources."""
    test_image_data = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAF"
        "BQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    text_resource = TextResourceContents(
        uri="file:///notes.txt",
        mimeType="text/plain",
        text="Some notes",
    )

    acp_prompt: list = [
        TextContentBlock(type="text", text="Check this:"),
        ImageContentBlock(
            type="image",
            data=test_image_data,
            mimeType="image/png",
        ),
        ResourceContentBlock(
            type="resource_link",
            uri="file:///data.csv",
            name="data.csv",
            mimeType="text/csv",
            size=5678,
        ),
        EmbeddedResourceContentBlock(
            type="resource",
            resource=text_resource,
        ),
        TextContentBlock(type="text", text="What do you think?"),
    ]

    result = convert_acp_prompt_to_message_content(acp_prompt)

    assert len(result) == 5
    assert isinstance(result[0], TextContent)
    assert result[0].text == "Check this:"
    assert isinstance(result[1], ImageContent)
    assert isinstance(result[2], TextContent)
    assert "data.csv" in result[2].text
    assert isinstance(result[3], TextContent)
    assert "Some notes" in result[3].text
    assert isinstance(result[4], TextContent)
    assert result[4].text == "What do you think?"
