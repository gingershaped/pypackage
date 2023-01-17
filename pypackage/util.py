from typing import Iterable

def nthitem(iter, n):
    yield from (i[n] for i in iter)

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
        