from tomli import load as loadToml
from tomli_w import dump as dumpToml
from rich.columns import Columns
from rich.prompt import Confirm
from rich.progress import Progress
from rich.padding import Padding
from rich.tree import Tree
from pypi_simple import PyPISimple
from result import Ok, Err
from packaging.version import Version, InvalidVersion

import requests
import platformdirs

import os
import os.path
import subprocess
import json
import sys
import concurrent.futures
import zipfile

from pypackage.util import assertOk, formatPackageName, renderDepTree, FormattedProgress
from pypackage.commands import Command

CHUNKSIZE = 512


class PackageCommand(Command):
    def __init__(self, subparsers):
        super().__init__(subparsers, "package", "Package a Python project to a .dpy file")

    def loadPyProject(self):
        if not os.path.isfile("pyproject.toml"):
            return Err("pyproject.toml does not exist!")
        with open("pyproject.toml", "rb") as f:
            data = loadToml(f)
        return Ok(data)
        

    def depsForReq(self, requirement):
        self.console.print(Columns([f"[cyan]{requirement.name}[/cyan]",  f"[bold]{str(requirement.specifier)}"], expand = True, width = 15))
        process = subprocess.run([sys.executable, "-m", "pipdeptree", "--json-tree", "-p", requirement.name], capture_output = True)
        process.check_returncode()
        result = json.loads(process.stdout)[0]
        return result 

    def locatePackagesToDownload(self, dependencies):
        toDownload = []
        with self.console.status("Locating package files", spinner = "dots12"), PyPISimple() as pypi:
            for dependency in dependencies.values():
                target = None
                for package in pypi.get_project_page(dependency.name).packages:
                    try:
                        if Version(package.version) == dependency.version and package.package_type == "sdist":
                            target = package
                            break
                    except InvalidVersion:
                        self.console.print(f"[bold yellow]WARNING[/bold yellow]: Package {package.project} has an invalid version \"{package.version}\". Please alert the maintainer.")
                if not target:
                    self.console.print(f"[bold][red]ERROR[/red]: Unable to find a version matching {dependency.version} for package {dependency.name}.")
                    exit(100)
                toDownload.append(target)
        return toDownload

    def downloadThread(self, package, progress):
        path = os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build", package.filename)
        if os.path.exists(path) and False:
            self.console.print(f"Using cached [bold][cyan]{package.project}[/cyan] {package.version}[/bold]")
            return path
        bar = progress.add_task(f"Downloading [bold][cyan]{package.project}[/cyan] {package.version}[/bold]...", total = None, visible = False)
        request = requests.get(package.url, stream = True)
        with open(path, "wb") as file:
            if "Content-Length" in request.headers:
                progress.start_task(bar)
                total = int(request.headers["Content-Length"]) // CHUNKSIZE
                progress.update(bar, total = total)
                if not total < CHUNKSIZE * 4:
                    progress.update(bar, visible = True)
            else:
                progress.update(bar, visible = True)
            for chunk in request.iter_content(CHUNKSIZE):
                file.write(chunk)
                if "Content-Length" in request.headers:
                    progress.update(bar, advance = 1)
        progress.update(bar, visible = False)
        self.console.print(f"Downloaded [bold][cyan]{package.project}[/cyan] {package.version}[/bold]")
        return path
    
    def downloadPackages(self, packages):
        os.makedirs(os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build"), exist_ok = True)
        results = set()
        with FormattedProgress(console = self.console) as progress, concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            tasks = {executor.submit(self.downloadThread, package, progress): package for package in packages}
            for future in concurrent.futures.as_completed(tasks):
                results.add(future.result())
        return results

    def buildProject(self, projdir):
        cmdline = [sys.executable, "-m", "build", "--sdist", "--outdir", os.path.join(platformdirs.user_cache_path("pypackage"), f"{self.projectMeta['name']}-build"), projdir]
        self.console.print(f"[green]{str(cmdline)}")
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
        config = assertOk(self.loadPyProject())
        with self.console.status("Identifying project", spinner = "dots12") as status:
            match config["build-system"]["build-backend"]:
                case "poetry.core.masonry.api":
                    self.console.print("[dim]Detected Poetry project.")
                    status.update("Resolving dependencies")
                    import pypackage.poetry
                    with open("poetry.lock", "rb") as lockfile:
                        lockData = loadToml(lockfile)
                    tools = pypackage.poetry.PoetryTools(self.console, lockData, config)
                case _:
                    raise RuntimeError("Unknown build system!")

            self.projectMeta = tools.generateMeta()
            dependencies = tools.resolveDeps()
            tree = tools.makeDepTree(dependencies)

        self.console.rule("[cyan bold]Dependencies[/cyan bold]")
        self.console.print(renderDepTree(Tree(formatPackageName(self.projectMeta["name"], self.projectMeta["version"])), tree))
        self.console.rule()
        self.console.print(f"[bold cyan]{len(dependencies)}[/bold cyan] packages to include.")
        if not Confirm.ask("Proceed with packaging?", console = self.console):
            self.console.print("[bold red]Aborted.")
            exit(2)
        toDownload = self.locatePackagesToDownload(dependencies)
        self.console.print("[bold]Downloading packages...")
        paths = self.downloadPackages(toDownload)
    
        self.console.print(f"\nDownloaded [bold cyan]{len(paths)}[/bold cyan] packages.")
        self.console.print("[bold]Building project...[/bold]")
        builtProject = self.buildProject(os.getcwd())
        with self.console.status("[bold]Creating final distribution...", spinner = "dots12"), zipfile.ZipFile(f"{self.projectMeta['name']}.dpy", "w") as dpyfile:
            self.addMetadataToDpy(dpyfile, self.projectMeta)
            self.addDependencyTreeToDpy(dpyfile, tree)
            self.addFilesToDpy(dpyfile, paths, "dependencies")
            self.addFilesToDpy(dpyfile, (builtProject,))
        self.console.print("[bold green]Packaging succeeded!")
        