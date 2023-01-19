from enum import Enum
from typing import NamedTuple

from packaging.version import Version
from packaging.specifiers import SpecifierSet

class DependencyType(Enum):
    SDIST = "sdist"
    WHEEL = "wheel"

def nthitem(iter, n):
    yield from (i[n] for i in iter)

def formatPackageName(name, version):
    return f"[bold][cyan]{name}[/cyan] {version}"

def renderDepTree(baseTree, depTree):
    for name, data in depTree.items():
        tree = baseTree.add(formatPackageName(name, data["version"]))
        renderDepTree(tree, data["depends"])
    return baseTree

class ProjectMeta(NamedTuple):
    name: str
    version: Version
    description: str
    python: SpecifierSet