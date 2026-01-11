"""GUI launcher for OpenHands CLI."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from openhands_cli.locations import PERSISTENCE_DIR


def _is_wsl2() -> bool:
    """Check if running in WSL2 environment."""
    try:
        release = platform.release()
        return "microsoft" in release.lower() or release.endswith("microsoft-standard-WSL2")
    except Exception:
        return False


def _wsl_to_windows_path(wsl_path: str) -> str:
    """Convert WSL2 path to Windows path for Docker Desktop.

    Docker Desktop on Windows with WSL2 backend expects Windows-style paths
    (e.g., D:/folder) for volume mounts, not WSL2 paths (e.g., /mnt/d/folder).

    Args:
        wsl_path: A path that may be in WSL2 format (e.g., /mnt/d/ai-data/workspace)

    Returns:
        Windows-style path (e.g., D:/ai-data/workspace) if input is a WSL2 mount path,
        otherwise returns the original path unchanged.
    """
    # Only convert paths that start with /mnt/ followed by a single drive letter
    if wsl_path.startswith("/mnt/") and len(wsl_path) > 5:
        parts = wsl_path[5:].split("/", 1)
        if len(parts) >= 1 and len(parts[0]) == 1 and parts[0].isalpha():
            drive_letter = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""
            return f"{drive_letter}:/{rest}"
    return wsl_path


def _format_docker_command_for_logging(cmd: list[str]) -> str:
    """Format a Docker command for logging with grey color.

    Args:
        cmd (list[str]): The Docker command as a list of strings

    Returns:
        str: The formatted command string in grey HTML color
    """
    cmd_str = " ".join(cmd)
    return f"<grey>Running Docker command: {cmd_str}</grey>"


def check_docker_requirements() -> bool:
    """Check if Docker is installed and running.

    Returns:
        bool: True if Docker is available and running, False otherwise.
    """
    # Check if Docker is installed
    if not shutil.which("docker"):
        print_formatted_text(
            HTML("<ansired>❌ Docker is not installed or not in PATH.</ansired>")
        )
        print_formatted_text(
            HTML(
                "<grey>Please install Docker first: https://docs.docker.com/get-docker/</grey>"
            )
        )
        return False

    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print_formatted_text(
                HTML("<ansired>❌ Docker daemon is not running.</ansired>")
            )
            print_formatted_text(
                HTML("<grey>Please start Docker and try again.</grey>")
            )
            return False
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        print_formatted_text(
            HTML("<ansired>❌ Failed to check Docker status.</ansired>")
        )
        print_formatted_text(HTML(f"<grey>Error: {e}</grey>"))
        return False

    return True


def ensure_config_dir_exists() -> Path:
    """Ensure the OpenHands configuration directory exists and return its path."""
    path = Path(PERSISTENCE_DIR)
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
    print_formatted_text(
        HTML("<ansiblue>🚀 Launching OpenHands GUI server...</ansiblue>")
    )
    print_formatted_text("")

    # Check Docker requirements
    if not check_docker_requirements():
        sys.exit(1)

    # Ensure config directory exists
    config_dir = ensure_config_dir_exists()

    # Get the current version for the Docker image
    version = get_openhands_version()
    runtime_image = f"docker.openhands.dev/openhands/runtime:{version}-nikolaik"
    app_image = f"docker.openhands.dev/openhands/openhands:{version}"

    print_formatted_text(HTML("<grey>Pulling required Docker images...</grey>"))

    # Pull the runtime image first
    pull_cmd = ["docker", "pull", runtime_image]
    print_formatted_text(HTML(_format_docker_command_for_logging(pull_cmd)))
    try:
        subprocess.run(pull_cmd, check=True)
    except subprocess.CalledProcessError:
        print_formatted_text(
            HTML("<ansired>❌ Failed to pull runtime image.</ansired>")
        )
        sys.exit(1)

    print_formatted_text("")
    print_formatted_text(
        HTML("<ansigreen>✅ Starting OpenHands GUI server...</ansigreen>")
    )
    print_formatted_text(
        HTML("<grey>The server will be available at: http://localhost:3000</grey>")
    )
    print_formatted_text(HTML("<grey>Press Ctrl+C to stop the server.</grey>"))
    print_formatted_text("")

    # Build the Docker command
    docker_cmd = [
        "docker",
        "run",
        "-it",
        "--rm",
        "--pull=always",
        "-e",
        f"SANDBOX_RUNTIME_CONTAINER_IMAGE={runtime_image}",
        "-e",
        "LOG_ALL_EVENTS=true",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{config_dir}:/.openhands",
    ]

    # Add GPU support if requested
    if gpu:
        print_formatted_text(
            HTML("<ansigreen>🖥️ Enabling GPU support via nvidia-docker...</ansigreen>")
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
        cwd = str(Path.cwd())

        # Convert WSL2 paths to Windows paths for Docker Desktop compatibility
        # Docker Desktop on Windows with WSL2 backend expects Windows-style paths
        if _is_wsl2():
            mount_path = _wsl_to_windows_path(cwd)
            if mount_path != cwd:
                print_formatted_text(
                    HTML(
                        f"<grey>WSL2 detected: Converting path for Docker Desktop</grey>"
                    )
                )
                print_formatted_text(
                    HTML(f"<grey>  WSL2 path: {cwd}</grey>")
                )
                print_formatted_text(
                    HTML(f"<grey>  Docker path: {mount_path}</grey>")
                )
        else:
            mount_path = cwd

        # Following the documentation at https://docs.all-hands.dev/usage/runtimes/docker#connecting-to-your-filesystem
        docker_cmd.extend(
            [
                "-e",
                f"SANDBOX_VOLUMES={mount_path}:/workspace:rw",
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
        print_formatted_text(
            HTML(
                f"<ansigreen>📂 Mounting current directory:</ansigreen> "
                f"<ansiyellow>{cwd}</ansiyellow> <ansigreen>to</ansigreen> "
                f"<ansiyellow>/workspace</ansiyellow>"
            )
        )

    docker_cmd.extend(
        [
            "-p",
            "3000:3000",
            "--add-host",
            "host.docker.internal:host-gateway",
            "--name",
            "openhands-app",
            app_image,
        ]
    )

    try:
        # Log and run the Docker command
        print_formatted_text(HTML(_format_docker_command_for_logging(docker_cmd)))
        subprocess.run(docker_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print_formatted_text("")
        print_formatted_text(
            HTML("<ansired>❌ Failed to start OpenHands GUI server.</ansired>")
        )
        print_formatted_text(HTML(f"<grey>Error: {e}</grey>"))
        sys.exit(1)
    except KeyboardInterrupt:
        print_formatted_text("")
        print_formatted_text(
            HTML("<ansigreen>✓ OpenHands GUI server stopped successfully.</ansigreen>")
        )
        sys.exit(0)
