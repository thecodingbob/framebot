import sys
from os.path import dirname, realpath
from pathlib import Path

RESOURCES_DIR: Path = Path(dirname(realpath(__file__))).joinpath("resources").resolve()

try:
    import framebot
except ModuleNotFoundError:
    sys.path.append(str(Path.cwd().joinpath("src")))
