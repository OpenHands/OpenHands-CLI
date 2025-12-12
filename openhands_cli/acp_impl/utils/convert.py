"""Utility functions for ACP implementation."""

import base64
from uuid import uuid4

from acp.schema import (
    AudioContentBlock as ACPAudioContentBlock,
    EmbeddedResourceContentBlock as ACPEmbeddedResourceContentBlock,
    ImageContentBlock as ACPImageContentBlock,
    ResourceContentBlock as ACPResourceContentBlock,
    TextContentBlock as ACPTextContentBlock,
)

from openhands.sdk import ImageContent, TextContent
from openhands_cli.acp_impl.utils.resources import (
    ACP_CACHE_DIR,
    SUPPORTED_IMAGE_MIME_TYPES,
    _convert_image_to_supported_format,
    convert_resources_to_content,
)


def _convert_image_block(block: ACPImageContentBlock) -> TextContent | ImageContent:
    """
    Convert an ACP image content block to SDK format.

    Handles:
    1. Supported image formats -> ImageContent
    2. Unsupported but convertible formats -> ImageContent with converted data
    3. Unsupported and non-convertible formats -> TextContent with file path

    Args:
        block: ACP image content block

    Returns:
        ImageContent if format is supported or convertible, TextContent otherwise
    """
    # Handle supported formats directly
    if block.mimeType in SUPPORTED_IMAGE_MIME_TYPES:
        return ImageContent(image_urls=[f"data:{block.mimeType};base64,{block.data}"])

    # Try to convert unsupported formats
    data = base64.b64decode(block.data)
    converted = _convert_image_to_supported_format(data, block.mimeType)

    if converted is not None:
        target_mime, converted_data = converted
        return ImageContent(image_urls=[f"data:{target_mime};base64,{converted_data}"])

    # Conversion failed - save to disk and return explanatory text
    filename = f"image_{uuid4().hex}"
    target = ACP_CACHE_DIR / filename
    target.write_bytes(data)
    supported = ", ".join(sorted(SUPPORTED_IMAGE_MIME_TYPES))

    return TextContent(
        text=(
            "\n[BEGIN USER PROVIDED ADDITIONAL CONTEXT]\n"
            f"User provided image with unsupported format ({block.mimeType}).\n"
            "Attempted automatic conversion failed.\n"
            f"Supported formats: {supported}\n"
            f"Saved to file: {str(target)}\n"
            "[END USER PROVIDED ADDITIONAL CONTEXT]\n"
        )
    )


def convert_acp_prompt_to_message_content(
    acp_prompt: list[
        ACPTextContentBlock
        | ACPImageContentBlock
        | ACPAudioContentBlock
        | ACPResourceContentBlock
        | ACPEmbeddedResourceContentBlock,
    ],
) -> list[TextContent | ImageContent]:
    """
    Convert ACP prompt to OpenHands message content format.

    Handles various ACP prompt formats:
    - Simple string
    - List of content blocks (text/image)
    - Single ContentBlock object

    Args:
        prompt: ACP prompt in various formats (string, list, or ContentBlock)

    Returns:
        List of TextContent and ImageContent objects supported by SDK
    """
    message_content: list[TextContent | ImageContent] = []
    for block in acp_prompt:
        if isinstance(block, ACPTextContentBlock):
            message_content.append(TextContent(text=block.text))
        elif isinstance(block, ACPImageContentBlock):
            message_content.append(_convert_image_block(block))
        elif isinstance(
            block, ACPResourceContentBlock | ACPEmbeddedResourceContentBlock
        ):
            # https://agentclientprotocol.com/protocol/content#resource-link
            # https://agentclientprotocol.com/protocol/content#embedded-resource
            message_content.append(convert_resources_to_content(block))
    return message_content
