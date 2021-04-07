#%%
import configparser
from glob import glob
import os
import facebook
import time
from datetime import datetime
import json
from PIL import Image, ImageOps
import shutil
from random import random, randint
from io import BytesIO

def safe_json_dump(fpath, jsoncontent):
    safe_path = fpath + "_safe"
    with open(safe_path, "w") as f:
        json.dump(jsoncontent, f, indent=4)
    shutil.move(safe_path, fpath)


def get_filename(full_path):
    return full_path[full_path.rfind(os.path.sep) + 1:]

class SingleVideoFrameBot:
    def __init__(self, access_token, page_id, movie_title, mirroring_enabled=False,
                 mirror_photos_album_id=None, mirroring_ratio=0.5, best_of_reposting_enabled=False,
                  best_of_reactions_threshold=0, best_of_album_id=None, best_of_wait_hours=24,
                 best_of_to_check_file="bofc.json", frames_directory="frames", frames_ext="jpg",
                 upload_interval=150, bot_name="Bot", delete_files=False):
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
                with open(best_of_check_file) as f:
                    self.best_of_to_check = json.load(f)
            else:
                self.best_of_to_check = {"list": []}
            self.best_of_reactions_threshold = best_of_reactions_threshold
            self.best_of_wait_hours = best_of_wait_hours
            self.best_of_album_id = best_of_album_id
            self.best_of_local_dir = os.path.join("albums", "".join(x for x in f"Bestof_{self.movie_title.replace(os.path.sep, '-')}" if (x.isalnum()) or x in "._- "))
            os.makedirs(self.best_of_local_dir, exist_ok=True)
        self.frames_directory = frames_directory
        self.frames_ext = frames_ext
        self.frames = glob(os.path.join(frames_directory, f"*.{self.frames_ext}"))
        self.frames.sort()
        if len(self.frames) == 0:
            self.total_frames_number = 0
        else:
            self.total_frames_number = self.get_frame_index_number(get_filename(self.frames[-1]))
        print(f"Found {len(self.frames)} frames.")
        self.upload_interval = upload_interval
        if os.path.exists("last_frame_uploaded"):
            with open("last_frame_uploaded") as f:
                self.last_frame_uploaded = int(f.read())
                print(f"Last frame uploaded is {self.last_frame_uploaded}.")
        else:
            self.last_frame_uploaded = -1
        self.bot_name = bot_name
        self.delete_files = delete_files

    def upload_photo(self, image, message, album=None):
        if album is None:
            album = self.page_id
        uploaded = False
        retry_count = 0
        while not uploaded:
            try:
                if type(image) == str:
                    with open(image, "rb") as im:
                        page_post_id = self.graph.put_photo(image=im, message=message, album_path=album + "/photos")['id']
                else:
                    page_post_id = self.graph.put_photo(image=image.getvalue(), message=message, album_path=album + "/photos")['id']
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
            return int(file_name[:file_name.find(".")])

    def get_default_message(self, frame_number):
        return f"{self.movie_title}\nFrame {frame_number} of {self.total_frames_number}"

    def advance_bests(self):
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
                    page_story_id = self.graph.get_object(frame_to_check["post_id"], fields="page_story_id")["page_story_id"]
                    reactions = self.graph.get_object(id=page_story_id, fields="reactions.summary(total_count)")["reactions"]["summary"]["total_count"]
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
                    safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
                    modified = True
        except Exception as e:
            print(e)
        finally:
            if modified:
                safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)

    def start_upload(self):
        for frame in self.frames:
            if self.best_of_reposting_enabled:
                self.advance_bests()

            frame_number = self.get_frame_index_number(get_filename(frame))
            if frame_number <= self.last_frame_uploaded:
                continue

            print(f"Uploading frame {frame_number} of {self.total_frames_number}...")

            message = self.get_default_message(frame_number)
            post_id = self.upload_photo(frame, message)

            with open("last_frame_uploaded", "w") as f:
                self.last_frame_uploaded = frame_number
                f.write(str(frame_number))

            if self.best_of_reposting_enabled:
                self.best_of_to_check["list"].append(
                    {"time": str(datetime.now()), "post_id": post_id, "path": frame,
                     "album_id": best_of_album_id, "frame_number": frame_number})
                safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
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
                        f"There are still {len(self.best_of_to_check['list'])} frames to check for best of. Sleeping for one hour...")
                    time.sleep(3600)

                
#%%


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')

    upload_interval = config.getint("bot_settings", "upload_interval")

    reactions_threshold = config.getint("best_of_album_uploader", "reactions_threshold")
    wait_hours = config.getint("best_of_album_uploader", "wait_hours")

    page_id = config["facebook"]["page_id"]
    if page_id == "":
        page_id = input("Insert page id:")
        config["facebook"]["page_id"] = page_id
        with open("config.ini", "w") as cfg:
            config.write(cfg)
    access_token = config["facebook"]["access_token"]
    if access_token == "":
        access_token = input("Insert access token:")
        config["facebook"]["access_token"] = access_token
        with open("config.ini", "w") as cfg:
            config.write(cfg)
    movie_title = config["bot_settings"]["movie_title"]
    if access_token == "":
        movie_title = input("Insert movie title:")
        config["bot_settings"]["movie_title"] = access_token
        with open("config.ini", "w") as cfg:
            config.write(cfg)

    best_of_reposting_enabled = config.getboolean("best_of_album_uploader", "enabled")
    best_of_album_id = config["best_of_album_uploader"]["best_of_album_id"]
    mirroring_enabled = config.getboolean("mirroring", "enabled")
    mirroring_ratio = config.getfloat("mirroring", "ratio")
    mirror_album_id = config["mirroring"]["mirror_album_id"]
    best_of_check_file = config["best_of_album_uploader"]["local_file"]
    bot_name = config["bot_settings"]["bot_name"]
    delete_files = config["bot_settings"]["delete_files"]

    bot = SingleVideoFrameBot(access_token=access_token, page_id=page_id, movie_title=movie_title,
                              mirror_photos_album_id=mirror_album_id,
                              best_of_reactions_threshold=reactions_threshold,
                              best_of_wait_hours=wait_hours, best_of_to_check_file=best_of_check_file,
                              upload_interval=upload_interval, best_of_album_id=best_of_album_id,
                              mirroring_enabled=mirroring_enabled, best_of_reposting_enabled=best_of_reposting_enabled,
                              mirroring_ratio=mirroring_ratio, delete_files=delete_files, bot_name=bot_name)

    bot.start_upload()



