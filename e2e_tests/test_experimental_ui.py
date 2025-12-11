"""E2E test for experimental textual UI functionality."""

import os
import select
import subprocess
import time
from pathlib import Path

from .models import TestResult
from .utils import seed_dummy_settings


def test_experimental_ui() -> TestResult:
    """Test the experimental textual UI with --exp flag."""
    test_name = "experimental_ui"
    start_time = time.time()

    try:
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
                [str(exe_path), "--exp", "--exit-without-confirmation"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ},
            )

            # Wait for experimental UI to start - look for textual UI markers
            deadline = boot_start + 60
            saw_ui_start = False
            captured = []

            # Markers that indicate the textual UI has started
            ui_markers = [
                "initialized conversation",
                "what do you want to build",
            ]

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
                if any(marker.lower() in line.lower() for marker in ui_markers):
                    print("fouind marker in line", line)
                    saw_ui_start = True
                    break

            if not saw_ui_start:
                try:
                    proc.kill()
                except Exception:
                    pass
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    error_message="Did not detect experimental UI startup",
                    output_preview=(
                        "".join(captured[-10:]) if captured else "No output captured"
                    ),
                )

            boot_end = time.time()
            boot_time = boot_end - boot_start

            # Send Ctrl+Q to gracefully exit the experimental UI
            if proc.stdin is None:
                proc.kill()
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=time.time() - start_time,
                    boot_time_seconds=boot_time,
                    error_message="stdin unavailable",
                )

            # Send Ctrl+Q (ASCII 17) to exit the textual UI
            proc.stdin.write("\x11")  # Ctrl+Q
            proc.stdin.flush()
            out, _ = proc.communicate(timeout=30)

            total_end = time.time()
            full_output = "".join(captured) + (out or "")
            total_time = total_end - start_time

            # Check if the experimental UI started properly
            if any(marker in full_output.lower() for marker in ui_markers):
                return TestResult(
                    test_name=test_name,
                    success=True,
                    total_time_seconds=total_time,
                    boot_time_seconds=boot_time,
                    metadata={
                        "ui_started": True,
                        "ui_markers_found": [
                            marker
                            for marker in ui_markers
                            if marker in full_output.lower()
                        ],
                    },
                )
            else:
                return TestResult(
                    test_name=test_name,
                    success=False,
                    total_time_seconds=total_time,
                    boot_time_seconds=boot_time,
                    error_message="Experimental UI startup markers not found",
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
                error_message="Experimental UI test timed out",
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
                error_message=f"Error testing experimental UI: {e}",
            )

    except Exception as e:
        return TestResult(
            test_name=test_name,
            success=False,
            total_time_seconds=time.time() - start_time,
            error_message=f"Error setting up experimental UI test: {e}",
        )
