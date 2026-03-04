"""Verify that entrypoint suppresses import-time warnings.

opentelemetry emits DeprecationWarnings at module-level import time.
entrypoint.py must call ``warnings.filterwarnings("ignore")`` *before*
the openhands_cli imports that transitively pull in opentelemetry, so
those warnings are already filtered by the time the problematic code runs.

The primary test uses Python's ``ast`` module to verify the structural
ordering in the source: the filterwarnings call must appear before the
first openhands_cli import statement.

A secondary functional test confirms the suppression works for a genuine
import-time DeprecationWarning by registering a fake module that emits
one at import time.
"""

import ast
import sys
import types
import warnings
from pathlib import Path


class TestEntrypointWarningsFilterOrdering:
    """filterwarnings("ignore") must precede openhands_cli imports in entrypoint."""

    def _entrypoint_source(self) -> str:
        import openhands_cli.entrypoint as m

        return Path(m.__file__).read_text()

    def test_filterwarnings_appears_before_openhands_cli_imports(self):
        """Parse entrypoint.py and verify filterwarnings call precedes imports.

        This is a structural guard: if the order is ever accidentally reversed
        the test will catch it before a user sees spurious DeprecationWarnings.
        """
        source = self._entrypoint_source()
        tree = ast.parse(source)

        filter_lineno = None
        first_openhands_import_lineno = None

        for node in ast.walk(tree):
            # Detect: warnings.filterwarnings(...)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "filterwarnings"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "warnings"
            ):
                if filter_lineno is None or node.lineno < filter_lineno:
                    filter_lineno = node.lineno

            # Detect: from openhands_cli.* import ...
            is_openhands_import = (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("openhands_cli")
            )
            if is_openhands_import:
                if (
                    first_openhands_import_lineno is None
                    or node.lineno < first_openhands_import_lineno
                ):
                    first_openhands_import_lineno = node.lineno

        assert filter_lineno is not None, (
            "No warnings.filterwarnings() call found in entrypoint.py"
        )
        assert first_openhands_import_lineno is not None, (
            "No 'from openhands_cli.*' import found in entrypoint.py"
        )
        assert filter_lineno < first_openhands_import_lineno, (
            f"warnings.filterwarnings() is on line {filter_lineno} but the first "
            f"openhands_cli import is on line {first_openhands_import_lineno}. "
            f"The filter must come BEFORE the imports so it suppresses import-time "
            f"DeprecationWarnings from opentelemetry and other transitive dependencies."
        )


class TestFilterwarningsSuppressesImportTimeWarnings:
    """Functional check: filterwarnings("ignore") called before an import suppresses
    DeprecationWarnings emitted at that module's load time."""

    def test_ignore_filter_before_import_suppresses_import_time_deprecation(self):
        """A DeprecationWarning emitted at module import time must be silenced when
        warnings.filterwarnings("ignore") is already active."""
        # Register a fake module that emits a DeprecationWarning at import time
        module_name = "_test_fake_deprecation_module_xyz"

        fake_code = compile(
            "import warnings; warnings.warn('fake', DeprecationWarning, stacklevel=1)",
            "<fake>",
            "exec",
        )
        fake_mod = types.ModuleType(module_name)
        sys.modules[module_name] = fake_mod

        captured: list[warnings.WarningMessage] = []
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.filterwarnings("ignore")
                # Simulate importing the module (executing its top-level code)
                exec(fake_code, fake_mod.__dict__)  # noqa: S102
                captured.extend(w)
        finally:
            sys.modules.pop(module_name, None)

        deprecation_warnings = [
            x for x in captured if issubclass(x.category, DeprecationWarning)
        ]
        assert deprecation_warnings == [], (
            f"DeprecationWarning was emitted despite filterwarnings('ignore') "
            f"being active: {deprecation_warnings}"
        )
