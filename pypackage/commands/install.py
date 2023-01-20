from rich.tree import Tree
from rich.table import Table
from rich.prompt import Confirm, IntPrompt

import platformdirs
import zipfile
import os
import os.path

from pypackage.commands import Command
from pypackage.ppk import PPK
from pypackage.venv import Venv
from pypackage.venv.builder import PypackageBuilder
from pypackage.locators.python_locator import PythonLocator
from pypackage.util import formatPackageName, renderDepTree


class InstallCommand(Command):
    def __init__(self, subparsers, console, parentLogger):
        super().__init__(subparsers, console, parentLogger, "install", "Install a .ppk file")
        self.parser.add_argument("path")

        self.venv: Venv = Venv(PypackageBuilder(clear = True, with_pip = True))
        self.locator: PythonLocator = PythonLocator()

    def promptForPython(self, pythons):
        self.console.print("[bold]Multiple Python interpreters are available[/bold] to create the virtual environment with.\nWhich would you like to use?")
        pythonTable = Table(show_header = False)
        for c, python in enumerate(pythons, 1):
            pythonTable.add_row(f"[bold]{c}", f"[cyan]{python}")
        self.console.print(pythonTable)
        while True:
            result = IntPrompt.ask("[bold purple]Select an interpreter")
            if result >= 1 and result <= len(pythons):
                break
            self.console.print("[bold red]Invalid choice.")
        return pythons[result-1]
        
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
        
        pythons = list(self.locator.locatePythonExecutables(self.ppk.python))
        assert len(pythons) > 0, "You don't have any elegible Python interpreters to make a virtualenv with. How is that even possible?!"
        if len(pythons) > 1:
            python = self.promptForPython(pythons)
        else:
            python = pythons[0]
        with self.console.status("Creating virtualenv...", spinner = "dots12"):
            self.venv.create(python, self.installPath)
        