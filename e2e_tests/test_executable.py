"""E2E test for main executable functionality."""

import os
import select
import subprocess
import time
from pathlib import Path

from .models import TestResult
from .utils import seed_dummy_settings


WELCOME_MARKERS = ["welcome", "openhands cli", "type /help", "available commands", ">"]


def _is_welcome(line: str) -> bool:
    """Check if a line contains welcome markers."""
    s = line.strip().lower()
    return any(marker in s for marker in WELCOME_MARKERS)


def test_executable() -> TestResult:
    """Test the built executable, measuring boot time and total test time."""
    test_name = "main_executable"
    start_time = time.time()

    try:
        # Create dummy agent settings
        seed_dummy_settings()

        exe_path = Path("dist/openhands")
        if not exe_path.exists():
            exe_path = Path("dist/openhands.exe")
            if not exe_path.exists():
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    error_message="Executable not found!",
                )

        proc = None
        try:
            if os.name != "nt":
                os.chmod(exe_path, 0o755)

            boot_start = time.time()
            proc = subprocess.Popen(
                [str(exe_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ},
            )

            # Wait for welcome
            deadline = boot_start + 60
            saw_welcome = False
            captured = []

            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                if proc.stdout is None:
                    break
                rlist, _, _ = select.select([proc.stdout], [], [], 0.2)
                if not rlist:
                    continue
                line = proc.stdout.readline()
                if not line:
                    continue
                captured.append(line)
                if _is_welcome(line):
                    saw_welcome = True
                    break

            if not saw_welcome:
                try:
                    proc.kill()
                except Exception:
                    pass
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    error_message="Did not detect welcome prompt",
                    output_preview=(
                        "".join(captured[-10:]) if captured else "No output captured"
                    ),
                )

            boot_end = time.time()
            boot_time = boot_end - boot_start

            # Run /help then /exit
            if proc.stdin is None:
                proc.kill()
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    boot_time_seconds=boot_time,
                    error_message="stdin unavailable",
                )

            proc.stdin.write("/help\n/exit\n")
            proc.stdin.flush()
            out, _ = proc.communicate(timeout=60)

            total_end = time.time()
            full_output = "".join(captured) + (out or "")
            total_time = total_end - start_time

            if "available commands" in full_output.lower():
                return TestResult(
                    test_name=test_name,
                    success=True,
                    total_time_seconds=total_time,
                    boot_time_seconds=boot_time,
                    metadata={
                        "welcome_detected": True,
                        "help_command_worked": True,
                    },
                )
            else:
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=total_time,
                    boot_time_seconds=boot_time,
                    error_message="/help output not found",
                    output_preview=full_output[-500:] if full_output else "No output",
                )

        except subprocess.TimeoutExpired:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return TestResult(
                test_name=test_name,
                success=False,
                total_time_seconds=time.time() - start_time,
                error_message="Executable test timed out",
            )
        except Exception as e:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return TestResult(
                test_name=test_name,
                success=False,
                total_time_seconds=time.time() - start_time,
                error_message=f"Error testing executable: {e}",
            )

    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error setting up test: {e}",
        )
