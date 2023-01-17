from rich.progress import Progress
from rich.console import Console
from rich.live import Live
from rich.table import Table, Column
from rich.align import Align

from typing import Any

class ProgressManager:
    def start(self):
        pass
    def addTask(self, taskLabel: str, total: int) -> int:
        raise NotImplementedError()
    def updateTask(self, task: int, amount: int):
        raise NotImplementedError()
    def finishTask(self, task: int):
        pass
    def finish(self):
        pass
    def __enter__(self) -> "ProgressManager":
        self.start()
        return self
    def __exit__(self, excType, excVal, excTb):
        self.finish()

class RichProgressManager(ProgressManager):
    def __init__(self, console: Console, *progressColumns, **progressOptions):
        self._tasks = []
        self.console = console
        self.progress = Progress(*progressColumns, console = self.console, **progressOptions)

    def addTask(self, taskLabel, total):
        ident = self.progress.add_task(taskLabel, total = total)
        return ident
    def updateTask(self, task, amount):
        self.progress.advance(task, amount)
    def finishTask(self, task):
        self.progress.remove_task(task)

    def start(self):
        self.progress.start()
    def finish(self):
        self.progress.stop()
        