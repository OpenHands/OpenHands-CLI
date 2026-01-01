from acp import Client
from openhands_cli.acp_impl.slash_commands import (
    get_available_slash_commands,
)

from acp.schema import (
    AvailableCommandsUpdate,
)

class SharedACPAgentHandler:
    def __init__(
        self,
        conn: Client
    ): 
        self._conn = conn

    async def send_available_commands(self, session_id: str) -> None:
        """Send available slash commands to the client.

        Args:
            session_id: The session ID
        """
        await self._conn.session_update(
            session_id=session_id,
            update=AvailableCommandsUpdate(
                session_update="available_commands_update",
                available_commands=get_available_slash_commands(),
            ),
        )
    