"""Text utilities shared across the codebase."""

ELLIPSIS = "..."


def truncate_text(
    text: str,
    max_length: int,
    *,
    from_start: bool = True,
    collapse_whitespace: bool = True,
) -> str:
    """Truncate text with ellipsis if it exceeds max_length.

    Args:
        text: The text to truncate.
        max_length: Maximum length before truncation.
        from_start: If True, keep the start and add ellipsis at end.
                   If False, keep the end and add ellipsis at start (useful for paths).
        collapse_whitespace: If True, replace newlines and carriage returns with spaces.

    Returns:
        The truncated text, or the original text if it's within the limit.
    """
    if collapse_whitespace:
        text = text.replace("\n", " ").replace("\r", " ")

    if len(text) <= max_length:
        return text

    ellipsis_len = len(ELLIPSIS)
    if from_start:
        return text[: max_length - ellipsis_len] + ELLIPSIS
    else:
        return ELLIPSIS + text[-(max_length - ellipsis_len) :]
