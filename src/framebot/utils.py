import logging
import shutil
import sys
from logging import Logger
from pathlib import Path
from typing import Union, Any

import jsonpickle


def safe_json_dump(fpath: Union[str, Path], obj: Any) -> None:
    """
    Utility function used to avoid json file corruption in case of abrupt termination of the script
    :param fpath: path where the json has to be saved
    :param obj: the content to be saved
    """
    if issubclass(type(fpath), Path):
        fpath = str(fpath)
    safe_path = fpath + "_safe"
    with open(safe_path, "w") as f:
        json_str = jsonpickle.dumps(obj, indent=4)
        f.write(json_str)
    shutil.move(safe_path, fpath)


def load_obj_from_json_file(fpath: Union[str, Path]) -> Any:
    """

    :param fpath:
    :return:
    """
    with open(fpath, "r") as f:
        str_result = f.read()
        result = jsonpickle.decode(str_result)
    return result


def get_logger(name: str, level: int = logging.INFO) -> Logger:
    """

    :param name:
    :param level:
    :return:
    """
    if name is None or level is None:
        raise ValueError("name and level must not be None!")
    logger = Logger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('[%(asctime)s|%(name)s|%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class LoggingObject(object):
    """
    Object that comes equipped with a logger
    """
    logger: Logger

    def __init__(self):
        self.logger = get_logger(type(self).__name__)
