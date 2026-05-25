"""Rich text utilities shared across the codebase."""


def escape_rich_markup(text: str) -> str:
    """Escape Rich markup characters in text to prevent markup errors.

    This is needed to handle content with special characters (e.g., brackets)
    that would otherwise cause MarkupError when rendered in widgets with markup=True.
    """
    return text.replace("[", r"\[").replace("]", r"\]")
