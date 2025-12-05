import sys
from unittest.mock import MagicMock, AsyncMock
import pytest
import asyncio

mock_obj = MagicMock()


modules_to_patch = [
    "openhands",
    "openhands.sdk",
    "openhands.sdk.conversation",
    "openhands.sdk.conversation.state",
    "openhands.sdk.security",                   
    "openhands.sdk.security.confirmation_policy", 
    "openhands_cli.listeners",
    "openhands_cli.listeners.pause_listener",
    "openhands_cli.setup",
    "openhands_cli.user_actions",
    "openhands_cli.user_actions.types",
]

for module in modules_to_patch:
    sys.modules[module] = mock_obj


from openhands_cli.tui.tui import InputManager
from openhands_cli.runner import ConversationRunner



def test_instantiate_input_manager():
    # Act
    manager = InputManager()
    # Assert
    assert manager.session is not None

@pytest.mark.asyncio
async def test_input_manager_reads_async():
    # Arrange
    manager = InputManager()
    # Mockamos o prompt para não travar esperando digitação real
    manager.session.prompt_async = AsyncMock(return_value="hello")
    
    # Act
    result = await manager.read_input()
    
    # Assert
    assert result == "hello"

def test_runner_accepts_input_manager():
    # Arrange
    runner = ConversationRunner(MagicMock())
    input_mgr = InputManager()
    
    # Act
    runner.set_input_manager(input_mgr)
    
    # Assert
    assert runner.input_manager == input_mgr
    
    
@pytest.mark.asyncio
async def test_runner_executes_step_in_executor():
    """Ciclo 4: Testa execução segura (fallback para síncrono)"""
    # Arrange
    mock_conv = MagicMock()
    
    # TRUQUE: Deletamos explicitamente o atributo 'step_async'.
    # Isso obriga o 'hasattr' a retornar False no código, forçando o 'else'.
    del mock_conv.step_async 
    
    # Definimos o método síncrono que esperamos que seja chamado
    mock_conv.step = MagicMock()
    
    runner = ConversationRunner(mock_conv)
    
    # Act
    await runner._step_agent_safe()
    
    # Assert
    # Agora sim verificamos se o método síncrono foi chamado
    mock_conv.step.assert_called_once()
    
@pytest.mark.asyncio
async def test_concurrent_loop_exit():
    # Arrange
    runner = ConversationRunner(MagicMock())
    runner.conversation.state.execution_status = "RUNNING"
    
    mock_input = MagicMock()
    mock_input.read_input = AsyncMock(return_value="/exit")
    runner.set_input_manager(mock_input)
    
    # Act
    await runner.run_concurrent_loop()
    
    # Assert
    # Se o loop não terminar, o teste trava (timeout)
    assert True
    
@pytest.mark.asyncio
async def test_input_interrupts_agent():
    
    mock_conv = MagicMock()
    mock_conv.state.execution_status = "RUNNING"
    
    
    async def slow_agent_step():
        await asyncio.sleep(0.01) 
    
    mock_conv.step_async = AsyncMock(side_effect=slow_agent_step)
    
    
    mock_input = MagicMock()
    
    mock_input.read_input = AsyncMock(side_effect=["ajuda aqui", "/exit"])
    
    runner = ConversationRunner(mock_conv)
    runner.set_input_manager(mock_input)
    
    await runner.run_concurrent_loop()
    
    mock_conv.send_message.assert_called_with("ajuda aqui")