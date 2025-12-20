"""E2E test runner for OpenHands CLI."""

import time
from collections.abc import Callable

from .models import TestResult, TestSummary
from .test_acp import test_acp_executable
from .test_experimental_ui import test_experimental_ui
from .test_version import test_version


def run_all_e2e_tests() -> TestSummary:
    """Run all E2E tests and return a summary."""
    print("🧪 Running E2E tests...")
    print("=" * 60)

    # Define all tests
    tests: list[Callable[[], TestResult]] = [
        test_version,
        test_experimental_ui,
        test_acp_executable,
    ]

    results: list[TestResult] = []
    start_time = time.time()

    for i, test_func in enumerate(tests, 1):
        print(f"\n[{i}/{len(tests)}] Running {test_func.__name__}...")

        try:
            result = test_func()
            results.append(result)
            print(f"  {result}")

        except Exception as e:
            # Create a failed result for any unexpected exceptions
            result = TestResult(
                test_name=test_func.__name__,
                success=False,
                total_time_seconds=0.0,
                error_message=f"Unexpected error: {e}",
            )
            results.append(result)
            print(f"  {result}")

    total_time = time.time() - start_time

    # Calculate summary statistics
    passed_tests = sum(1 for r in results if r.success)
    failed_tests = len(results) - passed_tests
    total_cost = sum(r.cost for r in results)

    summary = TestSummary(
        total_tests=len(results),
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        total_time_seconds=total_time,
        total_cost=total_cost,
        results=results,
    )

    return summary


def print_detailed_results(summary: TestSummary) -> None:
    """Print detailed test results."""
    print(f"\n{summary}")

    if summary.failed_tests > 0:
        print(f"\n❌ Failed Tests ({summary.failed_tests}):")
        print("-" * 40)
        for result in summary.results:
            if not result.success:
                print(f"  • {result.test_name}: {result.error_message}")
                if result.output_preview:
                    print(f"    Preview: {result.output_preview[:200]}...")

    if summary.passed_tests > 0:
        print(f"\n✅ Passed Tests ({summary.passed_tests}):")
        print("-" * 40)
        for result in summary.results:
            if result.success:
                boot_info = ""
                if result.boot_time_seconds is not None:
                    boot_info = f" (boot: {result.boot_time_seconds:.2f}s)"
                time_str = f"{result.total_time_seconds:.2f}s{boot_info}"
                print(f"  • {result.test_name}: {time_str}")
