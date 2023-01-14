from rich.console import Console

class Command:
    def __init__(self, subparsers, name, help):
        self.parser = subparsers.add_parser(name, help = help)
        self.parser.set_defaults(command = self)
        self.console = Console(highlight = False)

    def printError(self, text):
        self.console.print(f"[bold][red]ERROR[/red]: {text}")