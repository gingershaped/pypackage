from packaging.utils import parse_sdist_filename
from tomli import load as loadToml
from rich.tree import Tree
from rich.prompt import Confirm

import platformdirs
import virtualenv
import concurrent.futures
import subprocess
import zipfile
import os
import os.path

from json import load as loadJson

from pypackage.commands import Command
from pypackage.util import FormattedProgress, formatPackageName, renderDepTree


class InstallCommand(Command):
    def __init__(self, subparsers):
        super().__init__(subparsers, "install", "Install a .dpy file")
        self.parser.add_argument("path")

    def createVenv(self):
        with self.console.status("Creating virtualenv", spinner = "dots12"):
            return virtualenv.cli_run(["--app-data", os.path.join(self.installPath, "venv-appdata"), "--clear", "--no-vcs-ignore", "--system-site-packages", os.path.join(self.installPath, "venv")])

    def installPackage(self, progress, bar, environ, dpyfile, name, version, path):
        self.console.print(f"Extracting [cyan]{path}")
        filePath = dpyfile.extract(path)
        self.console.print(f"Installing {formatPackageName(name, version)}")
        cmdline = [str(environ.creator.exe), "-Im", "pip", "install", "-qq", "--use-pep517", "--no-deps", "--force-reinstall", filePath]
        #self.console.print(f"[dim]{cmdline}")
        subprocess.run(cmdline).check_returncode()
        progress.update(bar, advance = 1)
        
    def installPackagesToVenv(self, environ, dpyfile, dependencyTree, pathsForDeps):
        oldCwd = os.getcwd()
        newCwd = os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.metadata['name']}-{self.metadata['version']}-install")
        os.makedirs(newCwd, exist_ok = True)
        os.chdir(newCwd)
        alreadyInstalled = set()
        def installLevel(pool, progress, bar, level):
            futureToName = {}
            for name, data in level.items():
                futureToName.update(installLevel(pool, progress, bar, data["depends"]))
            d = {pool.submit(self.installPackage, progress, bar, environ, dpyfile, name, data["version"], pathsForDeps[name]): name for name, data in level.items() if name not in alreadyInstalled}
            for name in level.keys():
                alreadyInstalled.add(name)
            return d
        with FormattedProgress(console = self.console) as progress:
            bar = progress.add_task(f"Installing {formatPackageName(self.metadata['name'], self.metadata['version'])}", total = len(pathsForDeps))
            with concurrent.futures.ThreadPoolExecutor(max_workers = 4) as pool:
                futureToName = installLevel(pool, progress, bar, dependencyTree)
                for future in concurrent.futures.as_completed(futureToName):
                    data = future.result()
        os.chdir(oldCwd)
    
    def run(self, args):
        with zipfile.ZipFile(args.path) as dpyfile:
            with dpyfile.open("metadata.toml", "r") as meta:
                self.metadata = loadToml(meta)
            with dpyfile.open("dependencies.json", "r") as df:
                dependencyTree = loadJson(df)
            self.installPath = os.path.join(platformdirs.user_data_path("pypackage") if os.geteuid() != 0 else platformdirs.site_data_path("pypackage"), "packages", f"{self.metadata['name']}")

            dependenciesByPath = {}
            for file in dpyfile.infolist():
                if os.path.dirname(file.filename) == "dependencies":
                    name, version = parse_sdist_filename(os.path.basename(file.filename))
                    dependenciesByPath[name] = file.filename
            self.console.rule("[cyan bold]Dependencies[/cyan bold]")
            self.console.print(renderDepTree(Tree(formatPackageName(self.metadata['name'], self.metadata['version'])), dependencyTree))
            self.console.rule()
            self.console.print(f"Going to install {formatPackageName(self.metadata['name'], self.metadata['version'])} and [bold cyan]{len(dependenciesByPath)}[/bold cyan] dependencies to [underline]{self.installPath}.")
            if not Confirm.ask("Install software?"):
                self.console.print("[bold red]Aborted.")
                exit(1)
            self.console.print()
            environ = self.createVenv()
            self.installPackagesToVenv(environ, dpyfile, dependencyTree, dependenciesByPath)