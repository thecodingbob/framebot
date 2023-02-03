"""
Contains framebots implementations
"""
import datetime
import os
import re
import time
from datetime import timedelta, datetime
from pathlib import Path
from re import Pattern
from typing import List, Union

from . import utils, DEFAULT_WORKING_DIR
from .model import FacebookFrame
from .plugins import FrameBotPlugin
from .social import FacebookHelper

LAST_FRAME_UPLOADED_FILE = "last_frame_uploaded"


def _get_filename(full_path: Union[str, Path]):
    """

    :param full_path:
    :return:
    """
    if issubclass(type(full_path), Path):
        full_path = str(full_path)
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

    def __init__(self, facebook_helper: FacebookHelper, video_title: str, frames_directory: Union[str, Path] = "frames",
                 frames_ext: str = "jpg", frames_naming: str = "$N$",
                 upload_interval: timedelta = timedelta(seconds=150), bot_name: str = "Bot",
                 delete_files: bool = False, plugins: List[FrameBotPlugin] = None,
                 working_dir: Union[Path, str] = DEFAULT_WORKING_DIR):
        """"
        :param facebook_helper: Helper to gather data and post it to Facebook
        :param video_title: Title of the movie/episode/whatever you want to post. Will be showed in the posts
            description
        :param frames_directory: Directory where the frame files are stored
        :param frames_ext: Extension of the frame files
        :param frames_naming: Naming pattern of the frame files e.g. frame$N$
        :param upload_interval: time interval between one frame and the other
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
        self.frames_directory = (frames_directory if type(frames_directory) is Path else Path(frames_directory))\
            .resolve(strict=True)
        self.frames_ext = frames_ext
        self.frames_naming = frames_naming
        self.working_dir = working_dir.resolve(strict=False)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.last_frame_uploaded_file = self.working_dir.joinpath(LAST_FRAME_UPLOADED_FILE)
        if plugins is None:
            plugins = []
        self.plugins: List[FrameBotPlugin] = plugins
        self._init_status()
        self._init_frames()

        self._log_parameters()
        self.logger.info("Done initializing.")

    @property
    def frames_naming(self) -> Pattern:
        return self._frames_naming

    @frames_naming.setter
    def frames_naming(self, naming_str: str) -> None:
        if "$N$" not in naming_str:
            raise ValueError("Frames naming must contain the $N$ placeholder to determine where the frame number"
                             " should be extracted from.")
        naming_str = naming_str.replace("$N$", "(\\d+)")
        expr = f"^{naming_str}\\.{self.frames_ext}$"
        self._frames_naming = re.compile(expr)

    def _init_frames(self) -> None:
        """
        Initializes the frames list and total frames number
        """
        self.frames: List[FacebookFrame] = []
        for frame_path in self.frames_directory.glob(f"*.{self.frames_ext}"):
            try:
                index_number = self._get_frame_index_number(frame_path)
                if index_number > self.last_frame_uploaded:
                    self.frames.append(FacebookFrame(index_number, frame_path.resolve(strict=True)))
            except AttributeError:
                # doesn't match the regex: not a valid frame
                self.logger.warning(f"File {frame_path} doesn't match the naming regex {self._frames_naming}. Bot will"
                                    f" not load it as a frame.")
        self.frames.sort(key=lambda frame: frame.number)
        if len(self.frames) == 0:
            self.total_frames_number = 0
        else:
            self.total_frames_number = self.frames[-1].number
        self.logger.info(f"Found {len(self.frames)} yet to upload frames.")

    def _init_status(self) -> None:
        """
        Check if stored status exists and loads it
        """
        if self.last_frame_uploaded_file.exists():
            with open(self.last_frame_uploaded_file) as f:
                self.last_frame_uploaded = int(f.read())
                self.logger.info(f"Last frame uploaded is {self.last_frame_uploaded}.")
        else:
            self.last_frame_uploaded = -1
            self.logger.info(f"Starting the bot for the first frame.")

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

    def _get_frame_index_number(self, file_path: Union[Path, str]) -> int:
        """
        Using the frame naming regexp, extracts the frame number from the filename
        :param file_path: The path of the frame file
        :return: The frame number
        """
        return int(self.frames_naming.search(_get_filename(file_path)).group(1))

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
        with open(self.last_frame_uploaded_file, "w") as f:
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
        self.last_frame_uploaded_file.unlink()

    def _upload_loop(self) -> None:
        """
        The frame upload loop
        """
        self.logger.info("Starting upload loop.")
        for frame in self.frames:
            for plugin in self.plugins:
                plugin.before_frame_upload(frame)
            self._upload_frame(frame)
            for plugin in self.plugins:
                plugin.after_frame_upload(frame)
            if self.delete_files:
                os.remove(frame.local_file)
            if not (frame.number == self.total_frames_number):
                adjusted_pause = self._determine_adjusted_pause(frame)
                self.logger.info(f"Uploaded. Waiting {adjusted_pause} seconds before the next one...")
                time.sleep(adjusted_pause.total_seconds())
        self.logger.info("Upload loop over.")

    def _determine_adjusted_pause(self, last_posted_frame: FacebookFrame) -> timedelta:
        """
        Determines how long the bot should wait before posting the next frame, in order to be more regular
        with the expected post interval.
        :param last_posted_frame: the last posted frame
        :return: the adjusted pause
        """
        wanted_post_time = last_posted_frame.post_time + self.upload_interval
        now = datetime.now()
        if wanted_post_time <= now:
            return timedelta(seconds=0)
        return wanted_post_time - now

    def _upload_frame(self, frame: FacebookFrame) -> None:
        """
        Uploads a single frame
        :param frame: the frame to be uploaded
        """
        self.logger.info(f"Uploading frame {frame.number} of {self.total_frames_number}...")

        frame.text = self._get_default_message(frame.number)
        response = self.facebook_helper.post_photo(frame.local_file, frame.text)

        frame.photo_id = response.photo_id
        frame.post_id = response.post_id
        frame.url = f"https://facebook.com/{frame.photo_id}"
        frame.post_time = datetime.now()

        self._update_last_frame_uploaded(frame.number)
