import platformdirs

from rich.progress import Progress, DownloadColumn
from rich.prompt import Confirm
from rich.tree import Tree
from tomli import load as loadToml

import os
import os.path
import itertools
import zipfile
import concurrent.futures
import sys
import subprocess

from pypackage.commands import Command
from pypackage.dpy_tools import DpyTools
from pypackage.package_locator import PackageLocator
from pypackage.pooled_downloader import PooledDownloader
from pypackage.progress_manager import RichProgressManager
from pypackage.tools import toolForBuildSystem
from pypackage.util import renderDepTree, formatPackageName, nthitem

class PackageCommand(Command):
    def __init__(self, subparsers):
        super().__init__(subparsers, "package", "Package a Python project to a .dpy file")
        self.parser.add_argument("path", nargs = "?", default = ".")
        self.dpyTools = DpyTools()
        self.locator = PackageLocator()

    def locatePackages(self, status, dependencies):
        for c, packages in enumerate(nthitem(self.locator.locatePackages(dependencies.values()), 1)):
            status.update(f"Locating packages ({c}/{len(dependencies)})")
            yield from packages
    def queuePackageDownloads(self, downloader, packages, paths):
        for package, path in zip(packages, paths):
            future = downloader.downloadUrlToPath(package.url, path, f"Downloading [cyan]{package.filename}[/cyan]...")
            yield future
    def downloadPackages(self, downloader, packages, paths):
        for package, future in zip(packages, self.queuePackageDownloads(downloader, packages, paths)):
            self.console.print(f"Downloaded [cyan]{package.filename}[/cyan]")
            yield future.result()
    def buildProject(self, projdir):
        cmdline = [sys.executable, "-m", "build", "--sdist", "--outdir", os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build"), projdir]
        subprocess.run(cmdline)
        return os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build", f"{self.projectMeta['name']}-{self.projectMeta['version']}.tar.gz")

    def run(self, args):
        oldCwd = os.getcwd()
        os.chdir(args.path)
        
        if not os.path.isfile("pyproject.toml"):
            self.printError(f"{os.path.join(os.getcwd(), 'pyproject.toml')} does not exist!")
            exit(101)
        with self.console.status("Identifying project", spinner = "dots12"), open("pyproject.toml", "rb") as pyprojectFile:
            pyproject = loadToml(pyprojectFile)
            
            tools = toolForBuildSystem(pyproject["build-system"]["build-backend"])(self.console, pyproject)
            self.projectMeta = tools.generateMeta()
            self.cachePath = os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build")
            os.makedirs(self.cachePath, exist_ok = True)
            
            dependencies = tools.resolveDeps()
            tree = tools.makeDepTree(dependencies)
        self.console.print("Identifying project... done")

        self.console.rule("[cyan bold]Dependencies[/cyan bold]")
        self.console.print(renderDepTree(Tree(formatPackageName(self.projectMeta["name"], self.projectMeta["version"])), tree))
        self.console.rule()
        self.console.print(f"[bold cyan]{len(dependencies)}[/bold cyan] packages to include.")
        if not Confirm.ask("Proceed with packaging?", console = self.console):
            self.console.print("[bold red]Aborted.")
            exit(2)

        self.console.print()
        with self.console.status("Locating packages", spinner = "dots12") as status:
            packages = list(self.locatePackages(status, dependencies))
        
        self.console.print("[bold]Downloading packages...")
        with PooledDownloader(RichProgressManager(
            self.console,
            *Progress.get_default_columns(),
            DownloadColumn(),
            expand = True,
            transient = True
        )) as downloader:
            packagePaths = list(self.downloadPackages(
                downloader,
                packages,
                (os.path.join(self.cachePath, package.filename) for package in packages)
            ))
        
        self.console.print("[bold]Building project...[/bold]")
        builtProject = self.buildProject(os.getcwd())
        
        os.makedirs("dist", exist_ok = True)
        dpyPath = f"dist/{self.projectMeta['name']}.dpy"
        with self.console.status("[bold]Creating final distribution...", spinner = "dots12"), zipfile.ZipFile(dpyPath, "w") as dpyfile:
            self.dpyTools.addMetadataToDpy(dpyfile, self.projectMeta)
            self.dpyTools.addDependencyTreeToDpy(dpyfile, tree)
            for path in itertools.chain(self.dpyTools.addFilesToDpy(dpyfile, packagePaths, "dependencies"), self.dpyTools.addFilesToDpy(dpyfile, (builtProject,))):
                self.console.print(f"Adding [cyan]{path}")
            
        self.console.print("Creating final distribution... done")
        self.console.print(f"[green]Distribution located at {dpyPath}")
        self.console.print("[bold green]Packaging succeeded!")
        os.chdir(oldCwd)