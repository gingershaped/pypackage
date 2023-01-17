import platformdirs

from tomli_w import dump as dumpToml

import sys
import subprocess
import json
import os.path

class DpyTools:
    def __init__(self):
        pass

    def addMetadataToDpy(self, dpy, projectMeta):
        with dpy.open("metadata.toml", "w") as f:
            dumpToml(projectMeta, f)
    def addDependencyTreeToDpy(self, dpy, tree):
        with dpy.open("dependencies.dat", "w") as f:
            f.write(json.dumps(tree).encode("utf-8"))
    def addFilesToDpy(self, dpy, paths, arcbase = ""):
        for path in paths:
            dpy.write(path, arcname = os.path.join(arcbase, os.path.basename(path)))
            yield path