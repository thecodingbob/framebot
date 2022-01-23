import json
import logging
import shutil
import sys
from logging import Logger


def safe_json_dump(fpath: str, jsoncontent: dict) -> None:
    """
    Utility function used to avoid json file corruption in case of abrupt termination of the script.
    :param fpath: path where the json has to be saved
    :param jsoncontent: the content to be saved
    """
    safe_path = fpath + "_safe"
    with open(safe_path, "w") as f:
        json.dump(jsoncontent, f, indent=4)
    shutil.move(safe_path, fpath)


def get_logger(name: str, level: int = logging.INFO) -> Logger:
    logger = Logger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('[%(asctime)s|%(name)s|%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
