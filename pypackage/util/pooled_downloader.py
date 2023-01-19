import concurrent.futures

from itertools import repeat

from rich.progress import Progress

import requests

from pypackage.util.progress_manager import ProgressManager

class PooledDownloader:
    def __init__(self, progressManager: ProgressManager, workers: int = 4, chunksize: int = 512):
        self.progressManager = progressManager
        self.chunksize = chunksize
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers = workers)

    def _downloadUrlToPath(self, label: str, url: str, path: str) -> str: 
        request = requests.get(url, stream = True)
        if "Content-Length" in request.headers:
            total = int(request.headers["Content-Length"])
        else:
            total = 0
        task = self.progressManager.addTask(label, total) if total > 2**20 else None
        with open(path, "wb") as file:
            for chunk in request.iter_content(self.chunksize):
                file.write(chunk)
                if task:
                    self.progressManager.updateTask(task, self.chunksize)
        if task:
            self.progressManager.finishTask(task)
        return path

    def downloadUrlToPath(self, url: str, path: str, label: str) -> concurrent.futures.Future:
        return self.pool.submit(self._downloadUrlToPath, label, url, path)

    def __enter__(self):
        self.progressManager.start()
        return self
    def __exit__(self, excType, excVal, excTb):
        self.progressManager.finish()
        self.pool.shutdown(wait = True, cancel_futures = True)