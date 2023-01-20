from typing import Iterable

from packaging.specifiers import SpecifierSet
from packaging.version import Version, InvalidVersion

import subprocess
import os
import itertools
import logging

GET_PYTHON_VERSION_ONELINER = "import sys; print('.'.join([str(s) for s in sys.version_info[:3]]))"
GET_PYTHON_PREFIXES_ONELINER = "import sys; print(sys.base_prefix, ':', sys.prefix)"

AVAILABLE_PYTHONS = {
    Version("3.9"),
    Version("3.10"),
    Version("3.11")
}

class PythonLocator:
    def __init__(self):
        self.logger = logging.getLogger("PythonLocator")
    def pythonPaths(self, availablePythons: Iterable[Version] = AVAILABLE_PYTHONS) -> Iterable[str]:
        executables = {"python" + str(version) for version in availablePythons}
        return itertools.chain(*map(set, ((os.path.join(dirpath, executable) for executable in executables if executable in filenames) for dirpath, _, filenames in itertools.chain(*map(os.walk, os.get_exec_path())))))
    def locatePythonExecutables(self, specifiers: SpecifierSet, availablePythons: Iterable[str] = AVAILABLE_PYTHONS):
        for pythonPath in self.pythonPaths(availablePythons):
            # Only supported versions, please!
            try:
                versionRaw = subprocess.run([pythonPath, "-c", GET_PYTHON_VERSION_ONELINER], capture_output = True, text = True, check = True).stdout
                version = Version(versionRaw)
            except subprocess.CalledProcessError:
                self.logger.warning(f"Failed to run command {[pythonPath, '-c', GET_PYTHON_VERSION_ONELINER]}")
                continue
            except InvalidVersion:
                self.logger.warning(f"{pythonPath} has invalid version {versionRaw}!")
                continue
            if version not in specifiers:
                self.logger.debug(f"Skipping {pythonPath} (inelegible version {version})")
                continue
            # Make sure it's not a virtualenv doing some fuckery
            try:
                basePrefix, prefix = subprocess.run([pythonPath, "-c", GET_PYTHON_PREFIXES_ONELINER], capture_output = True, text = True, check = True).stdout.split(":")
                basePrefix, prefix = basePrefix.strip(), prefix.strip()
            except subprocess.CalledProcessError:
                self.logger.warning(f"Failed to run command {[pythonPath, '-c', GET_PYTHON_PREFIXES_ONELINER]}")
                continue
            if basePrefix != prefix:
                self.logger.debug(f"Skipping {pythonPath} (probably a virtualenv) {basePrefix} != {prefix}")
                continue
            yield pythonPath