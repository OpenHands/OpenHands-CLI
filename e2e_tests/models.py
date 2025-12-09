"""Pydantic models for E2E test results."""

from typing import Any

from pydantic import BaseModel


class TestResult(BaseModel):
    """Result of an E2E test execution."""

    test_name: str
    success: bool
    cost: float = 0.0  # Currently all tests should have 0 cost
    boot_time_seconds: float | None = None
    total_time_seconds: float
    error_message: str | None = None
    output_preview: str | None = None
    metadata: dict[str, Any] = {}

    def __str__(self) -> str:
        """String representation of test result."""
        status = "✅ PASSED" if self.success else "❌ FAILED"
        time_info = f"({self.total_time_seconds:.2f}s"
        if self.boot_time_seconds is not None:
            time_info += f", boot: {self.boot_time_seconds:.2f}s"
        time_info += ")"

        result = f"{self.test_name}: {status} {time_info}"
        if not self.success and self.error_message:
            result += f" - {self.error_message}"
        return result


class TestSummary(BaseModel):
    """Summary of all E2E test results."""

    total_tests: int
    passed_tests: int
    failed_tests: int
    total_time_seconds: float
    total_cost: float = 0.0
    results: list[TestResult]

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def all_passed(self) -> bool:
        """Check if all tests passed."""
        return self.failed_tests == 0

    def __str__(self) -> str:
        """String representation of test summary."""
        status = "✅ ALL PASSED" if self.all_passed else "❌ SOME FAILED"
        return (
            f"\n{'=' * 60}\n"
            f"E2E Test Summary: {status}\n"
            f"{'=' * 60}\n"
            f"Total tests: {self.total_tests}\n"
            f"Passed: {self.passed_tests}\n"
            f"Failed: {self.failed_tests}\n"
            f"Success rate: {self.success_rate:.1f}%\n"
            f"Total time: {self.total_time_seconds:.2f}s\n"
            f"Total cost: ${self.total_cost:.2f}\n"
            f"{'=' * 60}"
        )
