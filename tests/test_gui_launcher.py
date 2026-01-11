"""Tests for GUI launcher functionality."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openhands_cli.gui_launcher import (
    _format_docker_command_for_logging,
    _is_wsl2,
    _wsl_to_windows_path,
    check_docker_requirements,
    get_openhands_version,
    launch_gui_server,
)


class TestWSL2Detection:
    """Test WSL2 detection and path conversion functions."""

    @pytest.mark.parametrize(
        "platform_release,expected",
        [
            ("5.15.153.1-microsoft-standard-WSL2", True),
            ("5.10.16.3-microsoft-standard-WSL2", True),
            ("5.4.72-microsoft-standard-WSL2", True),
            ("4.4.0-19041-Microsoft", True),  # WSL1 but still has microsoft
            ("5.15.0-generic", False),  # Regular Linux
            ("6.8.0-1026-gke", False),  # GKE
            ("Darwin Kernel Version 21.6.0", False),  # macOS
        ],
    )
    def test_is_wsl2(self, platform_release, expected):
        """Test WSL2 detection based on platform release string."""
        with patch("platform.release", return_value=platform_release):
            result = _is_wsl2()
            assert result is expected

    def test_is_wsl2_exception_handling(self):
        """Test that _is_wsl2 returns False on exception."""
        with patch("platform.release", side_effect=Exception("Test error")):
            result = _is_wsl2()
            assert result is False


class TestWSLToWindowsPath:
    """Test WSL2 to Windows path conversion."""

    @pytest.mark.parametrize(
        "wsl_path,expected",
        [
            # Standard WSL2 mount paths
            ("/mnt/c/Users/test", "C:/Users/test"),
            ("/mnt/d/ai-data/workspace", "D:/ai-data/workspace"),
            ("/mnt/e/projects/myproject", "E:/projects/myproject"),
            # Drive root
            ("/mnt/c", "C:/"),
            ("/mnt/d", "D:/"),
            # Paths that should NOT be converted
            ("/home/user/project", "/home/user/project"),  # Native Linux path
            ("/workspace", "/workspace"),  # Container path
            ("/mnt/wsl/docker-desktop", "/mnt/wsl/docker-desktop"),  # WSL internal
            ("/mnt/", "/mnt/"),  # Just /mnt/
            ("/mnt/ab/test", "/mnt/ab/test"),  # Two-letter "drive"
            ("", ""),  # Empty string
            ("/", "/"),  # Root
            # Edge cases
            ("/mnt/c/", "C:/"),  # Trailing slash
            ("/mnt/C/Users/Test", "C:/Users/Test"),  # Uppercase drive letter
        ],
    )
    def test_wsl_to_windows_path(self, wsl_path, expected):
        """Test WSL2 to Windows path conversion."""
        result = _wsl_to_windows_path(wsl_path)
        assert result == expected


class TestFormatDockerCommand:
    """Test the Docker command formatting function."""

    @pytest.mark.parametrize(
        "cmd,expected",
        [
            (
                ["docker", "run", "hello-world"],
                "<grey>Running Docker command: docker run hello-world</grey>",
            ),
            (
                ["docker", "run", "-it", "--rm", "-p", "3000:3000", "openhands:latest"],
                "<grey>Running Docker command: docker run -it --rm -p 3000:3000 "
                "openhands:latest</grey>",
            ),
            ([], "<grey>Running Docker command: </grey>"),
        ],
    )
    def test_format_docker_command(self, cmd, expected):
        """Test formatting Docker commands."""
        result = _format_docker_command_for_logging(cmd)
        assert result == expected


class TestCheckDockerRequirements:
    """Test Docker requirements checking."""

    @pytest.mark.parametrize(
        "which_return,run_side_effect,expected_result,expected_print_count",
        [
            # Docker not installed
            (None, None, False, 2),
            # Docker daemon not running
            ("/usr/bin/docker", MagicMock(returncode=1), False, 2),
            # Docker timeout
            ("/usr/bin/docker", subprocess.TimeoutExpired("docker info", 10), False, 2),
            # Docker available
            ("/usr/bin/docker", MagicMock(returncode=0), True, 0),
        ],
    )
    @patch("shutil.which")
    @patch("subprocess.run")
    def test_docker_requirements(
        self,
        mock_run,
        mock_which,
        which_return,
        run_side_effect,
        expected_result,
        expected_print_count,
    ):
        """Test Docker requirements checking scenarios."""
        mock_which.return_value = which_return
        if run_side_effect is not None:
            if isinstance(run_side_effect, Exception):
                mock_run.side_effect = run_side_effect
            else:
                mock_run.return_value = run_side_effect

        with patch("openhands_cli.gui_launcher.print_formatted_text") as mock_print:
            result = check_docker_requirements()

        assert result is expected_result
        assert mock_print.call_count == expected_print_count


class TestGetOpenHandsVersion:
    """Test version retrieval."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            (None, "latest"),  # No environment variable set
            ("1.2.3", "1.2.3"),  # Environment variable set
        ],
    )
    def test_version_retrieval(self, env_value, expected):
        """Test version retrieval from environment."""
        if env_value:
            os.environ["OPENHANDS_VERSION"] = env_value
        result = get_openhands_version()
        assert result == expected


class TestLaunchGuiServer:
    """Test GUI server launching."""

    @patch("openhands_cli.gui_launcher.check_docker_requirements")
    @patch("openhands_cli.gui_launcher.print_formatted_text")
    def test_launch_gui_server_docker_not_available(
        self, mock_print, mock_check_docker
    ):
        """Test that launch_gui_server exits when Docker is not available."""
        mock_check_docker.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            launch_gui_server()

        assert exc_info.value.code == 1

    @pytest.mark.parametrize(
        "pull_side_effect,run_side_effect,expected_exit_code,mount_cwd,gpu",
        [
            # Docker pull failure
            (subprocess.CalledProcessError(1, "docker pull"), None, 1, False, False),
            # Docker run failure
            (
                MagicMock(returncode=0),
                subprocess.CalledProcessError(1, "docker run"),
                1,
                False,
                False,
            ),
            # KeyboardInterrupt during run
            (MagicMock(returncode=0), KeyboardInterrupt(), 0, False, False),
            # Success with mount_cwd
            (MagicMock(returncode=0), MagicMock(returncode=0), None, True, False),
            # Success with GPU
            (MagicMock(returncode=0), MagicMock(returncode=0), None, False, True),
        ],
    )
    @patch("openhands_cli.gui_launcher.check_docker_requirements")
    @patch("openhands_cli.gui_launcher.ensure_config_dir_exists")
    @patch("openhands_cli.gui_launcher.get_openhands_version")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("pathlib.Path.cwd")
    @patch("openhands_cli.gui_launcher.print_formatted_text")
    def test_launch_gui_server_scenarios(
        self,
        mock_print,
        mock_cwd,
        mock_check_output,
        mock_run,
        mock_version,
        mock_config_dir,
        mock_check_docker,
        pull_side_effect,
        run_side_effect,
        expected_exit_code,
        mount_cwd,
        gpu,
    ):
        """Test various GUI server launch scenarios."""
        # Setup mocks
        mock_check_docker.return_value = True
        mock_config_dir.return_value = Path("/home/user/.openhands")
        mock_version.return_value = "latest"
        mock_check_output.return_value = "1000\n"
        mock_cwd.return_value = Path("/current/dir")

        # Configure subprocess.run side effects
        side_effects = []
        if pull_side_effect is not None:
            if isinstance(pull_side_effect, Exception):
                side_effects.append(pull_side_effect)
            else:
                side_effects.append(pull_side_effect)

        if run_side_effect is not None:
            if isinstance(run_side_effect, Exception):
                side_effects.append(run_side_effect)
            else:
                side_effects.append(run_side_effect)

        mock_run.side_effect = side_effects

        # Test the function
        if expected_exit_code is not None:
            with pytest.raises(SystemExit) as exc_info:
                launch_gui_server(mount_cwd=mount_cwd, gpu=gpu)
            assert exc_info.value.code == expected_exit_code
        else:
            # Should not raise SystemExit for successful cases
            launch_gui_server(mount_cwd=mount_cwd, gpu=gpu)

            # Verify subprocess.run was called correctly
            assert mock_run.call_count == 2  # Pull and run commands

            # Check pull command
            pull_call = mock_run.call_args_list[0]
            pull_cmd = pull_call[0][0]
            assert pull_cmd[0:3] == [
                "docker",
                "pull",
                "docker.openhands.dev/openhands/runtime:latest-nikolaik",
            ]

            # Check run command
            run_call = mock_run.call_args_list[1]
            run_cmd = run_call[0][0]
            assert run_cmd[0:2] == ["docker", "run"]

            if mount_cwd:
                assert "SANDBOX_VOLUMES=/current/dir:/workspace:rw" in " ".join(run_cmd)
                assert "SANDBOX_USER_ID=1000" in " ".join(run_cmd)

            if gpu:
                assert "--gpus" in run_cmd
                assert "all" in run_cmd
                assert "SANDBOX_ENABLE_GPU=true" in " ".join(run_cmd)

    @patch("openhands_cli.gui_launcher.check_docker_requirements")
    @patch("openhands_cli.gui_launcher.ensure_config_dir_exists")
    @patch("openhands_cli.gui_launcher.get_openhands_version")
    @patch("openhands_cli.gui_launcher._is_wsl2")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("pathlib.Path.cwd")
    @patch("openhands_cli.gui_launcher.print_formatted_text")
    def test_launch_gui_server_wsl2_path_conversion(
        self,
        mock_print,
        mock_cwd,
        mock_check_output,
        mock_run,
        mock_is_wsl2,
        mock_version,
        mock_config_dir,
        mock_check_docker,
    ):
        """Test that WSL2 paths are converted to Windows paths for Docker Desktop."""
        # Setup mocks
        mock_check_docker.return_value = True
        mock_config_dir.return_value = Path("/home/user/.openhands")
        mock_version.return_value = "latest"
        mock_check_output.return_value = "1000\n"
        mock_cwd.return_value = Path("/mnt/d/ai-data/workspace")
        mock_is_wsl2.return_value = True

        # Configure subprocess.run to succeed
        mock_run.return_value = MagicMock(returncode=0)

        # Run the function
        launch_gui_server(mount_cwd=True, gpu=False)

        # Verify subprocess.run was called correctly
        assert mock_run.call_count == 2  # Pull and run commands

        # Check run command has converted path
        run_call = mock_run.call_args_list[1]
        run_cmd = run_call[0][0]

        # The WSL2 path /mnt/d/ai-data/workspace should be converted to D:/ai-data/workspace
        assert "SANDBOX_VOLUMES=D:/ai-data/workspace:/workspace:rw" in " ".join(run_cmd)

    @patch("openhands_cli.gui_launcher.check_docker_requirements")
    @patch("openhands_cli.gui_launcher.ensure_config_dir_exists")
    @patch("openhands_cli.gui_launcher.get_openhands_version")
    @patch("openhands_cli.gui_launcher._is_wsl2")
    @patch("subprocess.run")
    @patch("subprocess.check_output")
    @patch("pathlib.Path.cwd")
    @patch("openhands_cli.gui_launcher.print_formatted_text")
    def test_launch_gui_server_non_wsl2_no_path_conversion(
        self,
        mock_print,
        mock_cwd,
        mock_check_output,
        mock_run,
        mock_is_wsl2,
        mock_version,
        mock_config_dir,
        mock_check_docker,
    ):
        """Test that paths are NOT converted when not running on WSL2."""
        # Setup mocks
        mock_check_docker.return_value = True
        mock_config_dir.return_value = Path("/home/user/.openhands")
        mock_version.return_value = "latest"
        mock_check_output.return_value = "1000\n"
        mock_cwd.return_value = Path("/mnt/d/ai-data/workspace")
        mock_is_wsl2.return_value = False  # Not WSL2

        # Configure subprocess.run to succeed
        mock_run.return_value = MagicMock(returncode=0)

        # Run the function
        launch_gui_server(mount_cwd=True, gpu=False)

        # Verify subprocess.run was called correctly
        assert mock_run.call_count == 2  # Pull and run commands

        # Check run command has original path (not converted)
        run_call = mock_run.call_args_list[1]
        run_cmd = run_call[0][0]

        # The path should NOT be converted when not on WSL2
        assert "SANDBOX_VOLUMES=/mnt/d/ai-data/workspace:/workspace:rw" in " ".join(run_cmd)
