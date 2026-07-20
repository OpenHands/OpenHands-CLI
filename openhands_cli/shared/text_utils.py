"""Shared text utilities for display and formatting."""

ELLIPSIS = "…"


def truncate_text(
    text: str,
    max_length: int = 70,
    *,
    from_start: bool = True,
    ellipsis: str = ELLIPSIS,
) -> str:
    """Truncate text with ellipsis if it exceeds max_length.

    Args:
        text: The text to truncate.
        max_length: Maximum length before truncation.
        from_start: If True, keep the start and add ellipsis at end.
                   If False, keep the end and add ellipsis at start (for paths).
        ellipsis: The ellipsis string to use (default: "…").

    Returns:
        The truncated text, or original text if within max_length.
    """
    if len(text) <= max_length:
        return text

    if from_start:
        return text[: max_length - len(ellipsis)] + ellipsis
    else:
        return ellipsis + text[-(max_length - len(ellipsis)) :]


def clean_for_display(text: str, max_length: int = 70) -> str:
    """Strip, collapse newlines to spaces, and truncate text for display.

    Args:
        text: The text to clean.
        max_length: Maximum length before truncation.

    Returns:
        Cleaned and truncated text.
    """
    cleaned = str(text).strip().replace("\n", " ").replace("\r", " ")
    return truncate_text(cleaned, max_length)
