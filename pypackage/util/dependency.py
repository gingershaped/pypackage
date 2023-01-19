from collections.abc import Collection, Mapping
from dataclasses import dataclass

from rich.tree import Tree
from packaging.version import Version

@dataclass
class Dependency:
    name: str
    version: Version
    depends: Collection["Dependency"]
    
    def toTree(self, dependencies: Mapping[str, "Dependency"], parent: Tree) -> Tree:
        parent[self.name] = {"version": str(self.version), "depends": {}}
        for dependency in self.depends:
            dependencies[dependency.name].toTree(dependencies, parent[self.name]["depends"])
        return parent