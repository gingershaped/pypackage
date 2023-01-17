from pypi_simple import PyPISimple, NoSuchProjectError
from packaging.version import Version, InvalidVersion
from packaging.tags import Tag
from packaging.utils import parse_wheel_filename

from pypackage.util import Dependency

class PackageLocator:
    def __init__(self, warehouseUrls: list[str]):
        self.warehouses = [PyPISimple(url) for url in warehouseUrls]
    def sdistForDependency(self, dependency: Dependency):
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
    def wheelsForDependency(self, dependency: Dependency, acceptedTags: set[Tag]):
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
                            for acceptedTag in acceptedTags:
                                for wheelTag in wheelTags:
                                    if acceptedTag == wheelTag:
                                        yield package
                                        break
                    except InvalidVersion:
                        continue