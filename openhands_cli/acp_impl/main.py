"""OpenHands ACP Main Entry Point."""

import asyncio
import logging
import os
import sys
from datetime import datetime

from openhands.sdk.logger import DEBUG

from .agent import run_acp_server


def setup_logging_and_redirect() -> None:
    """Setup logging and redirect stderr based on DEBUG flag.

    Note: stdout is NOT redirected as it's used by stdio_streams() for ACP protocol.
    Only stderr and logging output are redirected.
    """
    if DEBUG:
        # When DEBUG is true, redirect stderr and logging to log file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        log_file = f"openhands_acp_{timestamp}.log"
        log_fd = open(log_file, "a")

        # Redirect stderr to log file
        sys.stderr = log_fd

        # Configure logging to same file
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(log_fd)],
        )
        logger = logging.getLogger(__name__)
        logger.info(f"Debug mode enabled, logging to {log_file}")
    else:
        # When DEBUG is false, redirect stderr and logging to /dev/null
        devnull = open(os.devnull, "w")

        # Redirect stderr to /dev/null
        sys.stderr = devnull

        # Configure logging to /dev/null
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(devnull)],
        )


async def run_acp_agent() -> None:
    """Run the ACP agent server (alias for run_acp_server)."""
    setup_logging_and_redirect()
    await run_acp_server()


if __name__ == "__main__":
    setup_logging_and_redirect()
    asyncio.run(run_acp_server())
