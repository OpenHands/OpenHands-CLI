"""LLM Profiles tab component for the settings modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Input, Label, Select, Static
from textual.widgets._select import NoSelection

from openhands.sdk import Agent
from openhands_cli.stores import AgentStore


class ProfilesTab(Container):
    """Tab component for managing LLM profiles.

    Allows users to:
    - View and load saved LLM profiles
    - Save the current LLM configuration as a new profile
    - Delete existing profiles
    """

    def __init__(self, **kwargs):
        """Initialize the profiles tab."""
        super().__init__(**kwargs)
        self.agent_store = AgentStore()

    def compose(self) -> ComposeResult:
        """Compose the profiles tab content."""
        with VerticalScroll(id="profiles_content"):
            # Load Profile Section
            yield Static("Load Profile", classes="form_section_title")
            yield Static(
                "Select a saved LLM profile to use as your active configuration.",
                classes="form_help",
            )

            with Container(classes="form_group"):
                yield Label("Available Profiles:", classes="form_label")
                yield Select(
                    [],
                    id="profile_select",
                    prompt="Select a profile",
                    classes="form_input",
                )

            with Horizontal(classes="profile_buttons"):
                yield Button(
                    "Load Profile",
                    id="load_profile_btn",
                    variant="primary",
                    classes="profile_button",
                )
                yield Button(
                    "Delete Profile",
                    id="delete_profile_btn",
                    variant="error",
                    classes="profile_button",
                )

            # Save Profile Section
            yield Static("Save as Profile", classes="form_section_title")
            yield Static(
                "Save your current LLM configuration as a reusable profile.",
                classes="form_help",
            )

            with Container(classes="form_group"):
                yield Label("Profile Name:", classes="form_label")
                yield Input(
                    placeholder="e.g., work, personal, claude-opus",
                    id="profile_name_input",
                    classes="form_input",
                )

            yield Button(
                "Save Current as Profile",
                id="save_profile_btn",
                variant="success",
                classes="profile_button save_profile_button",
            )

    def on_mount(self) -> None:
        """Initialize the profile list when mounted."""
        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        """Refresh the profile dropdown with available profiles."""
        try:
            profiles = self.agent_store.list_profiles()
            select = self.query_one("#profile_select", Select)

            if profiles:
                # Remove .json extension for display
                options = [
                    (name.removesuffix(".json"), name) for name in sorted(profiles)
                ]
                select.set_options(options)
            else:
                select.set_options([])
        except Exception:
            # If we can't list profiles, just show empty
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "load_profile_btn":
            self._load_selected_profile()
        elif event.button.id == "save_profile_btn":
            self._save_current_as_profile()
        elif event.button.id == "delete_profile_btn":
            self._delete_selected_profile()

    def _load_selected_profile(self) -> None:
        """Load the selected profile and update the settings form."""
        select = self.query_one("#profile_select", Select)

        if isinstance(select.value, NoSelection) or select.value is None:
            self.app.notify("Please select a profile to load", severity="warning")
            return

        profile_name = str(select.value).removesuffix(".json")

        try:
            agent = self.agent_store.swap_llm_from_profile(profile_name)
            self.app.notify(
                f"Profile '{profile_name}' loaded! Model: {agent.llm.model}",
                severity="information",
            )

            # Notify parent to update settings form
            self.post_message(ProfileLoaded(profile_name, agent))

        except FileNotFoundError:
            self.app.notify(f"Profile '{profile_name}' not found", severity="error")
        except ValueError as e:
            self.app.notify(f"Failed to load profile: {e}", severity="error")
        except TimeoutError:
            self.app.notify(
                "Could not acquire lock on profiles. Please try again.",
                severity="error",
            )

    def _save_current_as_profile(self) -> None:
        """Save the current agent's LLM as a new profile."""
        profile_name_input = self.query_one("#profile_name_input", Input)
        profile_name = profile_name_input.value.strip()

        if not profile_name:
            self.app.notify("Please enter a profile name", severity="warning")
            return

        # Check if agent exists
        current_agent = self.agent_store.load_from_disk()
        if current_agent is None:
            self.app.notify(
                "No agent configured. Please save settings first.",
                severity="error",
            )
            return

        try:
            self.agent_store.save_llm_as_profile(profile_name, current_agent.llm)
            self.app.notify(
                f"Profile '{profile_name}' saved successfully!",
                severity="information",
            )

            # Clear input and refresh list
            profile_name_input.value = ""
            self._refresh_profile_list()

        except ValueError as e:
            self.app.notify(f"Invalid profile name: {e}", severity="error")
        except TimeoutError:
            self.app.notify(
                "Could not acquire lock on profiles. Please try again.",
                severity="error",
            )

    def _delete_selected_profile(self) -> None:
        """Delete the selected profile."""
        select = self.query_one("#profile_select", Select)

        if isinstance(select.value, NoSelection) or select.value is None:
            self.app.notify("Please select a profile to delete", severity="warning")
            return

        profile_name = str(select.value).removesuffix(".json")

        try:
            self.agent_store.delete_profile(profile_name)
            self.app.notify(
                f"Profile '{profile_name}' deleted",
                severity="information",
            )
            self._refresh_profile_list()

        except TimeoutError:
            self.app.notify(
                "Could not acquire lock on profiles. Please try again.",
                severity="error",
            )


class ProfileLoaded(Message):
    """Message sent when a profile is loaded."""

    def __init__(self, profile_name: str, agent: Agent) -> None:
        self.profile_name = profile_name
        self.agent = agent
        super().__init__()
