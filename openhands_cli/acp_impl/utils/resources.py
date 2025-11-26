"""Utility functions for ACP implementation."""

import base64
import io
import mimetypes
from pathlib import Path
from uuid import uuid4

from acp.schema import (
    BlobResourceContents as ACPBlobResourceContents,
    EmbeddedResourceContentBlock as ACPEmbeddedResourceContentBlock,
    ResourceContentBlock as ACPResourceContentBlock,
    TextResourceContents as ACPTextResourceContents,
)
from PIL import Image

from openhands.sdk import ImageContent, TextContent
from openhands.sdk.context import Skill


RESOURCE_SKILL = Skill(
    name="user_provided_resources",
    content=(
        "You may encounter sections labeled as user-provided additional "
        "context or resources. "
        "These blocks contain files or data that the user referenced in their message. "
        "They may include plain text, images, code snippets, or binary "
        "content saved to a temporary file. "
        "Treat these blocks as part of the user’s input. "
        "Read them carefully and use their contents when forming your "
        "reasoning or answering the query. "
        "If a block points to a saved file, assume it contains relevant "
        "binary data that could not be displayed directly."
    ),
    trigger=None,
)

ACP_CACHE_DIR = Path.home() / ".openhands" / "cache" / "acp"
ACP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# LLM API supported image MIME types (Anthropic/Claude compatible)
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


def _convert_image_to_supported_format(
    image_data: bytes,
    source_mime_type: str,  # noqa: ARG001
) -> tuple[str, str] | None:
    """
    Try to convert an unsupported image format to PNG.

    Args:
        image_data: The raw image bytes
        source_mime_type: The original MIME type (currently unused but kept for API)

    Returns:
        A tuple of (mime_type, base64_data) if conversion succeeds, None otherwise
    """
    try:
        # Open the image with Pillow
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (some formats like RGBA need this for JPEG)
        # PNG supports transparency, so we'll use PNG as target format
        if img.mode in ("RGBA", "LA", "P"):
            # Keep transparency by converting to PNG
            output_format = "PNG"
            target_mime = "image/png"
        else:
            # For non-transparent images, we can use PNG or JPEG
            # PNG is lossless, so prefer it
            output_format = "PNG"
            target_mime = "image/png"

        # Convert the image to the target format
        output_buffer = io.BytesIO()
        img.save(output_buffer, format=output_format)
        output_buffer.seek(0)

        # Encode to base64
        converted_data = base64.b64encode(output_buffer.read()).decode("utf-8")

        return target_mime, converted_data

    except Exception:
        # If conversion fails for any reason, return None
        # This could happen for corrupted images, unsupported formats, etc.
        return None


def _materialize_embedded_resource(
    block: ACPEmbeddedResourceContentBlock,
) -> TextContent | ImageContent:
    """
    For:
    - text resources: return TextContent containing the text.
    - image blobs: return ImageContent directly (no disk write).
    - other binary blobs: write to disk and return TextContent explaining the path.
    """
    res: ACPTextResourceContents | ACPBlobResourceContents = block.resource

    if isinstance(res, ACPTextResourceContents):
        return TextContent(
            text=(
                "\n[BEGIN USER PROVIDED ADDITIONAL CONTEXT]\n"
                f"URI: {res.uri}\n"
                f"mimeType: {res.mimeType}\n"
                "Content:\n"
                f"{res.text}\n"
                "[END USER PROVIDED ADDITIONAL CONTEXT]\n"
            )
        )

    elif isinstance(res, ACPBlobResourceContents):
        mime_type = res.mimeType or ""

        # 1. If it's a supported image type, directly return ImageContent
        if mime_type in SUPPORTED_IMAGE_MIME_TYPES:
            data_uri = f"data:{mime_type};base64,{res.blob}"
            return ImageContent(image_urls=[data_uri])

        # 2. If it's an unsupported image type, try to convert it
        if mime_type.startswith("image/"):
            data = base64.b64decode(res.blob)
            converted = _convert_image_to_supported_format(data, mime_type)

            if converted is not None:
                # Conversion succeeded, return as ImageContent
                target_mime, converted_data = converted
                data_uri = f"data:{target_mime};base64,{converted_data}"
                return ImageContent(image_urls=[data_uri])

            # Conversion failed, fall through to disk storage

        # 3. For non-images or failed conversions, save to disk
        data = base64.b64decode(res.blob)

        ext = ""
        if mime_type:
            ext = mimetypes.guess_extension(mime_type) or ""

        filename = f"embedded_resource_{uuid4().hex}{ext}"
        target = ACP_CACHE_DIR / filename
        target.write_bytes(data)

        # Provide appropriate message based on content type
        if mime_type.startswith("image/"):
            description = (
                f"User provided image with unsupported format ({mime_type}).\n"
                "Attempted automatic conversion failed.\n"
                f"Supported formats: {', '.join(sorted(SUPPORTED_IMAGE_MIME_TYPES))}\n"
            )
        else:
            description = "User provided binary context (non-image).\n"

        return TextContent(
            text=(
                "\n[BEGIN USER PROVIDED ADDITIONAL CONTEXT]\n"
                f"{description}"
                f"Saved to file: {str(target)}\n"
                "[END USER PROVIDED ADDITIONAL CONTEXT]\n"
            )
        )


def convert_resources_to_content(
    resource: ACPResourceContentBlock | ACPEmbeddedResourceContentBlock,
) -> TextContent | ImageContent:
    if isinstance(resource, ACPResourceContentBlock):
        return TextContent(
            text=(
                "\n[BEGIN USER PROVIDED ADDITIONAL RESOURCE]\n"
                f"Type: {resource.type}\n"
                f"URI: {resource.uri}\n"
                f"name: {resource.name}\n"
                f"mimeType: {resource.mimeType}\n"
                f"size: {resource.size}\n"
                "[END USER PROVIDED ADDITIONAL RESOURCE]\n"
            )
        )
    elif isinstance(resource, ACPEmbeddedResourceContentBlock):
        return _materialize_embedded_resource(resource)

    raise ValueError(f"Unexpected resource type: {type(resource)}")
