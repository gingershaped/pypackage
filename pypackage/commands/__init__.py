class Command:
    def __init__(self, subparsers, console, parentLogger, name, help):
        self.console = console
        self.logger = parentLogger.getChild(name)
        
        self.parser = subparsers.add_parser(name, help = help)
        self.parser.set_defaults(command = self)