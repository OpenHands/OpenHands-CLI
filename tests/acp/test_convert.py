"""Tests for ACP conversion utilities."""

from acp.schema import (
    ImageContentBlock,
    TextContentBlock,
)

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


def test_convert_unsupported_image_mime_type():
    """Test that unsupported image formats fall back to disk storage."""

    # Test with unsupported image formats
    unsupported_types = ["image/tiff", "image/svg+xml", "image/bmp"]
    test_data = "dGVzdGRhdGE="  # base64 encoded "testdata"

    for mime_type in unsupported_types:
        acp_prompt: list = [
            ImageContentBlock(
                type="image",
                data=test_data,
                mimeType=mime_type,
            )
        ]

        result = convert_acp_prompt_to_message_content(acp_prompt)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "unsupported format" in result[0].text
        assert mime_type in result[0].text
        assert "Saved to file:" in result[0].text
        # Verify the file path is mentioned
        assert "image_" in result[0].text
