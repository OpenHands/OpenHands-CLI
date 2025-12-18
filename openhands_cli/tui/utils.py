# Minimal replacement for removed TUI components


class StepCounter:
    """Minimal step counter placeholder."""

    def __init__(self, total_steps=1):
        self.total_steps = total_steps
        self.current_step = 0

    def next_step(self):
        self.current_step += 1

    def get_progress(self):
        return f"{self.current_step}/{self.total_steps}"
