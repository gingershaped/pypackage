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
from pypackage.buildsystems import BUILD_SYSTEMS
from pypackage.ppk import PPK, PPKDependencyFile
from pypackage.locators.package_locator import PackageLocator
from pypackage.util import renderDepTree, formatPackageName, nthitem, ProjectMeta
from pypackage.util.pooled_downloader import PooledDownloader
from pypackage.util.progress_manager import RichProgressManager

class PackageCommand(Command):
    def __init__(self, subparsers, console, parentLogger):
        super().__init__(subparsers, console, parentLogger, "package", "Package a Python project to a .ppk file")
        self.parser.add_argument("path", nargs = "?", default = ".")
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
        cmdline = [sys.executable, "-m", "build", "--sdist", "--outdir", os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta.name}-build"), projdir]
        subprocess.run(cmdline)
        return os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta.name}-build", f"{self.projectMeta.name}-{self.projectMeta.version}.tar.gz")

    def run(self, args):
        os.chdir(args.path)
        
        if not os.path.isfile("pyproject.toml"):
            self.logger.critical(f"{os.path.join(os.getcwd(), 'pyproject.toml')} does not exist!")
            exit(101)
        with self.console.status("Identifying project", spinner = "dots12"), open("pyproject.toml", "rb") as pyprojectFile:
            pyproject = loadToml(pyprojectFile)
            
            tools = BUILD_SYSTEMS[pyproject["build-system"]["build-backend"]](self.console, pyproject)
            self.projectMeta = tools.generateMeta()
            self.cachePath = os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta.name}-build")
            os.makedirs(self.cachePath, exist_ok = True)
            
            dependencies = tools.resolveDeps()
            tree = tools.makeDepTree(dependencies)
        self.console.print("Identifying project... done")

        self.console.rule("[cyan bold]Dependencies[/cyan bold]")
        self.console.print(renderDepTree(Tree(formatPackageName(self.projectMeta.name, self.projectMeta.version)), tree))
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
        ppkPath = f"dist/{self.projectMeta.name}-{self.projectMeta.version}.ppk"
        with self.console.status("[bold]Creating final distribution...", spinner = "dots12"), zipfile.ZipFile(ppkPath, "w") as ppkfile:
            ppk = PPK(*tools.generateMeta(), tree, list(map(PPKDependencyFile.fromPath, packagePaths)), [PPKDependencyFile.fromPath(builtProject)])
            with ppkfile.open("metadata.toml", "w") as metafile:
                ppk.dumpMeta(metafile)
            with ppkfile.open("dependencies.dat", "w") as treefile:
                ppk.dumpDependencyTree(treefile)
            for file in ppk.dependencyFiles:
                self.console.print(f"Adding [cyan]{file.path.name}")
                file.dumpToZip(ppkfile, "dependencies")
            for file in ppk.sourceFiles:
                self.console.print(f"Adding [cyan]{file.path.name}")
                file.dumpToZip(ppkfile, "source")
            
        self.console.print("Creating final distribution... done")
        self.console.print(f"[green]Distribution located at {ppkPath}")
        self.console.print("[bold green]Packaging succeeded!")