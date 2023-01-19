from typing import Optional
from collections.abc import Collection, Iterable, Iterator

from pypi_simple import PyPISimple, NoSuchProjectError, PYPI_SIMPLE_ENDPOINT, DistributionPackage
from packaging.version import Version, InvalidVersion
from packaging.tags import Tag, sys_tags
from packaging.utils import parse_wheel_filename

from pypackage.util.dependency import Dependency

# If you don't look at it, it can't hurt you.
DistributionPackage.__hash__ = lambda self: hash(self.url) + hash(self.filename)

class NoSdistFound(Exception):
    def __init__(self, dependency: Dependency):
        super().__init__()
        self.dependency = dependency

class PackageLocator:
    def __init__(self, warehouseUrls: Iterable[str] = (PYPI_SIMPLE_ENDPOINT,)):
        self.warehouses = [PyPISimple(url) for url in warehouseUrls]
    def sdistForDependency(self, dependency: Dependency) -> Optional[DistributionPackage]:
        for warehouse in self.warehouses:
            with warehouse:
                try:
                    project = warehouse.get_project_page(dependency.name)
                except NoSuchProjectError:
                    continue
                for package in project.packages:
                    try:
                        if Version(package.version) == dependency.version and package.package_type == "sdist":
                            return package
                    except InvalidVersion:
                        continue
        return None
    def wheelsForDependency(self, dependency: Dependency, acceptedTags: Collection[Tag]) -> Iterator[DistributionPackage]:
        for warehouse in self.warehouses:
            with warehouse:
                try:
                    project = warehouse.get_project_page(dependency.name)
                except NoSuchProjectError:
                    continue
                for package in project.packages:
                    try:
                        if Version(package.version) == dependency.version and package.package_type == "wheel":
                            wheelTags = parse_wheel_filename(package.filename)[-1]
                            for wheelTag in wheelTags:
                                for acceptedTag in acceptedTags:
                                    if wheelTag == acceptedTag:
                                        yield package
                                        break
                    except InvalidVersion:
                        continue

    def locatePackages(self, dependencies: Iterable[Dependency], tags = list(sys_tags())) -> Iterable[Dependency, set[DistributionPackage]]:
        for c, dependency in enumerate(dependencies, 1):
            sdist = self.sdistForDependency(dependency)
            if not sdist:
                raise NoSdistFound(dependency)
            yield dependency, set((sdist,)) | set(self.wheelsForDependency(dependency, tags))