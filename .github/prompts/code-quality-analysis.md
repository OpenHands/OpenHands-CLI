# Code Quality Analysis Task

Please analyze this Python codebase for code quality issues and generate a comprehensive report.

## Instructions

### 1. Type Checking Analysis
First, read the pyright output from `pyright_output.json` in the current directory.
Analyze the codebase in `openhands_cli/` directory for:
- Missing type hints on function parameters and return types
- Missing type hints on class attributes
- Any `Any` types that could be more specific
- Potential type safety issues that could lead to runtime bugs
- Areas where better typing could improve code quality

### 2. State Management Analysis
Analyze the codebase for state management patterns and issues:
- Identify global state that could be encapsulated in classes or dataclasses
- Look for mutable default arguments that could cause bugs
- Find places where state is scattered across modules instead of centralized
- Identify state that is passed through too many function calls (prop drilling)
- Look for opportunities to use proper state containers (dataclasses, TypedDict, etc.)
- Check `openhands_cli/stores/` for proper state management patterns

### 3. Separation of Concerns Analysis
Analyze the codebase for proper separation of concerns:
- Identify modules that mix business logic with UI/presentation code
- Look for functions/classes that do too many things (violate single responsibility)
- Find places where data access is mixed with business logic
- Identify tightly coupled components that should be loosely coupled
- Check if the `openhands_cli/acp_impl/`, `openhands_cli/tui/`, and `openhands_cli/auth/` directories have clear boundaries

### 4. Code Duplication Analysis (ACP vs TUI)
Compare the ACP implementation (`openhands_cli/acp_impl/`) and TUI implementation (`openhands_cli/tui/`) for code duplication:
- Identify similar or identical code patterns in both implementations
- Look for duplicated utility functions, data processing, or event handling logic
- Find opportunities to extract shared code into `openhands_cli/shared/` module
- Check for duplicated constants, configurations, or data structures
- Identify common patterns that could be abstracted into base classes or mixins
- Pay special attention to:
  - Event handling and processing logic
  - Agent interaction patterns
  - Error handling approaches
  - State synchronization code
  - User input processing

### 5. Generate Report
Generate a markdown report with the following sections:
- **Executive Summary**: Brief overview of all findings
- **Type Checking Issues**:
  - Critical Issues: Type errors that could cause runtime bugs
  - Missing Type Hints: Functions/methods lacking proper type annotations
  - Type Improvement Opportunities: Areas where typing could be enhanced
- **State Management Issues**:
  - Current State: How state is currently managed
  - Problems Identified: Issues with current state management
  - Recommendations: How to improve state management
- **Separation of Concerns Issues**:
  - Coupled Components: Areas where code is too tightly coupled
  - Mixed Responsibilities: Code that violates single responsibility principle
  - Recommendations: How to improve separation
- **Code Duplication (ACP/TUI)**:
  - Duplicated Patterns: Specific code that appears in both implementations
  - Shared Code Opportunities: What could be moved to shared modules
  - Recommendations: Specific refactoring suggestions
- **Low-Hanging Fruit**: Easy fixes that can be addressed quickly (mark each with estimated effort: trivial/small/medium)
- **Statistics**: Count of issues by category
- **Prioritized Action Items**: Ordered list of recommended fixes

### 6. Save Report
Save the report to `code_quality_report.md` in the current directory.

Focus on actionable items that would improve code quality, prevent runtime bugs, and reduce maintenance burden.
