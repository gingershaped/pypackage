from packaging.utils import parse_sdist_filename
from rich.tree import Tree
from rich.prompt import Confirm

import platformdirs
import zipfile
import os
import os.path

from pypackage.commands import Command
from pypackage.ppk import PPK
from pypackage.util.venv import Venv
from pypackage.locators.python_locator import PythonLocator
from pypackage.util import formatPackageName, renderDepTree


class InstallCommand(Command):
    def __init__(self, subparsers, console, parentLogger):
        super().__init__(subparsers, console, parentLogger, "install", "Install a .ppk file")
        self.parser.add_argument("path")

        self.venv: Venv = Venv()
        self.locator: PythonLocator = PythonLocator()
    
    def run(self, args):
        with zipfile.ZipFile(args.path) as ppkfile:
            self.ppk = PPK.fromZipfile(ppkfile)
        self.installPath = os.path.join(platformdirs.user_data_path("pypackage") if os.geteuid() != 0 else platformdirs.site_data_path("pypackage"), "packages", f"{self.ppk.name}")

        self.console.rule("[cyan bold]Dependencies[/cyan bold]")
        self.console.print(renderDepTree(Tree(formatPackageName(self.ppk.name, self.ppk.version)), self.ppk.dependencyTree))
        self.console.rule()
        self.console.print(f"Going to install {formatPackageName(self.ppk.name, self.ppk.version)} to [underline]{self.installPath}.")
        if not Confirm.ask("Install software?"):
            self.console.print("[bold red]Aborted.")
            exit(1)
        self.console.print()
        self.venv.create(self.locator.locatePythonExecutables(self.ppk.python))
        