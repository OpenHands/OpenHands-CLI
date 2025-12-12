import argparse
from collections.abc import Sequence


def split_flags_and_positionals(tokens: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split tokens into two lists: flag arguments and positional arguments.

    Flags:
      • Tokens starting with ``--``.
      • A flag consumes the next token as its value *only if* it exists and does
        not start with ``--``.
        Examples:
            --model gpt4      → value = "gpt4"
            --verbose --foo   → "--verbose" has no value; "--foo" is another flag.

    Positionals:
      • Tokens that do NOT start with ``--``.
      • Their meaning comes from their order (e.g., ``mcp add NAME TARGET``).

    This function does not perform full argparse logic—it only groups tokens so
    the caller can reorder or inspect them safely.

    Returns:
        (flag_args, positional_args)

    """

    flag_args: list[str] = []
    positional_args: list[str] = []

    for index, token in enumerate(tokens):
        # Flag indicator
        if token.startswith("--"):
            flag_args.append(token)

        # Value after a flag, should be grouped with the flag
        elif index > 0 and tokens[index - 1].startswith("--"):
            flag_args.append(token)

        # Value that isn't next to a flag, must be positional
        else:
            positional_args.append(token)

    return flag_args, positional_args


def preprocess_mcp_args(raw_args: Sequence[str]) -> list[str]:
    """Normalize argv for ``mcp add`` so argparse can parse it reliably.

    Argparse does **not** reorder arguments by itself - it processes them in the
    order they appear. For the ``mcp add`` subcommand we want a stable shape:

        mcp add [flags...] [positionals...] -- [command args...]

    This helper rewrites only ``mcp add`` invocations that contain ``--`` to put
    all flags (and their values) before the positional arguments.

    In other words, it converts argv like:

        # user-typed form (mixed flags/positionals)
        ["mcp", "add", "my-mcp", "--target", "python", "--", "echo", "hi"]

    into:

        # normalized form handed to argparse
        ["mcp", "add", "--target", "python", "my-mcp", "--", "echo", "hi"]

    Another example:

        # user-typed
        ["mcp", "add", "my-mcp", "python", "--foo", "bar", "--", "echo", "hi"]

        # becomes
        ["mcp", "add", "--foo", "bar", "my-mcp", "python", "--", "echo", "hi"]

    For everything that is **not** ``mcp add`` with a ``--`` separator, this
    function returns ``raw_args`` unchanged and argparse behaves normally.

    Args:
        raw_args: Tokens after the program name (i.e. like sys.argv[1:]).

    Returns:
        A new list of arguments with ``mcp add`` calls normalized.
    """
    args = list(raw_args)

    # Only rewrite `mcp add` commands
    if len(args) < 3 or args[0] != "mcp" or args[1] != "add":
        return args

    # If there's no `--`, nothing to normalize
    try:
        separator_index = args.index("--")
    except ValueError:
        return args

    # Split around the `--` separator
    before_double_dash = args[:separator_index]
    after_double_dash = args[separator_index + 1 :]  # skip the `--` itself

    # Everything after "mcp add" but before `--`
    mcp_add_payload = before_double_dash[2:]

    flag_args, positional_args = split_flags_and_positionals(mcp_add_payload)

    # Rebuild:
    #   mcp add [flags...] [positionals...] [-- remaining...]
    normalized_args: list[str] = ["mcp", "add", *flag_args, *positional_args]

    if after_double_dash:
        normalized_args.extend(["--", *after_double_dash])

    return normalized_args


def add_confirmation_mode_args(
    parser_or_group: argparse.ArgumentParser | argparse._MutuallyExclusiveGroup,
) -> None:
    """Add confirmation mode arguments to a parser or mutually exclusive group.

    Args:
        parser_or_group: Either an ArgumentParser or a mutually exclusive group
    """
    parser_or_group.add_argument(
        "--always-approve",
        action="store_true",
        help="Auto-approve all actions without asking for confirmation",
    )
    parser_or_group.add_argument(
        "--llm-approve",
        action="store_true",
        help=(
            "Enable LLM-based security analyzer "
            "(only confirm LLM-predicted high-risk actions)"
        ),
    )
