from tomli import load as loadToml
from tomli_w import dump as dumpToml
from rich.prompt import Confirm
from rich.progress import Progress, DownloadColumn
from rich.tree import Tree
from pypi_simple import PYPI_SIMPLE_ENDPOINT
from packaging.tags import sys_tags

import platformdirs

import os
import os.path
import subprocess
import json
import sys
import concurrent.futures
import zipfile
import functools

from pypackage.util import formatPackageName, renderDepTree
from pypackage.commands import Command
from pypackage.package_locator import PackageLocator
from pypackage.pooled_downloader import PooledDownloader
from pypackage.progress_manager import RichProgressManager
from pypackage.tools import toolForBuildSystem

class PackageCommand(Command):
    def __init__(self, subparsers):
        super().__init__(subparsers, "package", "Package a Python project to a .dpy file")
        self.parser.add_argument("path", nargs = "?", default = ".")

    def locatePackages(self, status, dependencies, warehouseUrls = (PYPI_SIMPLE_ENDPOINT,), tags = list(sys_tags())):
        locator = PackageLocator(warehouseUrls)
        for c, dependency in enumerate(dependencies.values(), 1):
            sdist = locator.sdistForDependency(dependency)
            if not sdist:
                self.printError(f"Unable to find match for {formatPackageName(dependency.name, dependency.version)}!")
                exit(100)
            yield sdist
            for i in locator.wheelsForDependency(dependency, tags):
                yield i
            status.update(f"Locating packages ({c}/{len(dependencies)})")

    def downloadPackages(self, downloader, packages, paths):
        for package, path in zip(packages, paths):
            future = downloader.downloadUrlToPath(package.url, path, f"Downloading [cyan]{package.filename}[/cyan]...")
            future.add_done_callback(functools.partial(lambda package, f: self.console.print(f"Downloaded [cyan]{package.filename}[/cyan]") if not f.cancelled() else 0, package))
            yield future
    def buildProject(self, projdir):
        cmdline = [sys.executable, "-m", "build", "--sdist", "--outdir", os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build"), projdir]
        #self.console.print(f"[green]{str(cmdline)}")
        subprocess.run(cmdline)
        return os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build", f"{self.projectMeta['name']}-{self.projectMeta['version']}.tar.gz")

    def addMetadataToDpy(self, dpy, projectMeta):
        with dpy.open("metadata.toml", "w") as f:
            dumpToml(projectMeta, f)
    def addDependencyTreeToDpy(self, dpy, tree):
        with dpy.open("dependencies.json", "w") as f:
            f.write(json.dumps(tree).encode("utf-8"))
    def addFilesToDpy(self, dpy, paths, arcbase = ""):
        for path in paths:
            self.console.print(f"Adding [cyan]{path}")
            dpy.write(path, arcname = os.path.join(arcbase, os.path.basename(path)))
    
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
            expand = True
        )) as downloader:
            packagePaths = list(i.result() for i in concurrent.futures.wait(
                self.downloadPackages(
                    downloader,
                    packages,
                    (os.path.join(self.cachePath, package.filename) for package in packages)
                )
            )[0])
        
        self.console.print("[bold]Building project...[/bold]")
        builtProject = self.buildProject(os.getcwd())
        
        os.makedirs("dist", exist_ok = True)
        dpyPath = f"dist/{self.projectMeta['name']}.dpy"
        with self.console.status("[bold]Creating final distribution...", spinner = "dots12"), zipfile.ZipFile(dpyPath, "w") as dpyfile:
            self.addMetadataToDpy(dpyfile, self.projectMeta)
            self.addDependencyTreeToDpy(dpyfile, tree)
            self.addFilesToDpy(dpyfile, packagePaths, "dependencies")
            self.addFilesToDpy(dpyfile, (builtProject,))
            
        self.console.print("Creating final distribution... done")
        self.console.print(f"[green]Distribution located at {dpyPath}")
        self.console.print("[bold green]Packaging succeeded!")
        os.chdir(oldCwd)