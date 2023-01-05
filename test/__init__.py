from os.path import dirname, realpath
from pathlib import Path


RESOURCES_DIR: Path = Path(dirname(realpath(__file__))).joinpath("resources").absolute()



