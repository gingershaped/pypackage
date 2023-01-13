import argparse
from pypackage.commands.package import PackageCommand
from pypackage.commands.install import InstallCommand

class PyPackage:
    def __init__(self):
        self.argparser = argparse.ArgumentParser("pypackage", description = "Package Python software with ease")
        subparsers = self.argparser.add_subparsers(title = "Operations")
        self.packageCommand = PackageCommand(subparsers)
        self.installCommand = InstallCommand(subparsers)

    def run(self):
        args = self.argparser.parse_args()
        args.command.run(args)
        