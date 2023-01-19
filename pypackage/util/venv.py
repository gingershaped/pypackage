from typing import Optional

import venv
import os
import sys


class Venv:
    def __init__(self, builder: Optional[venv.EnvBuilder] = None):
        self.builder = builder
        if not self.builder:
            self.builder = venv.EnvBuilder(clear = True, with_pip = True)
    def create(self, pythonPath: str, path: str):
        path = os.path.abspath(path)
        self.context = self.builder.ensure_directories(path)
        self.context.executable = pythonPath
        self.builder.create_configuration(self.context)
        self.builder.setup_python(self.context)