import concurrent.futures

from itertools import repeat

import requests

class PooledDownloader:
    def __init__(self, workers = 4, chunksize = 512):
        self.chunksize = chunksize
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers = workers)

    def _downloadUrlToPath(self, progress, bar, url, path):
        request = requests.get(url, stream = True)
        with open(path, "wb") as file:
            if "Content-Length" in request.headers:
                progress.start_task(bar)
                total = int(request.headers["Content-Length"]) // self.chunksize
                progress.update(bar, total = total)
                if not total < self.chunksize * 4:
                    progress.update(bar, visible = True)
            for chunk in request.iter_content(self.chunksize):
                file.write(chunk)
                if "Content-Length" in request.headers:
                    progress.update(bar, advance = 1)
        progress.update(bar, visible = False)
        return path

    def downloadUrlToPath(self, progress, url, path, label):
        return self.pool.submit(self._downloadUrlToPath, progress, progress.add_task(label, start = False, visible = False), url, path)

    def downloadUrlsToPaths(self, progress, urls, paths, labels, callbacks = repeat(None)):
        for url, path, label, callback in zip(urls, paths, labels, callbacks):
            f = self.pool.submit(self.downloadUrlToPath, progress, progress.add_task(label, visible = False), url, path)
            if callback:
                f.add_done_callback(callback)
            yield f