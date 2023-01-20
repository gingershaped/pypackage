from typing import Optional
from collections.abc import Collection, Iterable, Iterator

from pypi_simple import PyPISimple, NoSuchProjectError, PYPI_SIMPLE_ENDPOINT, DistributionPackage
from packaging.version import Version, InvalidVersion
from packaging.tags import Tag, sys_tags
from packaging.utils import parse_wheel_filename

from pypackage.util.package import PurePackage, RemotePackageFile, RemoteSdistPackageFile, RemoteWheelPackageFile

# If you don't look at it, it can't hurt you.
DistributionPackage.__hash__ = lambda self: hash(self.url) + hash(self.filename)

class NoSdistFound(Exception):
    def __init__(self, dependency: PurePackage):
        super().__init__()
        self.dependency = dependency

class PackageLocator:
    def __init__(self, warehouseUrls: Iterable[str] = (PYPI_SIMPLE_ENDPOINT,)):
        self.warehouses = [PyPISimple(url) for url in warehouseUrls]
    def sdistForPackage(self, dependency: PurePackage) -> Optional[RemoteSdistPackageFile]:
        for warehouse in self.warehouses:
            with warehouse:
                try:
                    project = warehouse.get_project_page(dependency.name)
                except NoSuchProjectError:
                    continue
                for package in project.packages:
                    try:
                        if Version(package.version) == dependency.version and package.package_type == "sdist":
                            return RemoteSdistPackageFile(package.url, package.filename, package.name, Version(package.version))
                    except InvalidVersion:
                        continue
        return None
    def wheelsForPackage(self, dependency: PurePackage, acceptedTags: Collection[Tag]) -> Iterator[RemoteWheelPackageFile]:
        for warehouse in self.warehouses:
            with warehouse:
                try:
                    project = warehouse.get_project_page(dependency.name)
                except NoSuchProjectError:
                    continue
                for package in project.packages:
                    try:
                        if Version(package.version) == dependency.version and package.package_type == "wheel":
                            _, _, build, wheelTags = parse_wheel_filename(package.filename)
                            for wheelTag in wheelTags:
                                for acceptedTag in acceptedTags:
                                    if wheelTag == acceptedTag:
                                        yield RemoteWheelPackageFile(package.url, package.filename, package.name, Version(package.version), wheelTags, build)
                                        break
                    except InvalidVersion:
                        continue

    def locatePackages(self, dependencies: Iterable[PurePackage], tags = list(sys_tags())) -> Iterable[PurePackage, set[RemotePackageFile]]:
        for c, dependency in enumerate(dependencies, 1):
            sdist = self.sdistForPackage(dependency)
            if not sdist:
                raise NoSdistFound(dependency)
            yield dependency, set((sdist,)) | set(self.wheelsForPackage(dependency, tags))