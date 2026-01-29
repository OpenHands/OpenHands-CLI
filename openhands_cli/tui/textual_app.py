"""OpenHands CLI TUI application.

This is the main Textual application for the OpenHands CLI. The architecture
separates concerns between App (shell/navigation), ConversationView (state/lifecycle),
and InputAreaContainer (slash command handling).

Widget Hierarchy::

    OpenHandsApp
    └── Horizontal(#content_area)
        └── ConversationView(#conversation_view)  ← Owns state + ConversationRunner
            ├── ScrollableContent(#scroll_view)  ← Scrollable conversation content
            │   ├── SplashContent(#splash_content) ← data_bind to conversation_id
            │   └── ... conversation widgets (dynamically added)
            └── InputAreaContainer(#input_area)  ← docked to bottom
                ├── WorkingStatusLine (data_bind)
                ├── InputField          ← Posts messages
                └── InfoStatusLine (data_bind)
    └── Footer

Message Flow:
    InputField → ConversationView
        - UserInputSubmitted: ConversationView renders and processes with runner
        - SlashCommandSubmitted: InputAreaContainer executes command (stops bubbling)
        - NewConversationRequested: ConversationView handles /new command

Responsibilities:
    - InputAreaContainer: Slash command execution
    - ConversationView: State management, ConversationRunner lifecycle, content rendering
    - ScrollableContent: Scrollable container for splash + conversation widgets
    - OpenHandsApp: Screen/modal management, side panels, global key bindings
    - SplashContent: Displays splash screen, auto-updates via conversation_id binding
"""

import uuid
from collections.abc import Iterable
from typing import ClassVar

from textual import events, getters, on
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, TextArea
from textual_autocomplete import AutoComplete

from openhands.sdk import BaseConversation
from openhands.sdk.event import ActionEvent
from openhands.sdk.security.confirmation_policy import (
    AlwaysConfirm,
    ConfirmationPolicyBase,
    ConfirmRisky,
    NeverConfirm,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands_cli.conversations.store.local import LocalFileStore
from openhands_cli.locations import get_conversations_dir
from openhands_cli.stores import AgentStore, MissingEnvironmentVariablesError
from openhands_cli.theme import OPENHANDS_THEME
from openhands_cli.tui.core import ConversationFinished, ConversationView
from openhands_cli.tui.core.conversation_runner import ConversationRunner
from openhands_cli.tui.core.conversation_switcher import ConversationSwitcher
from openhands_cli.tui.modals import SettingsScreen
from openhands_cli.tui.modals.exit_modal import ExitConfirmationModal
from openhands_cli.tui.panels.confirmation_panel import InlineConfirmationPanel
from openhands_cli.tui.panels.history_side_panel import (
    HistorySidePanel,
    SwitchConversationRequest,
)
from openhands_cli.tui.panels.mcp_side_panel import MCPSidePanel
from openhands_cli.tui.panels.plan_side_panel import PlanSidePanel
from openhands_cli.tui.widgets import InputField, ScrollableContent
from openhands_cli.tui.widgets.collapsible import (
    Collapsible,
    CollapsibleNavigationMixin,
    CollapsibleTitle,
)
from openhands_cli.tui.widgets.splash import SplashContent
from openhands_cli.user_actions.types import UserConfirmation


class OpenHandsApp(CollapsibleNavigationMixin, App):
    """A minimal textual app for OpenHands CLI with scrollable main display."""

    # Key bindings
    BINDINGS: ClassVar = [
        ("ctrl+l", "toggle_input_mode", "Toggle single/multi-line input"),
        ("ctrl+o", "toggle_cells", "Toggle Cells"),
        ("ctrl+j", "submit_textarea", "Submit multi-line input"),
        ("escape", "pause_conversation", "Pause the conversation"),
        ("ctrl+q", "request_quit", "Quit the application"),
        ("ctrl+c", "request_quit", "Quit the application"),
        ("ctrl+d", "request_quit", "Quit the application"),
    ]

    input_field: getters.query_one[InputField] = getters.query_one(InputField)
    scroll_view: getters.query_one[ScrollableContent] = getters.query_one(
        "#scroll_view"
    )
    content_area: getters.query_one[Horizontal] = getters.query_one("#content_area")

    @property
    def conversation_id(self) -> uuid.UUID:
        """Get current conversation ID from ConversationView (source of truth)."""
        return self.conversation_view.conversation_id

    @conversation_id.setter
    def conversation_id(self, value: uuid.UUID) -> None:
        """Set conversation ID in ConversationView (source of truth)."""
        self.conversation_view.conversation_id = value

    @property
    def conversation_runner(self) -> ConversationRunner | None:
        """Get conversation runner from ConversationView (source of truth)."""
        return self.conversation_view.conversation_runner

    @conversation_runner.setter
    def conversation_runner(self, value: ConversationRunner | None) -> None:
        """Set conversation runner in ConversationView (source of truth)."""
        self.conversation_view.conversation_runner = value

    def __init__(
        self,
        exit_confirmation: bool = True,
        resume_conversation_id: uuid.UUID | None = None,
        queued_inputs: list[str] | None = None,
        initial_confirmation_policy: ConfirmationPolicyBase | None = None,
        headless_mode: bool = False,
        json_mode: bool = False,
        env_overrides_enabled: bool = False,
        critic_disabled: bool = False,
        **kwargs,
    ):
        """Initialize the app with custom OpenHands theme.

        Args:
            exit_confirmation: If True, show confirmation modal before exit.
                             If False, exit immediately.
            resume_conversation_id: Optional conversation ID to resume.
            queued_inputs: Optional list of input strings to queue at the start.
            initial_confirmation_policy: Initial confirmation policy to use.
                                       If None, defaults to AlwaysConfirm.
            headless_mode: If True, run in headless mode.
            json_mode: If True, enable JSON output mode.
            env_overrides_enabled: If True, environment variables will override
                                   stored LLM settings.
            critic_disabled: If True, critic functionality will be disabled.
        """
        super().__init__(**kwargs)

        # ConversationView is the single source of truth for application state
        # It owns the ConversationRunner and all reactive state
        self.conversation_view = ConversationView(
            initial_confirmation_policy=initial_confirmation_policy or AlwaysConfirm(),
            env_overrides_enabled=env_overrides_enabled,
            critic_disabled=critic_disabled,
            json_mode=json_mode,
        )

        # Store exit confirmation setting
        self.exit_confirmation = exit_confirmation

        # Store headless mode setting for auto-exit behavior
        self.headless_mode = headless_mode

        # Store these for _reload_visualizer (still need App-level access)
        self.env_overrides_enabled = env_overrides_enabled

        # conversation_id is owned by ConversationView - we just initialize it here
        initial_conversation_id = (
            resume_conversation_id if resume_conversation_id else uuid.uuid4()
        )
        self.conversation_view.conversation_id = initial_conversation_id

        self.conversation_dir = BaseConversation.get_persistence_dir(
            get_conversations_dir(), initial_conversation_id
        )

        # Store queued inputs (copy to prevent mutating caller's list)
        self.pending_inputs = list(queued_inputs) if queued_inputs else []

        # ConversationRunner is now owned by ConversationView
        self._store = LocalFileStore()
        self._conversation_switcher = ConversationSwitcher(self)

        def reload_visualizer():
            runner = self.conversation_view.conversation_runner
            if runner:
                runner.visualizer.reload_configuration()

        self._reload_visualizer = reload_visualizer

        # Confirmation panel tracking
        self.confirmation_panel: InlineConfirmationPanel | None = None

        # MCP panel tracking
        self.mcp_panel: MCPSidePanel | None = None

        self.plan_panel: PlanSidePanel = PlanSidePanel(self)

        # Register the custom theme
        self.register_theme(OPENHANDS_THEME)

        # Set the theme as active
        self.theme = "openhands"

    CSS_PATH = "textual_app.tcss"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app.

        Widget Hierarchy::

            OpenHandsApp
            └── Horizontal(#content_area)
                └── ConversationView(#conversation_view)  ← Owns state
                    ├── ScrollableContent(#scroll_view)
                    │   ├── SplashContent  ← data_bind
                    │   └── ... conversation content
                    └── InputAreaContainer(#input_area)  ← handles input
                        ├── WorkingStatusLine (data_bind)
                        ├── InputField
                        └── InfoStatusLine (data_bind)
            └── Footer

        Message Flow:
            InputField → InputAreaContainer → ConversationView → OpenHandsApp

        Data Binding:
            All widgets are composed from ConversationView.compose(), so data_bind
            works because the active pump is ConversationView (the reactive owner).
        """
        # Content area - horizontal layout for conversation and optional panels
        with Horizontal(id="content_area"):
            # ConversationView composes scroll_view, input_area and all child widgets
            # This enables data_bind() to work (requires owner as active pump)
            yield self.conversation_view

        # Footer - shows available key bindings
        yield Footer()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "History",
            "Toggle conversation history panel",
            self.action_toggle_history,
        )
        yield SystemCommand(
            "MCP", "View MCP configurations", lambda: MCPSidePanel.toggle(self)
        )
        yield SystemCommand(
            "Plan",
            "View agent plan",
            lambda: self.plan_panel.toggle(),
        )
        yield SystemCommand("Settings", "Configure settings", self.action_open_settings)

    def on_mount(self) -> None:
        """Called when app starts."""
        from openhands_cli.stores import MissingEnvironmentVariablesError

        # Check if user has existing settings
        try:
            initial_setup_required = SettingsScreen.is_initial_setup_required(
                env_overrides_enabled=self.env_overrides_enabled
            )
        except MissingEnvironmentVariablesError as e:
            # Store the error to be re-raised after clean exit
            self._missing_env_vars_error = e
            self.exit()
            return

        if initial_setup_required:
            # In headless mode we cannot open interactive settings.
            if self.headless_mode:
                from rich.console import Console

                console = Console()
                console.print(
                    f"[{OPENHANDS_THEME.error}]Headless mode requires existing "
                    f"settings.[/{OPENHANDS_THEME.error}]\n"
                    f"[bold]Please run:[/bold] [{OPENHANDS_THEME.success}]openhands"
                    f"[/{OPENHANDS_THEME.success}] to configure your settings "
                    f"before using [{OPENHANDS_THEME.accent}]--headless"
                    f"[/{OPENHANDS_THEME.accent}]."
                )
                self.exit()
                return

            # No existing settings - show settings screen first
            self._show_initial_settings()
            return

        # User has settings - proceed with normal startup
        self._initialize_main_ui()

    def _show_initial_settings(self) -> None:
        """Show settings screen for first-time users."""
        settings_screen = SettingsScreen(
            on_settings_saved=[
                self._initialize_main_ui,
                self._reload_visualizer,
            ],
            on_first_time_settings_cancelled=self._handle_initial_setup_cancelled,
            env_overrides_enabled=self.env_overrides_enabled,
        )
        self.push_screen(settings_screen)

    def _handle_initial_setup_cancelled(self) -> None:
        """Handle when initial setup is cancelled - show settings again."""
        # For first-time users, cancelling should loop back to settings
        # This creates the loop until they either save settings or exit
        exit_modal = ExitConfirmationModal(
            on_exit_confirmed=lambda: self.app.exit(),
            on_exit_cancelled=self._show_initial_settings,
        )
        self.app.push_screen(exit_modal)

    @on(ConversationFinished)
    def on_conversation_finished(self, _event: ConversationFinished) -> None:
        """Handle conversation finished."""
        if self.headless_mode:
            self._print_conversation_summary()
            self.exit()

    def _print_conversation_summary(self) -> None:
        """Print conversation summary for headless mode."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.rule import Rule

        console = Console()

        if not self.conversation_runner:
            return

        num_agent_messages, last_agent_message = (
            self.conversation_runner.get_conversation_summary()
        )

        console.print()  # blank line
        console.print(Rule("CONVERSATION SUMMARY"))

        console.print(f"[bold]Number of agent messages:[/bold] {num_agent_messages}")

        console.print("[bold]Last message sent by the agent:[/bold]")
        console.print(
            Panel(
                last_agent_message,
                expand=False,
                border_style="cyan",
                title="Agent",
                title_align="left",
            )
        )

        console.print(Rule())

    def action_open_settings(self) -> None:
        """Action to open the settings screen."""
        # Check if conversation is running
        if self.conversation_runner and self.conversation_runner.is_running:
            self.notify(
                "Settings are not available while a conversation is running. "
                "Please wait for the current conversation to complete.",
                severity="warning",
                timeout=5.0,
            )
            return

        # Open the settings screen for existing users
        settings_screen = SettingsScreen(
            on_settings_saved=[
                self._reload_visualizer,
                self._notify_restart_required,
            ],
            env_overrides_enabled=self.env_overrides_enabled,
        )
        self.push_screen(settings_screen)

    def _notify_restart_required(self) -> None:
        """Notify user that CLI restart is required for agent settings changes.

        Only shows notification if a conversation runner has been instantiated,
        meaning a conversation has already started with the previous settings.

        Note: This callback is only registered for `action_open_settings` (existing
        users), not for `_show_initial_settings` (first-time setup). Additionally,
        during first-time setup, conversation_runner is always None, so even if
        this method were called, no notification would be shown.
        """
        if self.conversation_runner:
            self.notify(
                "Settings saved. Please restart the CLI for changes to take effect.",
                severity="information",
                timeout=10.0,
            )

    def _initialize_main_ui(self) -> None:
        """Initialize the main UI components.

        This method is responsible for:
        1. Checking if the agent has a critic configured
        2. Initializing the splash content (one-time setup)
        3. Processing any queued inputs

        UI lifecycle is owned by OpenHandsApp, not ConversationView. The splash
        content initialization is a direct method call, not a reactive
        state change, because it's a one-time operation.
        """

        splash_content = self.query_one("#splash_content", SplashContent)

        # Check if agent has critic configured
        has_critic = False
        try:
            agent_store = AgentStore()
            agent = agent_store.load_or_create(
                env_overrides_enabled=self.env_overrides_enabled,
                critic_disabled=self.conversation_view._critic_disabled,
            )
            if agent:
                has_critic = agent.critic is not None
        except Exception:
            # If we can't load agent, just continue without critic notice
            pass

        # Initialize splash content - direct call for UI lifecycle
        splash_content.initialize(has_critic=has_critic)

        # Process any queued inputs
        self._process_queued_inputs()

    def _process_queued_inputs(self) -> None:
        """Process any queued inputs from --task or --file arguments.

        Currently processes only the first queued input immediately.
        In the future, this could be extended to process multiple instructions
        from the queue one by one as the agent completes each task.

        Posts UserInputSubmitted to ConversationView, which flows through the same
        path as typed inputs:
        1. ConversationView._on_user_input_submitted() - renders + processes with runner
        """
        from openhands_cli.tui.messages import UserInputSubmitted

        if not self.pending_inputs:
            return

        # Process the first queued input immediately
        user_input = self.pending_inputs.pop(0)

        # Post to InputAreaContainer - reuses the same flow as typed inputs
        self.conversation_view.input_area.post_message(
            UserInputSubmitted(content=user_input)
        )

    def action_request_quit(self) -> None:
        """Action to handle Ctrl+Q key binding.

        Delegates to InputAreaContainer's _command_exit() for consistent behavior.
        """
        self.conversation_view.input_area._command_exit()

    def action_toggle_cells(self) -> None:
        """Action to handle Ctrl+O key binding.

        Collapses all cells if any are expanded, otherwise expands all cells.
        This provides a quick way to minimize or maximize all content at once.
        """
        collapsibles = self.scroll_view.query(Collapsible)

        # If any cell is expanded, collapse all; otherwise expand all
        any_expanded = any(not collapsible.collapsed for collapsible in collapsibles)

        for collapsible in collapsibles:
            collapsible.collapsed = any_expanded

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard navigation.

        - Auto-focus input when user starts typing (allows clicking cells without
          losing typing context)
        - When Tab is pressed from input area, focus the most recent (last) cell
          instead of the first one (unless autocomplete is showing)
        """
        # Handle Tab from input area - focus most recent cell
        # Skip if autocomplete dropdown is visible (Tab is used for selection)
        if event.key == "tab" and isinstance(self.focused, Input | TextArea):
            if not self._is_autocomplete_showing():
                collapsibles = list(self.scroll_view.query(Collapsible))
                if collapsibles:
                    # Focus the last (most recent) collapsible's title
                    last_collapsible = collapsibles[-1]
                    last_title = last_collapsible.query_one(CollapsibleTitle)
                    last_title.focus()
                    last_collapsible.scroll_visible()
                    event.stop()
                    event.prevent_default()
                    return

        # Auto-focus input when user types printable characters
        if event.is_printable and not isinstance(self.focused, Input | TextArea):
            self.input_field.focus_input()

    def _is_autocomplete_showing(self) -> bool:
        """Check if the autocomplete dropdown is currently visible.

        This prevents Tab key interception when user wants to select an
        autocomplete suggestion.
        """
        autocompletes = self.query(AutoComplete)
        return any(ac.display for ac in autocompletes)

    def on_mouse_up(self, _event: events.MouseUp) -> None:
        """Handle mouse up events for auto-copy on text selection.

        When the user finishes selecting text by releasing the mouse button,
        this method checks if there's selected text and copies it to clipboard.
        """
        # Get selected text from the screen
        selected_text = self.screen.get_selected_text()
        if not selected_text:
            return

        # Copy to clipboard and get result
        pyperclip_success = self._copy_to_clipboard(selected_text)

        # Show appropriate notification based on copy result
        if pyperclip_success:
            self.notify(
                "Selection copied to clipboard",
                title="Auto-copy",
                timeout=2,
            )
        elif self._is_linux():
            # On Linux without pyperclip working, OSC 52 may or may not work
            self.notify(
                "Selection copied. May require `sudo apt install xclip`",
                title="Auto-copy",
                timeout=4,
            )
        else:
            self.notify(
                "Selection copied to clipboard",
                title="Auto-copy",
                timeout=2,
            )

    def _is_linux(self) -> bool:
        """Check if the current platform is Linux."""
        import platform

        return platform.system() == "Linux"

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard using pyperclip with OSC 52 fallback.

        Uses a two-layer approach for clipboard access:
        1. Primary: pyperclip for direct OS clipboard access
        2. Fallback: Textual's copy_to_clipboard (OSC 52 escape sequence)

        This ensures clipboard works across different terminal environments.

        Returns:
            True if pyperclip succeeded, False otherwise.
        """
        import pyperclip

        pyperclip_success = False
        # Primary: Try pyperclip for direct OS clipboard access
        try:
            pyperclip.copy(text)
            pyperclip_success = True
        except pyperclip.PyperclipException:
            # pyperclip failed - will try OSC 52 fallback
            pass

        # Also try OSC 52 - this doesn't raise errors, it just sends escape
        # sequences. We do both because pyperclip and OSC 52 can target
        # different clipboards (e.g., remote terminals, tmux, SSH sessions)
        self.copy_to_clipboard(text)

        return pyperclip_success

    def action_pause_conversation(self) -> None:
        """Action to handle Esc key binding - pause the running conversation."""
        # Run the pause operation asynchronously to avoid blocking the UI
        if self.conversation_runner:
            self.conversation_runner.pause_runner_without_blocking()
        else:
            self.notify(message="No running conversation to pause", severity="error")

    def action_toggle_history(self) -> None:
        """Toggle the history side panel."""
        HistorySidePanel.toggle(
            self,
            current_conversation_id=self.conversation_id,
        )

    @on(SwitchConversationRequest)
    def _on_switch_conversation_request(self, event: SwitchConversationRequest) -> None:
        """Handle request from history panel to switch conversations."""
        self._conversation_switcher.switch_to(event.conversation_id)

    def _handle_confirmation_request(
        self, pending_actions: list[ActionEvent]
    ) -> UserConfirmation:
        """Handle confirmation request by showing an inline panel in the scroll view.

        The inline confirmation panel is mounted in the scroll_view area,
        underneath the latest action event collapsible. Since the action details
        are already visible in the collapsible above, this panel only shows
        the confirmation options.

        Args:
            pending_actions: List of pending actions that need confirmation

        Returns:
            UserConfirmation decision from the user
        """
        # This will be called from a background thread, so we need to use
        # call_from_thread to interact with the UI safely
        from concurrent.futures import Future

        # Create a future to wait for the user's decision
        decision_future: Future[UserConfirmation] = Future()

        def show_confirmation_panel():
            """Show the inline confirmation panel in the UI thread."""
            try:
                # Remove any existing confirmation panel
                if self.confirmation_panel:
                    self.confirmation_panel.remove()
                    self.confirmation_panel = None

                # Create callback that will resolve the future
                def on_confirmation_decision(decision: UserConfirmation):
                    # Remove the panel
                    if self.confirmation_panel:
                        self.confirmation_panel.remove()
                        self.confirmation_panel = None
                    # Resolve the future with the decision
                    if not decision_future.done():
                        decision_future.set_result(decision)

                # Create and mount the inline confirmation panel in scroll_view
                # This places it underneath the latest action event collapsible
                self.confirmation_panel = InlineConfirmationPanel(
                    len(pending_actions), on_confirmation_decision
                )
                self.scroll_view.mount(self.confirmation_panel)
                # Scroll to show the confirmation panel
                self.scroll_view.scroll_end(animate=False)

            except Exception:
                # If there's an error, default to DEFER
                if not decision_future.done():
                    decision_future.set_result(UserConfirmation.DEFER)

        # Schedule the UI update on the main thread
        self.call_from_thread(show_confirmation_panel)

        # Wait for the user's decision (this will block the background thread)
        try:
            return decision_future.result(timeout=300)  # 5 minute timeout
        except Exception:
            # If timeout or error, default to DEFER
            return UserConfirmation.DEFER


def main(
    resume_conversation_id: str | None = None,
    queued_inputs: list[str] | None = None,
    always_approve: bool = False,
    llm_approve: bool = False,
    exit_without_confirmation: bool = False,
    headless: bool = False,
    json_mode: bool = False,
    env_overrides_enabled: bool = False,
    critic_disabled: bool = False,
):
    """Run the textual app.

    Args:
        resume_conversation_id: Optional conversation ID to resume.
        queued_inputs: Optional list of input strings to queue at the start.
        always_approve: If True, auto-approve all actions without confirmation.
        llm_approve: If True, use LLM-based security analyzer (ConfirmRisky policy).
        exit_without_confirmation: If True, exit without showing confirmation dialog.
        headless: If True, run in headless mode (no UI output, auto-approve actions).
        json_mode: If True, enable JSON output mode (implies headless).
        env_overrides_enabled: If True, environment variables will override
            stored LLM settings.
        critic_disabled: If True, critic functionality will be disabled.

    Raises:
        MissingEnvironmentVariablesError: If env_overrides_enabled is True but
            required environment variables are missing. The app exits cleanly and
            the error is re-raised to be handled by the entrypoint.
    """

    # Determine if envs are required to be configured
    # Raise error before textual app is run to avoid traceback
    try:
        SettingsScreen.is_initial_setup_required(
            env_overrides_enabled=env_overrides_enabled
        )
    except MissingEnvironmentVariablesError as e:
        raise e

    # Determine initial confirmation policy from CLI arguments
    # If headless mode is enabled, always use NeverConfirm (auto-approve all actions)
    initial_confirmation_policy = AlwaysConfirm()  # Default
    if headless or always_approve:
        initial_confirmation_policy = NeverConfirm()
    elif llm_approve:
        initial_confirmation_policy = ConfirmRisky(threshold=SecurityRisk.HIGH)

    app = OpenHandsApp(
        exit_confirmation=not exit_without_confirmation,
        resume_conversation_id=uuid.UUID(resume_conversation_id)
        if resume_conversation_id
        else None,
        queued_inputs=queued_inputs,
        initial_confirmation_policy=initial_confirmation_policy,
        headless_mode=headless,
        json_mode=json_mode,
        env_overrides_enabled=env_overrides_enabled,
        critic_disabled=critic_disabled,
    )

    app.run(headless=headless)

    return app.conversation_id


if __name__ == "__main__":
    main()
