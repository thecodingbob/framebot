import json
import shutil


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
