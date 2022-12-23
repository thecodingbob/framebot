import os
import re
import time
from glob import glob
from io import BytesIO
from random import random
from typing import List

from PIL import Image, ImageOps

import utils
from model import FacebookFrame
from social import FacebookHelper

LAST_FRAME_UPLOADED_FILE = "last_frame_uploaded"


def get_filename(full_path: str):
    return full_path[full_path.rfind(os.path.sep) + 1:]


# placeholder
class Framebot(object):
    pass


class SingleVideoFrameBot(Framebot):
    def __init__(self, facebook_helper: FacebookHelper, video_title: str, mirroring_enabled: bool = False,
                 mirror_photos_album_id: str = None, mirroring_ratio: float = 0.5,
                 frames_directory: str = "frames", frames_ext: str = "jpg", frames_naming: str = "$N$",
                 upload_interval: int = 150, bot_name: str = "Bot", delete_files: bool = False):
        """"
        :param video_title: Title of the movie/episode/whatever you want to post. Will be showed in the posts
            description
        :param mirroring_enabled: If the random mirroring of the images is enabled or not
        :param mirror_photos_album_id: Id of the album where the mirrored photos will be posted
        :param mirroring_ratio: Percentage of frames that will get mirroring
        :param frames_directory: Directory where the frame files are stored
        :param frames_ext: Extension of the frame files
        :param frames_naming: Naming pattern of the frame files e.g frame$N$
        :param upload_interval: time interval between one frame and the other, in seconds
        :param bot_name: bot's name, currently used only in the mirrored posts
        :param delete_files: if this flag is enabled, the frame files will be deleted after those served their purpose
        """
        self.logger = utils.get_logger(type(self).__name__)
        self.facebook_helper = facebook_helper
        # Bot base settings
        self.bot_name = bot_name
        self.logger.info(f"Starting bot '{self.bot_name}'.")
        self.video_title = video_title
        self.logger.info(f"Movie/video title is '{self.video_title}'.")
        self.upload_interval = upload_interval
        self.logger.info(f"A frame will be posted every {self.upload_interval} seconds.")
        self.delete_files = delete_files
        self.logger.info(f"Frames will be deleted after posting and after the best-of checking is done (if enabled).")
        self.frames_directory = frames_directory
        self.frames_ext = frames_ext
        expr = "^" + frames_directory + "\\" + os.path.sep + frames_naming.replace("$N$", "(\\d+)")
        expr += "\\." + self.frames_ext + "$"
        self.frames_naming = re.compile(expr)
        self.logger.info(f"Frames will be picked from the directory '{self.frames_directory}'. Will search for "
                         f".{frames_ext} files with naming pattern {frames_naming}.")
        self.frames: List[FacebookFrame] = [
            FacebookFrame(self.get_frame_index_number(frame_path), frame_path)
            for frame_path in glob(os.path.join(frames_directory, f"*.{self.frames_ext}"))
        ]
        self.frames.sort(key=lambda frame: frame.number)
        if len(self.frames) == 0:
            self.total_frames_number = 0
        else:
            self.total_frames_number = self.frames[-1].number
        self.logger.info(f"Found {len(self.frames)} frames.")

        # Mirroring
        self.mirroring_enabled = mirroring_enabled
        if self.mirroring_enabled:
            self.mirroring_ratio = mirroring_ratio
            self.mirror_photos_album_id = mirror_photos_album_id
            self.logger.info(f"Random mirroring is enabled with ratio {self.mirroring_ratio}. Mirrored frames will be "
                             f"posted to the album with id {self.mirror_photos_album_id}.")

        # Last frame uploaded or fresh start
        if os.path.exists(LAST_FRAME_UPLOADED_FILE):
            with open(LAST_FRAME_UPLOADED_FILE) as f:
                self.last_frame_uploaded = int(f.read())
                self.logger.info(f"Last frame uploaded is {self.last_frame_uploaded}.")
        else:
            self.logger.info(f"Starting the bot from the first frame.")
            self.last_frame_uploaded = -1

        self.logger.info("Done initializing.")

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
        return self.facebook_helper.upload_photo(image_file, message, self.mirror_photos_album_id)

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
        return f"{self.video_title}\nFrame {frame_number} of {self.total_frames_number}"

    def start_upload(self) -> None:
        """
        Starts the framebot upload loop.
        """
        for frame in self.frames:
            if frame.number <= self.last_frame_uploaded.number:
                continue

            # advance bests

            self.logger.info(f"Uploading frame {frame.number} of {self.total_frames_number}...")

            frame.message = self.get_default_message(frame.number)
            frame.mark_as_posted(self.facebook_helper.upload_photo(frame.local_file, frame.message))

            with open(LAST_FRAME_UPLOADED_FILE, "w") as f:
                self.last_frame_uploaded = frame
                f.write(str(frame.number))

            # queue best of
            if self.mirroring_enabled and random() > (1 - self.mirroring_ratio / 100):
                self.logger.info("Posting mirrored frame...")
                self.post_mirror_frame(frame.local_file, frame.message)
            self.logger.info(f"Uploaded. Waiting {self.upload_interval} seconds before the next one...")
            if self.delete_files:
                os.remove(frame.local_file)
            time.sleep(self.upload_interval)

        # finish uploading best ofs
        if os.path.exists(LAST_FRAME_UPLOADED_FILE):
            os.remove(LAST_FRAME_UPLOADED_FILE)
