from typing import Optional
from collections.abc import Collection, Iterator

from pathlib import Path
from enum import Enum
from dataclasses import dataclass

from packaging.version import Version
from packaging.markers import Marker
from packaging.specifiers import SpecifierSet
from packaging.tags import Tag

from pypackage.ppk import PPKDependencyFile

@dataclass
class PackageFile:
    name: str
    version: Version
@dataclass
class RemotePackageFile(PackageFile):
    url: str
    filename: str
@dataclass
class SdistPackageFile(PackageFile):
    pass
@dataclass
class RemoteSdistPackageFile(SdistPackageFile, RemotePackageFile):
    pass
@dataclass
class ArchiveSdistPackageFile(SdistPackageFile):
    archivePath: Path
@dataclass
class WheelPackageFile(PackageFile):
    name: str
    version: Version
    tags: Collection[Tag]
    build: Optional[int]
@dataclass
class RemoteWheelPackageFile(WheelPackageFile, RemotePackageFile):
    pass
@dataclass
class ArchiveWheelPackageFile(WheelPackageFile):
    archivePath: Path

class PurePackage:
    def __init__(
        self,
        name: str,
        version: Version,
        pythonSpecifiers: SpecifierSet,
        description: str = "",
        dependencies: Collection["PurePackage"] = [],
        marker: Optional[Marker] = None,
    ):
        self.name = name
        self.version = version
        self.pythonSpecifiers = pythonSpecifiers
        self.description = description
        self.dependencies = dependencies
        self.marker = marker
    def iterDependencies(self) -> Iterator["PurePackage"]:
        yield self
        for child in self.data:
            yield from child.iterDependencies()
    def serialize(self) -> dict[str]:
        return {
            "name": self.name,
            "version": str(self.version),
            "python-specifiers": str(self.pythonSpecifiers),
            "description": self.description,
            "marker": str(self.marker) if self.marker else None,
            "dependencies": [dependency.serialize() for dependency in self.dependencies]
        }
    def addFiles(self, files: Collection[PackageFile]) -> "Package":
        return Package(self.name, self.version, self.pythonSpecifiers, files, self.description, self.dependencies, self.marker)
class Package(PurePackage):
    def __init__(
        self,
        name: str,
        version: Version,
        pythonSpecifiers: SpecifierSet,
        files: Collection[PackageFile],
        description: str = "",
        dependencies: Collection["PurePackage"] = [],
        marker: Optional[Marker] = None
    ):
        self.name = name
        self.version = version
        self.pythonSpecifiers = pythonSpecifiers
        self.description = description
        self.dependencies = dependencies
        self.marker = marker
        