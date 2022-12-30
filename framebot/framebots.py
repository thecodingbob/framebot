"""
Contains framebots implementations
"""
import os
import re
import time
from glob import glob
from typing import List

import utils
from model import FacebookFrame
from plugins import FrameBotPlugin
from social import FacebookHelper

LAST_FRAME_UPLOADED_FILE = "last_frame_uploaded"


def _remove_last_frame_uploaded_file():
    if os.path.exists(LAST_FRAME_UPLOADED_FILE):
        os.remove(LAST_FRAME_UPLOADED_FILE)


def get_filename(full_path: str):
    """

    :param full_path:
    :return:
    """
    return full_path[full_path.rfind(os.path.sep) + 1:]


# placeholder
class Framebot(utils.LoggingObject):
    """
    Placeholder class for later extension
    """
    pass


class SimpleFrameBot(Framebot):
    """
    Uploads frames from a fixed directory
    """
    def __init__(self, facebook_helper: FacebookHelper, video_title: str, frames_directory: str = "frames",
                 frames_ext: str = "jpg", frames_naming: str = "$N$", upload_interval: int = 150, bot_name: str = "Bot",
                 delete_files: bool = False, plugins: List[FrameBotPlugin] = None):
        """"
        :param facebook_helper: Helper to gather data and post it to Facebook
        :param video_title: Title of the movie/episode/whatever you want to post. Will be showed in the posts
            description
        :param frames_directory: Directory where the frame files are stored
        :param frames_ext: Extension of the frame files
        :param frames_naming: Naming pattern of the frame files e.g frame$N$
        :param upload_interval: time interval between one frame and the other, in seconds
        :param bot_name: bot's name, currently used only in the mirrored posts
        :param delete_files: if this flag is enabled, the frame files will be deleted after those served their purpose
        :param plugins: plugins to extend the bot's functionalities
        """
        super().__init__()
        self.facebook_helper = facebook_helper
        # Bot base settings
        self.bot_name = bot_name
        self.video_title = video_title
        self.upload_interval = upload_interval
        self.delete_files = delete_files
        self.frames_directory = frames_directory
        self.frames_ext = frames_ext
        expr = "^" + frames_directory + "\\" + os.path.sep + frames_naming.replace("$N$", "(\\d+)")
        expr += "\\." + self.frames_ext + "$"
        self.frames_naming = re.compile(expr)
        self.last_frame_uploaded: int = -1
        if plugins is None:
            plugins = []
        self.plugins: List[FrameBotPlugin] = plugins
        self._init_frames()
        self._init_status()

        self._log_parameters()
        self.logger.info("Done initializing.")

    def _init_frames(self) -> None:
        """
        Initializes the frames list and total frames number
        """
        self.frames: List[FacebookFrame] = [
            FacebookFrame(self._get_frame_index_number(frame_path), frame_path, facebook_helper=self.facebook_helper)
            for frame_path in glob(os.path.join(self.frames_directory, f"*.{self.frames_ext}"))
        ]
        self.frames.sort(key=lambda frame: frame.number)
        if len(self.frames) == 0:
            self.total_frames_number = 0
        else:
            self.total_frames_number = self.frames[-1].number
        self.logger.info(f"Found {len(self.frames)} frames.")

    def _init_status(self) -> None:
        """
        Check if stored status exists and loads it
        """
        if os.path.exists(LAST_FRAME_UPLOADED_FILE):
            with open(LAST_FRAME_UPLOADED_FILE) as f:
                self.last_frame_uploaded = int(f.read())
                self.logger.info(f"Last frame uploaded is {self.last_frame_uploaded}.")
        else:
            self.logger.info(f"Starting the bot from the first frame.")

    def _log_parameters(self) -> None:
        """
        Logs the loaded bot parameters
        """
        self.logger.info(f"Starting bot '{self.bot_name}'.")
        self.logger.info(f"Movie/video title is '{self.video_title}'.")
        self.logger.info(f"A frame will be posted every {self.upload_interval} seconds.")
        self.logger.info(f"Frames will {'' if self.delete_files else 'not'} be deleted after posting.")
        self.logger.info(f"Frames will be picked from the directory '{self.frames_directory}'. Will search for "
                         f".{self.frames_ext} files with naming pattern {self.frames_naming}.")
        plugin_names = [type(plugin).__name__ for plugin in self.plugins]
        self.logger.info(f"The following plugins are loaded: {plugin_names}")

    def _get_frame_index_number(self, file_name: str) -> int:
        """
        Using the frame naming regexp, extracts the frame number from the filename.
        :param file_name: The filename of the frame file.
        :return: The frame number
        """
        return int(self.frames_naming.search(file_name).group(1))

    def _get_default_message(self, frame_number: int) -> str:
        """
        Generates the default message for a post
        :param frame_number: the index number of the frame
        :return: the post message
        """
        return f"{self.video_title}\nFrame {frame_number} of {self.total_frames_number}"

    def _update_last_frame_uploaded(self, number: int) -> None:
        """
        Stores the last uploaded frame number into a file for later resuming
        :param number: the latest frame uploaded's index number
        """
        with open(LAST_FRAME_UPLOADED_FILE, "w") as f:
            self.last_frame_uploaded = number
            f.write(str(number))

    def start(self) -> None:
        """
        Starts the framebot.
        """
        for plugin in self.plugins:
            plugin.before_upload_loop()
        self._upload_loop()
        for plugin in self.plugins:
            plugin.after_upload_loop()
        _remove_last_frame_uploaded_file()

    def _upload_loop(self) -> None:
        """
        The frame upload loop
        """
        for frame in self.frames:
            if frame.number <= self.last_frame_uploaded:
                continue
            for plugin in self.plugins:
                plugin.before_frame_upload(frame)
            self._upload_frame(frame)
            self.logger.info(f"Uploaded. Waiting {self.upload_interval} seconds before the next one...")
            for plugin in self.plugins:
                plugin.after_frame_upload(frame)
            if self.delete_files:
                os.remove(frame.local_file)
            time.sleep(self.upload_interval)

    def _upload_frame(self, frame: FacebookFrame) -> None:
        """
        Uploads a single frame
        :param frame: the frame to be uploaded
        """
        self.logger.info(f"Uploading frame {frame.number} of {self.total_frames_number}...")

        frame.message = self._get_default_message(frame.number)
        frame.mark_as_posted(self.facebook_helper.upload_photo(frame.local_file, frame.message))

        self._update_last_frame_uploaded(frame.number)
