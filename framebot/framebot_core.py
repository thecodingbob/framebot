from glob import glob
import os
import time
from datetime import datetime
import json
# noinspection PyPackageRequirements
import facebook
from PIL import Image, ImageOps
import shutil
from random import random
from io import BytesIO
import re

from framebot import utils

LAST_FRAME_UPLOADED_FILE = "last_frame_uploaded"


class FrameBot:
    def __init__(self, access_token, page_id, movie_title, mirroring_enabled=False,
                 mirror_photos_album_id=None, mirroring_ratio=0.5, best_of_reposting_enabled=False,
                 best_of_reactions_threshold=0, best_of_album_id=None, best_of_wait_hours=24,
                 best_of_to_check_file="bofc.json", frames_directory="frames", frames_ext="jpg",
                 frames_naming="$N$",
                 upload_interval=150, bot_name="Bot", delete_files=False):
        print(f"Initializing {bot_name}...")
        self.access_token = access_token
        self.page_id = page_id
        self.movie_title = movie_title
        self.graph = facebook.GraphAPI(access_token)
        self.mirroring_enabled = mirroring_enabled
        if self.mirroring_enabled:
            self.mirroring_ratio = mirroring_ratio
            self.mirror_photos_album_id = mirror_photos_album_id
        self.best_of_reposting_enabled = best_of_reposting_enabled
        if self.best_of_reposting_enabled:
            self.best_of_to_check_file = best_of_to_check_file
            if os.path.exists(self.best_of_to_check_file):
                print(f"Found existing {self.best_of_to_check_file} files for best of checks, trying to load it...")
                with open(best_of_to_check_file) as f:
                    self.best_of_to_check = json.load(f)
            else:
                self.best_of_to_check = {"list": []}
            self.best_of_reactions_threshold = best_of_reactions_threshold
            self.best_of_wait_hours = best_of_wait_hours
            self.best_of_album_id = best_of_album_id
            self.best_of_local_dir = os.path.join("albums", "".join(
                x for x in f"Bestof_{self.movie_title.replace(os.path.sep, '-').replace(' ', '_')}" if
                (x.isalnum()) or x in "._- "))
            print(f"Best ofs will be saved locally in the directory {self.best_of_local_dir}.")
            os.makedirs(self.best_of_local_dir, exist_ok=True)
        self.frames_directory = frames_directory
        self.frames_ext = frames_ext
        self.frames = glob(os.path.join(frames_directory, f"*.{self.frames_ext}"))
        expr = "^" + frames_directory + "\\" + os.path.sep + frames_naming.replace("$N$", "(\\d+)")
        expr += "\\." + self.frames_ext + "$"
        self.frames_naming = re.compile(expr)
        self.frames.sort(key=lambda frame: self.get_frame_index_number(frame))
        if len(self.frames) == 0:
            self.total_frames_number = 0
        else:
            self.total_frames_number = self.get_frame_index_number(self.frames[-1])
        print(f"Found {len(self.frames)} frames.")
        self.upload_interval = upload_interval
        if os.path.exists(LAST_FRAME_UPLOADED_FILE):
            with open(LAST_FRAME_UPLOADED_FILE) as f:
                self.last_frame_uploaded = int(f.read())
                print(f"Last frame uploaded is {self.last_frame_uploaded}.")
        else:
            print(f"Starting the bot from the first frame.")
            self.last_frame_uploaded = -1
        self.bot_name = bot_name
        self.delete_files = delete_files
        print("Done initializing.\n")

    def upload_photo(self, image, message, album=None):
        if album is None:
            album = self.page_id
        uploaded = False
        retry_count = 0
        while not uploaded:
            try:
                if type(image) == str:
                    with open(image, "rb") as im:
                        page_post_id = self.graph.put_photo(image=im, message=message, album_path=album + "/photos")[
                            'id']
                else:
                    page_post_id = \
                        self.graph.put_photo(image=image.getvalue(), message=message, album_path=album + "/photos")[
                            'id']
                uploaded = True
            except Exception as e:
                print(e)
                if retry_count < 5:
                    print("Retrying...")
                    time.sleep(60 * 30 if "spam" in str(e) else 180)
                else:
                    print("Something's wrong. Check it out.")
                    exit()
                retry_count += 1
        return page_post_id

    def post_mirror_frame(self, image_path, og_message):
        im = Image.open(image_path)
        flippedhalf = ImageOps.mirror(im.crop((0, 0, im.size[0] // 2, im.size[1])))
        im.paste(flippedhalf, (im.size[0] // 2, 0))
        image_file = BytesIO()
        im.save(image_file, "jpeg")
        lines = og_message.split("\n")
        message = ""
        for line in lines:
            message += line[:len(line) // 2] + line[len(line) // 2::-1] + "\n"

        message += f"\nJust a randomly mirrored image.\n-{self.bot_name}"
        self.upload_photo(image_file, message, self.mirror_photos_album_id)

    def get_frame_index_number(self, file_name):
        return int(self.frames_naming.search(file_name).group(1))

    def get_default_message(self, frame_number):
        return f"{self.movie_title}\nFrame {frame_number} of {self.total_frames_number}"

    def advance_bests(self):
        print(f"Checking for best of reuploading...")
        checked_all = False
        modified = False
        try:
            while (not checked_all) and len(self.best_of_to_check["list"]) > 0:
                frame_to_check = self.best_of_to_check["list"][0]
                timestamp = datetime.fromisoformat(frame_to_check["time"])
                elapsed_hours = ((datetime.now() - timestamp).total_seconds() // 3600)
                if elapsed_hours < self.best_of_wait_hours:
                    checked_all = True
                else:
                    print(f"Checking entry {frame_to_check}...")
                    page_story_id = self.graph.get_object(frame_to_check["post_id"], fields="page_story_id")[
                        "page_story_id"]
                    reactions = \
                        self.graph.get_object(id=page_story_id, fields="reactions.summary(total_count)")["reactions"][
                            "summary"]["total_count"]
                    if reactions > self.best_of_reactions_threshold:
                        print(f"Uploading frame {frame_to_check['path']} to best of album...")
                        message = f"Reactions after {int(elapsed_hours)} hours: {reactions}.\n" + \
                                  f"Original post: https://facebook.com/{frame_to_check['post_id']}\n\n" + \
                                  self.get_default_message(frame_to_check['frame_number'])
                        if os.path.exists(frame_to_check["path"]):
                            self.upload_photo(frame_to_check["path"], message, frame_to_check["album_id"])
                            shutil.copyfile(frame_to_check["path"],
                                            os.path.join(self.best_of_local_dir,
                                                         f"Frame {frame_to_check['frame_number']} "
                                                         f"id {frame_to_check['post_id']} "
                                                         f"reactions {reactions}.jpg"))
                            print("Done.\n")
                        else:
                            print(f"File {frame_to_check['path']} is missing. Skipping uploading to best of album...")
                    if self.delete_files:
                        os.remove(frame_to_check["path"])
                    self.best_of_to_check["list"].pop(0)
                    utils.safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
                    modified = True
        except Exception as e:
            print(e)
        finally:
            if modified:
                utils.safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
        print("Done checking for best ofs.\n")

    def start_upload(self):
        for frame in self.frames:
            frame_number = self.get_frame_index_number(frame)
            if frame_number <= self.last_frame_uploaded:
                continue

            if self.best_of_reposting_enabled:
                self.advance_bests()

            print(f"Uploading frame {frame_number} of {self.total_frames_number}...")

            message = self.get_default_message(frame_number)
            post_id = self.upload_photo(frame, message)

            with open(LAST_FRAME_UPLOADED_FILE, "w") as f:
                self.last_frame_uploaded = frame_number
                f.write(str(frame_number))

            if self.best_of_reposting_enabled:
                print(f"Queueing frame {frame_number} for best of checking...")
                self.best_of_to_check["list"].append(
                    {"time": str(datetime.now()), "post_id": post_id, "path": frame,
                     "album_id": self.best_of_album_id, "frame_number": frame_number})
                utils.safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
            if self.mirroring_enabled and random() > (1 - self.mirroring_ratio / 100):
                print("Posting mirrored frame...")
                self.post_mirror_frame(frame, message)
            print(f"Uploaded.\nWaiting {self.upload_interval} seconds before the next one...\n")
            if self.delete_files and not self.best_of_reposting_enabled:
                os.remove(frame)
            time.sleep(self.upload_interval)

        if self.best_of_reposting_enabled:
            self.best_of_wait_hours = self.best_of_wait_hours // 2
            while self.best_of_to_check['list']:
                self.advance_bests()
                if self.best_of_to_check['list']:
                    print(
                        f"There are still {len(self.best_of_to_check['list'])} frames to check for best of. Sleeping "
                        f"for one hour...")
                    time.sleep(3600)
        os.remove(LAST_FRAME_UPLOADED_FILE)
