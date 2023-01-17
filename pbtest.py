import concurrent.futures
import time

from rich.console import Console

from pypackage.progress_manager import RichProgressManager

def downloadThread(manager: RichProgressManager, label):
    task = manager.addTask(label, 100)
    for x in range(100):
        manager.updateTask(task, 1)
    manager.finishTask(task)

pool = concurrent.futures.ThreadPoolExecutor(max_workers = 4)

console = Console()
with RichProgressManager(console) as manager:
    for x in range(10):
        pool.submit(downloadThread, "bingus", manager)

