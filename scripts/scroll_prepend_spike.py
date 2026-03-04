"""SPEC-002 spike: validate Textual VerticalScroll prepend + scroll restoration behavior.

Usage:
    uv run python scripts/scroll_prepend_spike.py
"""

import asyncio
import json
import time

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class SpikeApp(App):
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="scroll"):
            for i in range(600):
                yield Static(f"row-{i}")


async def run_spike() -> dict[str, float | bool | str]:
    out: dict[str, float | bool | str] = {}

    app = SpikeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        container = app.query_one("#scroll", VerticalScroll)

        # Q1: scroll_y semantics
        out["q1_scroll_y_type"] = type(container.scroll_y).__name__
        out["q1_scroll_y_initial"] = float(container.scroll_y)

        # Q2: prepend behavior (does it auto-adjust?)
        container.scroll_to(y=220, animate=False)
        await pilot.pause()
        y_before_prepend = float(container.scroll_y)
        first = container.children[0] if container.children else None
        container.mount(Static("prep-single"), before=first)
        await pilot.pause()
        y_after_prepend = float(container.scroll_y)
        out["q2_scroll_y_before_prepend"] = y_before_prepend
        out["q2_scroll_y_after_prepend"] = y_after_prepend
        out["q2_auto_adjusted"] = y_after_prepend != y_before_prepend

        # Q3: restoration via scroll_to
        target = y_before_prepend + 120
        container.scroll_to(y=target, animate=False)
        await pilot.pause()
        y_after_restore = float(container.scroll_y)
        out["q3_scroll_to_target"] = float(target)
        out["q3_scroll_y_after_scroll_to"] = y_after_restore
        out["q3_restore_success"] = abs(y_after_restore - target) < 1e-6

        # Q4: latency for prepend + restore cycle (200 widgets)
        container.scroll_to(y=220, animate=False)
        await pilot.pause()
        baseline = float(container.scroll_y)
        t0 = time.perf_counter()
        for i in range(200):
            first = container.children[0] if container.children else None
            container.mount(Static(f"prep-{i}"), before=first)
        await pilot.pause()
        container.scroll_to(y=baseline + 200, animate=False)
        await pilot.pause()
        t1 = time.perf_counter()
        out["q4_latency_ms_prepend_and_restore_200"] = round((t1 - t0) * 1000, 3)
        out["q4_scroll_y_after_restore_200"] = float(container.scroll_y)

        # Q5: batching support
        out["q5_container_has_batch_update"] = hasattr(container, "batch_update")
        out["q5_app_has_batch_update"] = hasattr(app, "batch_update")

    return out


def main() -> None:
    result = asyncio.run(run_spike())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
