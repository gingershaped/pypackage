from rich.console import Console
from rich.logging import RichHandler

import argparse
import logging


from pypackage.commands.package import PackageCommand
from pypackage.commands.install import InstallCommand

class PyPackage:
    def __init__(self):
        self.logger = logging.getLogger("pypackage")
        self.console = Console(highlight = False)
        logging.basicConfig(format="%(message)s", handlers=[RichHandler(console = self.console, rich_tracebacks=True)])
        
        self.argparser = argparse.ArgumentParser("pypackage", description = "Package Python software with ease")
        subparsers = self.argparser.add_subparsers(title = "Operations")
        
        self.packageCommand = PackageCommand(subparsers, self.console, self.logger)
        self.installCommand = InstallCommand(subparsers, self.console, self.logger)

    def run(self):
        args = self.argparser.parse_args()
        try:
            args.command.run(args)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            self.console.print("[bold red]Aborted.")
        except:
            self.logger.exception("An uncaught error occured. Please open an issue on GitHub.")
        