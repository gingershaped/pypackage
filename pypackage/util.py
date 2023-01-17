from result import Ok, Err
from rich.progress import Progress
from rich.align import Align
from rich.padding import Padding


def assertOk(result):
    match result:
        case Ok(data):
            return data
        case Err(e):
            raise RuntimeError(e)

def formatPackageName(name, version):
    return f"[bold][cyan]{name}[/cyan] {version}"

def renderDepTree(baseTree, depTree):
    for name, data in depTree.items():
        tree = baseTree.add(formatPackageName(name, data["version"]))
        renderDepTree(tree, data["depends"])
    return baseTree  

class Dependency:
    def __init__(self, name, version, depends = []):
        self.name = name
        self.version = version
        self.depends = depends

    def toTree(self, dependencies, parent):
        parent[self.name] = {"version": str(self.version), "depends": {}}
        for dependency in self.depends:
            dependencies[dependency.name].toTree(dependencies, parent[self.name]["depends"])
        return parent
    def toTreeOld(self, dependencies, parent):
        tree = parent.add(formatPackageName(self.name, str(self.version)))
        for dependency in self.depends:
            dependencies[dependency.name].toTree(dependencies, tree)
        return parent
        