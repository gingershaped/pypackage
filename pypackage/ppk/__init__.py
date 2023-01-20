from typing import Optional, BinaryIO
from collections.abc import Collection, Iterator

import tomli
import tomli_w

import json
import os.path

from zipfile import ZipFile, Path as ZipPath
from dataclasses import dataclass
from pathlib import Path

from packaging.version import Version
from packaging.specifiers import SpecifierSet
from packaging.tags import Tag
from packaging.utils import parse_wheel_filename, parse_sdist_filename

DEFAULT_PPK_VERSION = Version("1.0")

@dataclass
class PPKDependencyFile:
    path: Path
    data: bytes
    name: str
    version: Version

    @classmethod
    def fromPath(cls, path: str | Path) -> "PPKDependencyFile":
        path = Path(path)
        with open(path, "rb") as file:
            if path.suffix == ".whl":
                return PPKWheelDependencyFile(path, file.read(), *parse_wheel_filename(path.name))
            elif path.suffix in (".gz", ".zip"):
                return PPKDependencyFile(path, file.read(), *parse_sdist_filename(path.name))
            else:
                raise ValueError(f"Cannot use file {path}!")
    def __hash__(self):
        return hash(self.path)
    def dumpToZip(self, zip: ZipFile, dir = "") -> None:
        with zip.open(os.path.join(dir, self.path.name), "w") as file:
            file.write(self.data)
@dataclass
class PPKWheelDependencyFile(PPKDependencyFile):
    build: Optional[tuple[int, str]]
    tags: set[Tag]

    def __hash__(self):
        return hash(self.path)
    

@dataclass
class PPK:
    name: str
    version: Version
    description: str
    python: SpecifierSet
    dependencyTree: dict
    dependencyFiles: Collection[PPKDependencyFile]
    sourceFiles: Collection[PPKDependencyFile]
    ppkVersion: Version = DEFAULT_PPK_VERSION

    @classmethod
    def dependenciesFromZip(cls, zip: ZipFile, path: str = "dependencies") -> Iterator[PPKDependencyFile]:
        for path in ZipPath(zip, path).iterdir():
            assert path.is_file(), "ppk files should only have files in the dependencies folder!"
            with path.open("rb") as file:
                if ext := os.path.splitext(path.name)[1] == ".whl":
                    yield PPKWheelDependencyFile(path, file.read(), *parse_wheel_filename(path.name))
                elif ext == ".gz":
                    yield PPKDependencyFile(path, file.read(), *parse_sdist_filename(path.name))
    @classmethod
    def fromZipfile(cls, zip: ZipFile) -> "PPK":
        with zip.open("metadata.toml") as metafile:
            meta = tomli.load(metafile)["pypackage"]
        with zip.open("dependencies.dat") as depfile:
            dependencyTree = json.load(depfile)
        return cls(
            meta["name"],
            Version(meta["version"]),
            meta["description"],
            SpecifierSet(meta["python"]),
            dependencyTree,
            set(cls.dependenciesFromZip(zip, "dependencies/")),
            set(cls.dependenciesFromZip(zip, "source/")),
            Version(meta["meta"]["ppk-version"])
        )
        
    def dumpMeta(self, file: BinaryIO) -> None:
        tomli_w.dump({
            "pypackage": {
                "name": self.name,
                "version": str(self.version),
                "description": self.description,
                "python": str(self.python),
                "meta": {
                    "ppk-version": str(self.ppkVersion)
                }
            }
        }, file)
    def dumpDependencyTree(self, file: BinaryIO) -> None:
        file.write(json.dumps(self.dependencyTree).encode("utf-8"))