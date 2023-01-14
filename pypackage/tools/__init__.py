from .poetry import PoetryTools

def toolForBuildSystem(buildSystem):
    match buildSystem:
        case "poetry.core.masonry.api":
            return PoetryTools