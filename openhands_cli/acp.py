#!/usr/bin/env python3
"""Standalone entry point for the OpenHands ACP server.

This module provides the ``openhands-acp`` console script declared in
``pyproject.toml``.  It is intentionally thin: parse CLI flags, configure
logging to *stderr* (ACP uses stdio for its JSON-RPC transport), and
hand off to :func:`openhands_cli.acp_impl.agent.launcher.run_acp_server`.
"""

import argparse
import asyncio
import logging
import os
import sys
import warnings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openhands-acp",
        description=(
            "Run OpenHands as an ACP (Agent Client Protocol) server over stdio."
        ),
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--always-approve",
        "--yolo",
        action="store_true",
        default=False,
        help="Automatically approve all actions without asking for confirmation.",
    )
    mode_group.add_argument(
        "--llm-approve",
        action="store_true",
        default=False,
        help="Use LLM security analyzer to auto-approve safe actions.",
    )

    parser.add_argument(
        "--override-with-envs",
        action="store_true",
        default=False,
        help="Override LLM settings with environment variables.",
    )

    parser.add_argument(
        "--cloud",
        action="store_true",
        default=False,
        help="Use OpenHands Cloud workspace instead of local workspace.",
    )

    parser.add_argument(
        "--cloud-url",
        type=str,
        default=os.getenv("OPENHANDS_CLOUD_URL", "https://app.all-hands.dev"),
        help="OpenHands Cloud API URL (default: %(default)s).",
    )

    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        metavar="CONVERSATION_ID",
        help="Resume an existing conversation by ID.",
    )

    return parser


def main() -> None:
    """Entry point for the ``openhands-acp`` console script."""

    # --- logging to stderr (stdout is the ACP transport) ----------------
    debug_env = os.getenv("DEBUG", "false").lower()
    if debug_env in ("1", "true"):
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING
        warnings.filterwarnings("ignore")

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # --- parse args -----------------------------------------------------
    parser = _build_parser()
    args = parser.parse_args()

    # --- determine confirmation mode ------------------------------------
    from openhands_cli.acp_impl.confirmation import ConfirmationMode

    confirmation_mode: ConfirmationMode = "always-ask"
    if args.always_approve:
        confirmation_mode = "always-approve"
    elif args.llm_approve:
        confirmation_mode = "llm-approve"

    env_overrides_enabled: bool = args.override_with_envs

    # --- launch the ACP server ------------------------------------------
    from openhands_cli.acp_impl.agent import run_acp_server

    asyncio.run(
        run_acp_server(
            initial_confirmation_mode=confirmation_mode,
            resume_conversation_id=args.resume,
            cloud=args.cloud,
            cloud_api_url=args.cloud_url,
            env_overrides_enabled=env_overrides_enabled,
        )
    )


if __name__ == "__main__":
    main()
