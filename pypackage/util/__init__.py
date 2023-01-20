from collections.abc import MutableMapping
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
    for name, _, version, dependencies in ((*key.partition("-"), value) for key, value in depTree.items()):
        tree = baseTree.add(formatPackageName(name, version))
        renderDepTree(tree, dependencies)
    return baseTree

def flattenDict(d, parent_key=''):
    items = []
    for k, v in d.items():
        new_key = k
        if isinstance(v, MutableMapping):
            items.extend(flatten(v).items())
        else:
            items.append((new_key, v))
    return dict(items)

class ProjectMeta(NamedTuple):
    name: str
    version: Version
    description: str
    python: SpecifierSet