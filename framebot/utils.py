import json
import os
import shutil


def safe_json_dump(fpath, jsoncontent):
    safe_path = fpath + "_safe"
    with open(safe_path, "w") as f:
        json.dump(jsoncontent, f, indent=4)
    shutil.move(safe_path, fpath)


def get_filename(full_path):
    return full_path[full_path.rfind(os.path.sep) + 1:]
