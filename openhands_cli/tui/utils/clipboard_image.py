"""Platform-specific clipboard image reading utilities.

Reads image data from the system clipboard on macOS and Linux.
Returns PNG-encoded bytes or None if no image is available.
"""

from __future__ import annotations

import io
import platform
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.text import Text

from openhands.sdk.logger import get_logger

logger = get_logger(__name__)

# Maximum image size to accept (10 MB)
MAX_IMAGE_SIZE = 10 * 1024 * 1024


def read_image_from_clipboard() -> bytes | None:
    """Read image data from the system clipboard.

    Returns PNG-encoded bytes if an image is on the clipboard, None otherwise.
    Supports macOS (pngpaste, osascript) and Linux (xclip, wl-paste).
    """
    system = platform.system()
    if system == "Darwin":
        return _read_clipboard_macos()
    elif system == "Linux":
        return _read_clipboard_linux()
    return None


def _read_clipboard_macos() -> bytes | None:
    """Read image from macOS clipboard."""
    # Try pngpaste first (brew install pngpaste)
    if shutil.which("pngpaste"):
        try:
            result = subprocess.run(
                ["pngpaste", "-"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                return _validate_image(result.stdout)
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Fallback: use osascript to write clipboard image to a temp file
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        script = (
            'set tmpFile to POSIX file "' + tmp_path + '"\n'
            "try\n"
            "  set imgData to the clipboard as «class PNGf»\n"
            "  set fRef to open for access tmpFile with write permission\n"
            "  write imgData to fRef\n"
            "  close access fRef\n"
            '  return "OK"\n'
            "on error\n"
            '  return "NO_IMAGE"\n'
            "end try"
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "OK" in result.stdout:
            import os

            with open(tmp_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_path)
            if data:
                return _validate_image(data)
        else:
            import os

            os.unlink(tmp_path)
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass

    # Try reading a copied file path from clipboard
    return _try_read_file_from_clipboard_macos()


def _try_read_file_from_clipboard_macos() -> bytes | None:
    """Try to read a copied image file from macOS clipboard.

    When users copy a file in Finder, the clipboard contains a file path
    rather than image data.
    """
    try:
        # Get clipboard content as text (may contain a file path)
        result = subprocess.run(
            ["osascript", "-e", 'the clipboard as text'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _load_image_from_file_path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Also try getting file URLs via pbpaste
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            if text.startswith("file://"):
                return _load_image_from_uri_text(text)
            return _load_image_from_file_path(text)
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def _load_image_from_file_path(path_str: str) -> bytes | None:
    """Try to load an image from a file path string."""
    _IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}

    try:
        path = __import__("pathlib").Path(path_str)
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS:
            data = path.read_bytes()
            return _validate_image(data)
    except (OSError, ValueError):
        pass
    return None


def _read_clipboard_linux() -> bytes | None:
    """Read image from Linux clipboard using xclip or wl-paste.

    Checks for image data first, then falls back to checking for copied
    file URIs (e.g., when a user copies an image file in a file manager).
    """
    # Try xclip (X11)
    if shutil.which("xclip"):
        try:
            # Check available TARGETS
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            targets = result.stdout if result.returncode == 0 else ""

            # Try direct image data first
            if "image/png" in targets:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout:
                    return _validate_image(result.stdout)

            # Try file URI (copied file from file manager)
            image_data = _try_read_file_uri_xclip(targets)
            if image_data is not None:
                return image_data

        except (subprocess.TimeoutExpired, OSError):
            pass

    # Try xsel (X11 alternative) - only supports getting text/URIs, not raw image
    if shutil.which("xsel"):
        try:
            result = subprocess.run(
                ["xsel", "--clipboard", "--output"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                text = result.stdout.strip()
                if text.startswith("file://"):
                    data = _load_image_from_uri_text(text)
                    if data is not None:
                        return data
                else:
                    data = _load_image_from_file_path(text)
                    if data is not None:
                        return data
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Try wl-paste (Wayland)
    if shutil.which("wl-paste"):
        try:
            # Check available MIME types
            result = subprocess.run(
                ["wl-paste", "--list-types"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            types = result.stdout if result.returncode == 0 else ""

            # Try direct image data first
            if "image/png" in types:
                result = subprocess.run(
                    ["wl-paste", "--type", "image/png"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout:
                    return _validate_image(result.stdout)

            # Try file URI (copied file from file manager)
            image_data = _try_read_file_uri_wl(types)
            if image_data is not None:
                return image_data

        except (subprocess.TimeoutExpired, OSError):
            pass

    return None


def _try_read_file_uri_xclip(targets: str) -> bytes | None:
    """Try to read an image file URI from xclip clipboard."""
    # File managers put URIs in various target types
    for target in ("text/uri-list", "x-special/gnome-copied-files"):
        if target not in targets:
            continue
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", target, "-o"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                data = _load_image_from_uri_text(result.stdout)
                if data is not None:
                    return data
        except (subprocess.TimeoutExpired, OSError):
            pass
    return None


def _try_read_file_uri_wl(types: str) -> bytes | None:
    """Try to read an image file URI from wl-paste clipboard."""
    for mime_type in ("text/uri-list", "x-special/gnome-copied-files"):
        if mime_type not in types:
            continue
        try:
            result = subprocess.run(
                ["wl-paste", "--type", mime_type],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                data = _load_image_from_uri_text(result.stdout)
                if data is not None:
                    return data
        except (subprocess.TimeoutExpired, OSError):
            pass
    return None


def _load_image_from_uri_text(uri_text: str) -> bytes | None:
    """Extract a file path from URI text and load it as an image.

    Handles formats like:
    - "file:///path/to/image.png"
    - "copy\\nfile:///path/to/image.png" (gnome-copied-files)
    """
    from urllib.parse import unquote, urlparse

    _IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}

    for line in uri_text.strip().splitlines():
        line = line.strip()
        if not line.startswith("file://"):
            continue
        try:
            parsed = urlparse(line)
            file_path = unquote(parsed.path)
            path = __import__("pathlib").Path(file_path)
            if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS:
                data = path.read_bytes()
                return _validate_image(data)
        except (OSError, ValueError):
            continue
    return None


def _validate_image(data: bytes) -> bytes | None:
    """Validate image data and convert to PNG format.

    Returns PNG bytes or None if data is not a valid image.
    """
    if len(data) > MAX_IMAGE_SIZE:
        logger.warning(
            f"Clipboard image too large ({get_image_size_display(data)}), "
            f"max {MAX_IMAGE_SIZE // (1024 * 1024)} MB"
        )
        return None

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        # Convert to PNG
        output = io.BytesIO()
        if img.mode in ("RGBA", "LA", "P"):
            img.save(output, format="PNG")
        else:
            img = img.convert("RGB")
            img.save(output, format="PNG")
        return output.getvalue()
    except Exception:
        logger.debug("Failed to validate clipboard image data")
        return None


def get_image_size_display(image_bytes: bytes) -> str:
    """Format image size for display (e.g., '245 KB')."""
    size = len(image_bytes)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int] | None:
    """Get image dimensions (width, height) from image bytes."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        return img.size
    except Exception:
        return None


def image_to_rich_text(
    image_data: bytes, width: int = 40, height: int = 20
) -> Text | None:
    """Convert image bytes to a Rich Text object using half-block ANSI art.

    Uses the "▀" (upper half block) character where the foreground color
    represents the top pixel and the background color represents the bottom
    pixel. This effectively doubles the vertical resolution.

    Args:
        image_data: PNG image bytes.
        width: Width in characters.
        height: Height in character rows (each row encodes 2 pixel rows).

    Returns:
        A Rich Text object with colored block characters, or None on error.
    """
    try:
        from PIL import Image
        from rich.text import Text

        img = Image.open(io.BytesIO(image_data))
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Each character row represents 2 pixel rows via half-blocks
        pixel_height = height * 2
        img = img.resize((width, pixel_height), Image.Resampling.LANCZOS)
        pixels = list(img.getdata())

        text = Text()
        for row in range(height):
            if row > 0:
                text.append("\n")
            top_row = row * 2
            bottom_row = top_row + 1
            for col in range(width):
                tr, tg, tb = pixels[top_row * width + col]
                br, bg, bb = pixels[bottom_row * width + col]
                # Upper half block: foreground = top pixel, background = bottom pixel
                text.append(
                    "▀",
                    style=f"#{tr:02x}{tg:02x}{tb:02x} on #{br:02x}{bg:02x}{bb:02x}",
                )
        return text
    except Exception:
        logger.debug("Failed to convert image to Rich text")
        return None
