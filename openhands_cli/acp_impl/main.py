"""OpenHands ACP Main Entry Point."""

import asyncio
import logging
import sys

from .agent import run_acp_server


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

logger = logging.getLogger(__name__)


async def run_acp_agent() -> None:
    """Run the ACP agent server (alias for run_acp_server)."""
    await run_acp_server()


if __name__ == "__main__":
    asyncio.run(run_acp_server())
