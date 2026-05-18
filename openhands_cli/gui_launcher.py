"""GUI launcher for OpenHands CLI."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from openhands_cli.locations import get_persistence_dir


console = Console(highlight=False, soft_wrap=True)


def _format_docker_command_for_logging(cmd: list[str]) -> str:
    """Format a Docker command for logging."""
    cmd_str = " ".join(cmd)
    return f"Running Docker command: {cmd_str}"


def check_docker_requirements() -> bool:
    """Check if Docker is installed and running.

    Returns:
        bool: True if Docker is available and running, False otherwise.
    """
    # Check if Docker is installed
    if not shutil.which("docker"):
        console.print(
            "❌ Docker is not installed or not in PATH.",
            style="red",
            markup=False,
        )
        console.print(
            "Please install Docker first: https://docs.docker.com/get-docker/",
            style="grey50",
            markup=False,
        )
        return False

    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            console.print(
                "❌ Docker daemon is not running.",
                style="red",
                markup=False,
            )
            console.print(
                "Please start Docker and try again.",
                style="grey50",
                markup=False,
            )
            return False
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        console.print(
            "❌ Failed to check Docker status.",
            style="red",
            markup=False,
        )
        console.print(f"Error: {e}", style="grey50", markup=False)
        return False

    return True


def ensure_config_dir_exists() -> Path:
    """Ensure the OpenHands configuration directory exists and return its path."""
    path = Path(get_persistence_dir())
    path.mkdir(exist_ok=True, parents=True)
    return path


def get_openhands_version() -> str:
    """Get the OpenHands version for Docker images.

    Returns:
        str: The version string to use for Docker images
    """
    # For now, use 'latest' as the default version
    # In the future, this could be read from a version file or environment variable
    return os.environ.get("OPENHANDS_VERSION", "latest")


def launch_gui_server(mount_cwd: bool = False, gpu: bool = False) -> None:
    """Launch the OpenHands GUI server using Docker.

    Args:
        mount_cwd: If True, mount the current working directory into the container.
        gpu: If True, enable GPU support by mounting all GPUs into the
            container via nvidia-docker.
    """
    console.print("🚀 Launching OpenHands GUI server...", style="blue", markup=False)
    console.print()

    # Check Docker requirements
    if not check_docker_requirements():
        sys.exit(1)

    # Ensure config directory exists
    config_dir = ensure_config_dir_exists()

    # Get the current version for the Docker image
    version = get_openhands_version()
    app_image = f"docker.openhands.dev/openhands/openhands:{version}"

    # Note: We intentionally do NOT set AGENT_SERVER_IMAGE_REPOSITORY/TAG env vars.
    # The OpenHands app image has a built-in default agent-server image that is
    # tested and compatible with that specific app version. Setting these env vars
    # could cause version mismatches between the app and agent server.

    console.print("✅ Starting OpenHands GUI server...", style="green", markup=False)
    console.print(
        "The server will be available at: http://localhost:3000",
        style="grey50",
        markup=False,
    )
    console.print("Press Ctrl+C to stop the server.", style="grey50", markup=False)
    console.print()

    # Build the Docker command
    docker_cmd = [
        "docker",
        "run",
        "-it",
        "--rm",
        "--pull=always",
        "-e",
        "LOG_ALL_EVENTS=true",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{config_dir}:/.openhands",
    ]

    # Add GPU support if requested
    if gpu:
        console.print(
            "🖥️ Enabling GPU support via nvidia-docker...",
            style="green",
            markup=False,
        )
        # Add the --gpus all flag to enable all GPUs
        docker_cmd.insert(2, "--gpus")
        docker_cmd.insert(3, "all")
        # Add environment variable to pass GPU support to sandbox containers
        docker_cmd.extend(
            [
                "-e",
                "SANDBOX_ENABLE_GPU=true",
            ]
        )

    # Add current working directory mount if requested
    if mount_cwd:
        cwd = Path.cwd()
        # Following the documentation at
        # https://docs.openhands.dev/usage/runtimes/docker#connecting-to-your-filesystem
        docker_cmd.extend(
            [
                "-e",
                f"SANDBOX_VOLUMES={cwd}:/workspace:rw",
            ]
        )

        # Set user ID for Unix-like systems only
        if os.name != "nt":  # Not Windows
            try:
                user_id = subprocess.check_output(["id", "-u"], text=True).strip()
                docker_cmd.extend(["-e", f"SANDBOX_USER_ID={user_id}"])
            except (subprocess.CalledProcessError, FileNotFoundError):
                # If 'id' command fails or doesn't exist, skip setting user ID
                pass
        # Print the folder that will be mounted to inform the user
        console.print(
            f"[green]📂 Mounting current directory:[/green] "
            f"[yellow]{escape(str(cwd))}[/yellow] "
            f"[green]to[/green] [yellow]/workspace[/yellow]"
        )

    docker_cmd.extend(
        [
            "-p",
            "127.0.0.1:3000:3000",
            "--add-host",
            "host.docker.internal:host-gateway",
            "--name",
            "openhands-app",
            app_image,
        ]
    )

    try:
        # Log and run the Docker command
        console.print(
            _format_docker_command_for_logging(docker_cmd),
            style="grey50",
            markup=False,
        )
        subprocess.run(docker_cmd, check=True)
    except subprocess.CalledProcessError as e:
        console.print()
        console.print(
            "❌ Failed to start OpenHands GUI server.",
            style="red",
            markup=False,
        )
        console.print(f"Error: {e}", style="grey50", markup=False)
        sys.exit(1)
    except KeyboardInterrupt:
        console.print()
        console.print(
            "✓ OpenHands GUI server stopped successfully.",
            style="green",
            markup=False,
        )
        sys.exit(0)
