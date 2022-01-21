import json
import shutil


def safe_json_dump(fpath: str, jsoncontent: dict):
    safe_path = fpath + "_safe"
    with open(safe_path, "w") as f:
        json.dump(jsoncontent, f, indent=4)
    shutil.move(safe_path, fpath)
