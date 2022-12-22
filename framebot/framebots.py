import json
import os
import re
import shutil
import time
from datetime import datetime
from glob import glob
from io import BytesIO
from random import random
from typing import Union

import facebook
from PIL import Image, ImageOps

import utils

LAST_FRAME_UPLOADED_FILE = "last_frame_uploaded"


def safe_json_dump(fpath: str, jsoncontent: dict):
    safe_path = fpath + "_safe"
    with open(safe_path, "w") as f:
        json.dump(jsoncontent, f, indent=4)
    shutil.move(safe_path, fpath)


def get_filename(full_path: str):
    return full_path[full_path.rfind(os.path.sep) + 1:]


class SingleVideoFrameBot:
    def __init__(self, access_token: str, page_id: str, movie_title: str, mirroring_enabled: bool = False,
                 mirror_photos_album_id: str = None, mirroring_ratio: float = 0.5,
                 best_of_reposting_enabled: bool = False, best_of_reactions_threshold: int = 0,
                 best_of_album_id: str = None, best_of_wait_hours: int = 24, best_of_to_check_file: str = "bofc.json",
                 frames_directory: str = "frames", frames_ext: str = "jpg", frames_naming: str = "$N$",
                 upload_interval: int = 150, bot_name: str = "Bot", delete_files: bool = False):
        """
        Constructor
        :param access_token: Access token for the Facebook page
        :param page_id: Id of the Facebook page
        :param movie_title: Title of the movie/episode/whatever you want to post. Will be showed in the posts
            description
        :param mirroring_enabled: If the random mirroring of the images is enabled or not
        :param mirror_photos_album_id: Id of the album where the mirrored photos will be posted
        :param mirroring_ratio: Percentage of frames that will get mirroring
        :param best_of_reposting_enabled: If the reposting of the frames with more reactions is enabled or not
        :param best_of_reactions_threshold: If the reposting is enabled, all the frames having more than this number
            of reactions after the check will be reposted
        :param best_of_album_id: Id of the album where best of frames will be reposted
        :param best_of_wait_hours: Hours to wait before checking if frames have exceeded the reposting threshold
        :param best_of_to_check_file: File used to keep information about frames that have yet to be checked for
            best of reposting
        :param frames_directory: Directory where the frame files are stored
        :param frames_ext: Extension of the frame files
        :param frames_naming: Naming pattern of the frame files e.g frame$N$
        :param upload_interval: time interval between one frame and the other, in seconds
        :param bot_name: bot's name, currently used only in the mirrored posts
        :param delete_files: if this flag is enabled, the frame files will be deleted after those served their purpose
        """
        self.logger = utils.get_logger(__name__)

        # Bot base settings
        self.bot_name = bot_name
        self.logger.info(f"Starting bot '{self.bot_name}'.")
        self.movie_title = movie_title
        self.logger.info(f"Movie/video title is '{self.movie_title}'.")
        self.upload_interval = upload_interval
        self.logger.info(f"A frame will be posted every {self.upload_interval} seconds.")
        self.delete_files = delete_files
        self.logger.info(f"Frames will be deleted after posting and after the best-of checking is done (if enabled).")
        self.frames_directory = frames_directory
        self.frames_ext = frames_ext
        self.frames = glob(os.path.join(frames_directory, f"*.{self.frames_ext}"))
        expr = "^" + frames_directory + "\\" + os.path.sep + frames_naming.replace("$N$", "(\\d+)")
        expr += "\\." + self.frames_ext + "$"
        self.frames_naming = re.compile(expr)
        self.logger.info(f"Frames will be picked from the directory '{self.frames_directory}'. Will search for "
                         f".{frames_ext} files with naming pattern {frames_naming}.")
        self.frames.sort(key=lambda frame: self.get_frame_index_number(frame))
        if len(self.frames) == 0:
            self.total_frames_number = 0
        else:
            self.total_frames_number = self.get_frame_index_number(self.frames[-1])
        self.logger.info(f"Found {len(self.frames)} frames.")

        # Facebook
        self.access_token = access_token
        self.page_id = page_id
        self.graph = facebook.GraphAPI(access_token)
        self.logger.info(f"Initialized GraphAPI for Facebook. Page id is {self.page_id}.")

        # Mirroring
        self.mirroring_enabled = mirroring_enabled
        if self.mirroring_enabled:
            self.mirroring_ratio = mirroring_ratio
            self.mirror_photos_album_id = mirror_photos_album_id
            self.logger.info(f"Random mirroring is enabled with ratio {self.mirroring_ratio}. Mirrored frames will be "
                             f"posted to the album with id {self.mirror_photos_album_id}.")

        # Best of reposting
        self.best_of_reposting_enabled = best_of_reposting_enabled
        if self.best_of_reposting_enabled:
            self.best_of_reactions_threshold = best_of_reactions_threshold
            self.best_of_wait_hours = best_of_wait_hours
            self.best_of_album_id = best_of_album_id
            self.best_of_local_dir = os.path.join("albums", "".join(
                x for x in f"Bestof_{self.movie_title.replace(os.path.sep, '-').replace(' ', '_')}" if
                (x.isalnum()) or x in "._- "))
            self.logger.info(f"Best of reposting is enabled with threshold {self.best_of_reactions_threshold} and "
                             f"{self.best_of_wait_hours} wait hours.")
            self.logger.info(f"Best ofs will be saved locally in the directory '{self.best_of_local_dir}' and "
                             f"reuploaded in the album with id {self.best_of_album_id}.")
            os.makedirs(self.best_of_local_dir, exist_ok=True)
            self.best_of_to_check_file = best_of_to_check_file
            if os.path.exists(self.best_of_to_check_file):
                self.logger.info(f"Found existing {self.best_of_to_check_file} files for best of checks, "
                                 f"trying to load it...")
                with open(best_of_to_check_file) as f:
                    self.best_of_to_check = json.load(f)
            else:
                self.best_of_to_check = {"list": []}

        # Last frame uploaded or fresh start
        if os.path.exists(LAST_FRAME_UPLOADED_FILE):
            with open(LAST_FRAME_UPLOADED_FILE) as f:
                self.last_frame_uploaded = int(f.read())
                self.logger.info(f"Last frame uploaded is {self.last_frame_uploaded}.")
        else:
            self.logger.info(f"Starting the bot from the first frame.")
            self.last_frame_uploaded = -1

        self.logger.info("Done initializing.")

    def upload_photo(self, image: Union[str, BytesIO], message: str, album: str = None) -> str:
        """
        Uploads a photo to a specific album, or to the news feed if no album id is specified.
        :param image: The image to be posted. Could be a path to an image file or a BytesIO object containing the image
        data
        :param message: The message used as image description
        :param album: The album where to post the image
        :return the resulting post id
        """
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
                self.logger.warning("Exception occurred during photo upload.", exc_info=True)
                if retry_count < 5:
                    self.logger.warning("Retrying photo upload...")
                    time.sleep(60 * 30 if "spam" in str(e) else 180)
                else:
                    self.logger.error("Unable to post even after several retries. Check what's happening. Bot is"
                                      " shutting down.")
                    exit()
                retry_count += 1
        return page_post_id

    def post_mirror_frame(self, image_path: str, og_message: str) -> str:
        """
        Mirrors a frame and posts it.
        :param image_path: Path to the image to be mirrored
        :param og_message: Message of the original post
        :return the posted photo id
        """
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
        return self.upload_photo(image_file, message, self.mirror_photos_album_id)

    def get_frame_index_number(self, file_name: str) -> int:
        """
        Using the frame naming regexp, extracts the frame number from the filename.
        :param file_name: The filename of the frame file.
        :return: The frame number
        """
        return int(self.frames_naming.search(file_name).group(1))

    def get_default_message(self, frame_number: int) -> str:
        """
        Generates the default message for a post
        :param frame_number: the index number of the frame
        :return: the post message
        """
        return f"{self.movie_title}\nFrame {frame_number} of {self.total_frames_number}"

    def advance_bests(self) -> None:
        """
        Checks if there are frames to repost into the best-of album, and posts those if there are.
        """
        self.logger.info(f"Checking for best of reuploading...")
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
                    self.logger.info(f"Checking entry {frame_to_check}...")
                    page_story_id = self.graph.get_object(frame_to_check["post_id"], fields="page_story_id")[
                        "page_story_id"]
                    reactions = \
                        self.graph.get_object(id=page_story_id, fields="reactions.summary(total_count)")["reactions"][
                            "summary"]["total_count"]
                    if reactions > self.best_of_reactions_threshold:
                        self.logger.info(f"Uploading frame {frame_to_check['path']} to best of album...")
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
                        else:
                            self.logger.info(f"File {frame_to_check['path']} is missing. Skipping uploading to best "
                                             f"of album...")
                    if self.delete_files:
                        os.remove(frame_to_check["path"])
                    self.best_of_to_check["list"].pop(0)
                    utils.safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
                    modified = True
        except Exception as e:
            self.logger.warning("There was a problem during the check of best-ofs", exc_info=True)
        finally:
            if modified:
                utils.safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
        self.logger.info("Done checking for best-ofs.")

    def start_upload(self) -> None:
        """
        Starts the framebot upload loop.
        """
        for frame in self.frames:
            frame_number = self.get_frame_index_number(frame)
            if frame_number <= self.last_frame_uploaded:
                continue

            if self.best_of_reposting_enabled:
                self.advance_bests()

            self.logger.info(f"Uploading frame {frame_number} of {self.total_frames_number}...")

            message = self.get_default_message(frame_number)
            post_id = self.upload_photo(frame, message)

            with open(LAST_FRAME_UPLOADED_FILE, "w") as f:
                self.last_frame_uploaded = frame_number
                f.write(str(frame_number))

            if self.best_of_reposting_enabled:
                self.logger.info(f"Queueing frame {frame_number} for best of checking...")
                self.best_of_to_check["list"].append(
                    {"time": str(datetime.now()), "post_id": post_id, "path": frame,
                     "album_id": self.best_of_album_id, "frame_number": frame_number})
                utils.safe_json_dump(self.best_of_to_check_file, self.best_of_to_check)
            if self.mirroring_enabled and random() > (1 - self.mirroring_ratio / 100):
                self.logger.info("Posting mirrored frame...")
                self.post_mirror_frame(frame, message)
            self.logger.info(f"Uploaded. Waiting {self.upload_interval} seconds before the next one...")
            if self.delete_files and not self.best_of_reposting_enabled:
                os.remove(frame)
            time.sleep(self.upload_interval)

        if self.best_of_reposting_enabled:
            self.best_of_wait_hours = self.best_of_wait_hours // 2
            while self.best_of_to_check['list']:
                self.advance_bests()
                if self.best_of_to_check['list']:
                    self.logger.info(
                        f"There are still {len(self.best_of_to_check['list'])} frames to check for best of. Sleeping "
                        f"for one hour...")
                    time.sleep(3600)
        if os.path.exists(LAST_FRAME_UPLOADED_FILE):
            os.remove(LAST_FRAME_UPLOADED_FILE)
