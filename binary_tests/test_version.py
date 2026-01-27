"""E2E test for version flag functionality."""

import os
import re
import subprocess
import time
from pathlib import Path

from .models import TestResult


def test_version() -> TestResult:
    """Test the --version flag of the built executable."""
    test_name = "version_flag"
    start_time = time.time()

    try:
        # Find the binary executable
        exe_path = Path("dist/openhands")
        if not exe_path.exists():
            exe_path = Path("dist/openhands.exe")
            if not exe_path.exists():
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    error_message="Binary executable not found!",
                )

        # Make binary executable on Unix-like systems
        if os.name != "nt":
            os.chmod(exe_path, 0o755)

        # Run --version and capture output
        result = subprocess.run(
            [str(exe_path), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        total_time = time.time() - start_time

        if result.returncode != 0:
            return TestResult(
                test_name=test_name,
                success=False,
                total_time_seconds=total_time,
                error_message=(
                    f"Failed to run binary --version command! "
                    f"Exit code: {result.returncode}"
                ),
                output_preview=f"Output: {result.stdout}\nError: {result.stderr}",
            )

        version_output = result.stdout + result.stderr

        # Check if output contains "OpenHands CLI"
        if "OpenHands CLI" not in version_output:
            return TestResult(
                test_name=test_name,
                success=False,
                total_time_seconds=total_time,
                error_message="Version output does not contain 'OpenHands CLI'!",
                output_preview=version_output,
            )

        # Check if output contains a valid version number (X.Y.Z format)
        if not re.search(r"\d+\.\d+\.\d+", version_output):
            return TestResult(
                test_name=test_name,
                success=False,
                total_time_seconds=total_time,
                error_message="Version output does not contain a valid version number!",
                output_preview=version_output,
            )

        return TestResult(
            test_name=test_name,
            success=True,
            total_time_seconds=total_time,
            metadata={"version_output": version_output.strip()},
        )

    except subprocess.TimeoutExpired:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message="Binary --version test timed out",
        )
    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error testing binary --version: {e}",
        )
