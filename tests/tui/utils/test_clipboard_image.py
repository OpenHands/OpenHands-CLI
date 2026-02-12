"""Tests for clipboard image reading utilities."""

import io
from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.tui.utils.clipboard_image import (
    _validate_image,
    get_image_dimensions,
    get_image_size_display,
    read_image_from_clipboard,
)


# ============================================================================
# get_image_size_display tests
# ============================================================================


class TestGetImageSizeDisplay:
    def test_bytes(self):
        assert get_image_size_display(b"x" * 500) == "500 B"

    def test_kilobytes(self):
        data = b"x" * (50 * 1024)
        assert get_image_size_display(data) == "50 KB"

    def test_megabytes(self):
        data = b"x" * (3 * 1024 * 1024)
        assert get_image_size_display(data) == "3.0 MB"

    def test_zero_bytes(self):
        assert get_image_size_display(b"") == "0 B"


# ============================================================================
# _validate_image tests
# ============================================================================


class TestValidateImage:
    def test_valid_png(self):
        """Valid PNG data should be returned as PNG bytes."""
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_data = buf.getvalue()

        result = _validate_image(png_data)
        assert result is not None
        assert len(result) > 0

    def test_valid_jpeg(self):
        """Valid JPEG data should be converted to PNG."""
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_data = buf.getvalue()

        result = _validate_image(jpeg_data)
        assert result is not None
        # Verify it's PNG by checking the header
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_rgba_image(self):
        """RGBA images should be preserved as PNG with transparency."""
        from PIL import Image

        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        rgba_data = buf.getvalue()

        result = _validate_image(rgba_data)
        assert result is not None

    def test_invalid_data(self):
        """Invalid image data should return None."""
        result = _validate_image(b"not an image")
        assert result is None

    def test_too_large(self):
        """Image exceeding MAX_IMAGE_SIZE should return None."""
        from openhands_cli.tui.utils.clipboard_image import MAX_IMAGE_SIZE

        large_data = b"x" * (MAX_IMAGE_SIZE + 1)
        result = _validate_image(large_data)
        assert result is None

    def test_empty_data(self):
        """Empty data should return None."""
        result = _validate_image(b"")
        assert result is None


# ============================================================================
# get_image_dimensions tests
# ============================================================================


class TestGetImageDimensions:
    def test_valid_image(self):
        from PIL import Image

        img = Image.new("RGB", (100, 50))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        dims = get_image_dimensions(buf.getvalue())
        assert dims == (100, 50)

    def test_invalid_data(self):
        dims = get_image_dimensions(b"not an image")
        assert dims is None


# ============================================================================
# read_image_from_clipboard tests
# ============================================================================


class TestReadImageFromClipboard:
    @patch("openhands_cli.tui.utils.clipboard_image.platform")
    def test_unsupported_platform(self, mock_platform):
        """Windows and other unsupported platforms should return None."""
        mock_platform.system.return_value = "Windows"
        assert read_image_from_clipboard() is None

    @patch("openhands_cli.tui.utils.clipboard_image.platform")
    @patch("openhands_cli.tui.utils.clipboard_image._read_clipboard_macos")
    def test_macos_delegates(self, mock_read, mock_platform):
        """macOS should call _read_clipboard_macos."""
        mock_platform.system.return_value = "Darwin"
        mock_read.return_value = b"png_data"
        result = read_image_from_clipboard()
        assert result == b"png_data"
        mock_read.assert_called_once()

    @patch("openhands_cli.tui.utils.clipboard_image.platform")
    @patch("openhands_cli.tui.utils.clipboard_image._read_clipboard_linux")
    def test_linux_delegates(self, mock_read, mock_platform):
        """Linux should call _read_clipboard_linux."""
        mock_platform.system.return_value = "Linux"
        mock_read.return_value = b"png_data"
        result = read_image_from_clipboard()
        assert result == b"png_data"
        mock_read.assert_called_once()


class TestReadClipboardLinux:
    @patch("openhands_cli.tui.utils.clipboard_image.shutil.which")
    def test_no_tools_available(self, mock_which):
        """Returns None when no clipboard tools are available."""
        mock_which.return_value = None
        from openhands_cli.tui.utils.clipboard_image import _read_clipboard_linux

        assert _read_clipboard_linux() is None

    @patch("openhands_cli.tui.utils.clipboard_image.subprocess.run")
    @patch("openhands_cli.tui.utils.clipboard_image.shutil.which")
    def test_xclip_with_image(self, mock_which, mock_run):
        """xclip returns image data when image/png is available."""
        from PIL import Image

        from openhands_cli.tui.utils.clipboard_image import _read_clipboard_linux

        # Create valid PNG bytes
        img = Image.new("RGB", (10, 10), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        mock_which.side_effect = lambda cmd: "/usr/bin/xclip" if cmd == "xclip" else None

        # First call: check TARGETS
        targets_result = MagicMock()
        targets_result.stdout = "TARGETS\nimage/png\ntext/plain"
        targets_result.returncode = 0

        # Second call: get image data
        image_result = MagicMock()
        image_result.stdout = png_bytes
        image_result.returncode = 0

        mock_run.side_effect = [targets_result, image_result]

        result = _read_clipboard_linux()
        assert result is not None
        # Should be valid PNG
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    @patch("openhands_cli.tui.utils.clipboard_image.subprocess.run")
    @patch("openhands_cli.tui.utils.clipboard_image.shutil.which")
    def test_xclip_no_image(self, mock_which, mock_run):
        """xclip returns None when no image/png in TARGETS."""
        from openhands_cli.tui.utils.clipboard_image import _read_clipboard_linux

        mock_which.side_effect = lambda cmd: "/usr/bin/xclip" if cmd == "xclip" else None

        targets_result = MagicMock()
        targets_result.stdout = "TARGETS\ntext/plain"
        targets_result.returncode = 0

        mock_run.return_value = targets_result

        result = _read_clipboard_linux()
        assert result is None


# ============================================================================
# _load_image_from_uri_text tests (copied file support)
# ============================================================================


class TestLoadImageFromUriText:
    def test_valid_file_uri(self, tmp_path):
        """Valid file:// URI pointing to a real image should return PNG bytes."""
        from PIL import Image

        from openhands_cli.tui.utils.clipboard_image import _load_image_from_uri_text

        # Create a real image file
        img = Image.new("RGB", (10, 10), color="red")
        img_path = tmp_path / "test.png"
        img.save(str(img_path), format="PNG")

        uri_text = f"file://{img_path}"
        result = _load_image_from_uri_text(uri_text)
        assert result is not None
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_gnome_copied_files_format(self, tmp_path):
        """gnome-copied-files format (copy\\nfile://...) should work."""
        from PIL import Image

        from openhands_cli.tui.utils.clipboard_image import _load_image_from_uri_text

        img = Image.new("RGB", (10, 10), color="blue")
        img_path = tmp_path / "photo.jpg"
        img.save(str(img_path), format="JPEG")

        uri_text = f"copy\nfile://{img_path}"
        result = _load_image_from_uri_text(uri_text)
        assert result is not None
        # Should be converted to PNG
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_non_image_file(self, tmp_path):
        """Non-image file extension should return None."""
        from openhands_cli.tui.utils.clipboard_image import _load_image_from_uri_text

        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("hello")

        uri_text = f"file://{txt_file}"
        result = _load_image_from_uri_text(uri_text)
        assert result is None

    def test_nonexistent_file(self):
        """URI pointing to a nonexistent file should return None."""
        from openhands_cli.tui.utils.clipboard_image import _load_image_from_uri_text

        result = _load_image_from_uri_text("file:///tmp/nonexistent_image_12345.png")
        assert result is None

    def test_no_file_uri(self):
        """Text without file:// prefix should return None."""
        from openhands_cli.tui.utils.clipboard_image import _load_image_from_uri_text

        result = _load_image_from_uri_text("just some text")
        assert result is None


# ============================================================================
# image_to_rich_text tests
# ============================================================================


class TestImageToRichText:
    def test_valid_image(self):
        """Valid image should produce a Rich Text object."""
        from PIL import Image

        from openhands_cli.tui.utils.clipboard_image import image_to_rich_text

        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = image_to_rich_text(buf.getvalue(), width=10, height=5)
        assert result is not None
        plain = result.plain
        lines = plain.split("\n")
        assert len(lines) == 5
        assert all(len(line) == 10 for line in lines)

    def test_uses_half_blocks(self):
        """Output should use the upper half block character."""
        from PIL import Image

        from openhands_cli.tui.utils.clipboard_image import image_to_rich_text

        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = image_to_rich_text(buf.getvalue(), width=5, height=3)
        assert result is not None
        assert "\u2580" in result.plain  # ▀ upper half block

    def test_invalid_data(self):
        """Invalid data should return None."""
        from openhands_cli.tui.utils.clipboard_image import image_to_rich_text

        result = image_to_rich_text(b"not an image")
        assert result is None

    def test_rgba_image(self):
        """RGBA image should be converted and rendered."""
        from PIL import Image

        from openhands_cli.tui.utils.clipboard_image import image_to_rich_text

        img = Image.new("RGBA", (20, 20), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = image_to_rich_text(buf.getvalue(), width=10, height=5)
        assert result is not None


# ============================================================================
# ConversationRunner._build_content_blocks tests
# ============================================================================


class TestBuildContentBlocks:
    def test_text_only(self):
        """Text-only message should produce single TextContent block."""
        from openhands.sdk import TextContent

        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        blocks = ConversationRunner._build_content_blocks("hello", None)
        assert len(blocks) == 1
        assert isinstance(blocks[0], TextContent)
        assert blocks[0].text == "hello"

    def test_image_only(self):
        """Image-only message should produce single ImageContent block."""
        from openhands.sdk import ImageContent

        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        blocks = ConversationRunner._build_content_blocks("", b"\x89PNG\r\n\x1a\ndata")
        assert len(blocks) == 1
        assert isinstance(blocks[0], ImageContent)
        assert blocks[0].image_urls[0].startswith("data:image/png;base64,")

    def test_text_and_image(self):
        """Text + image should produce both content blocks."""
        from openhands.sdk import ImageContent, TextContent

        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        blocks = ConversationRunner._build_content_blocks(
            "describe this", b"\x89PNG\r\n\x1a\ndata"
        )
        assert len(blocks) == 2
        assert isinstance(blocks[0], TextContent)
        assert isinstance(blocks[1], ImageContent)

    def test_empty_text_no_image(self):
        """Empty text and no image should produce empty list."""
        from openhands_cli.tui.core.conversation_runner import ConversationRunner

        blocks = ConversationRunner._build_content_blocks("", None)
        assert len(blocks) == 0
