"""
Contains implementations for framebot plugins
"""
from __future__ import annotations

import copy
import shutil
import time
import slugify
from datetime import timedelta, datetime
from random import random
from typing import List, Type, Dict, Union, Callable

from PIL import Image, ImageOps
from pyfacebook import FacebookError

from pathlib import Path
import os

from . import DEFAULT_WORKING_DIR
from . import utils
from .model import FacebookFrame
from .social import FacebookHelper


class FrameBotPlugin(utils.LoggingObject):
    """
    A plugin to inject custom extra behavior into a framebot. It has handles for before and after the upload loop
    and the single frame posting
    """

    def __init__(self, depends_on: List[Type[FrameBotPlugin]] = None):
        """
        Constructor
        :param depends_on: Signals this plugin depends on other plugins, and thus it cannot be used without these,
        and also must act after its dependencies. Behavior for this is yet to be implemented
        """
        super().__init__()
        self.logger.info(f"Initializing plugin {type(self).__name__}")
        if depends_on is None:
            depends_on = []
        self.depends_on: List[Type[FrameBotPlugin]] = depends_on
        self.dependencies: Dict[FrameBotPlugin] = {}

    def before_upload_loop(self) -> None:
        """
        Behavior to be executed before the upload loop starts.
        """
        self.logger.debug(f"No operation defined for 'before_upload_loop'")

    def after_upload_loop(self) -> None:
        """
        Behavior to be executed after the upload loop ends.
        """
        self.logger.debug(f"No operation defined for 'after_upload_loop'")

    def before_frame_upload(self, frame: FacebookFrame) -> None:
        """
        Behavior to be executed before a frame is uploaded
        :param frame: the frame to be uploaded
        """
        self.logger.debug(f"No operation defined for 'before_frame_upload'")

    def after_frame_upload(self, frame: FacebookFrame) -> None:
        """
        Behavior to be executed after a frame is uploaded
        :param frame: the uploaded frame
        """
        self.logger.debug(f"No operation defined for 'after_frame_upload'")


class FileWritingFrameBotPlugin(FrameBotPlugin):
    """
    A FrameBotPlugin that also needs to perform file writing operations within a working directory.
    """

    def __init__(self, depends_on: List[Type[FrameBotPlugin]] = None, working_dir: Path = None):
        """
        Constructor
        :param depends_on: Signals this plugin depends on other plugins, and thus it cannot be used without these,
        and also must act after its dependencies. Behavior for this is yet to be implemented
        :param working_dir: Local working directory for the plugin
        """
        super().__init__(depends_on=depends_on)
        if working_dir is None:
            working_dir = DEFAULT_WORKING_DIR
        self.working_dir: Path = working_dir.joinpath("plugins").joinpath(type(self).__name__).resolve(strict=False)
        os.makedirs(self.working_dir, exist_ok=True)


class BestOfReposter(FileWritingFrameBotPlugin):
    """
    Reposts frames that had a reaction count over a certain threshold, after a defined time threshold from the first
    post.
    """

    def __init__(self, facebook_helper: FacebookHelper, album_id: str,
                 video_title: str, reactions_threshold: int = 50,
                 time_threshold: timedelta = timedelta(days=1),
                 yet_to_check_file: str = "bofc.json",
                 store_best_ofs: bool = True, working_dir: Path = None):
        """
        Constructor
        :param facebook_helper: Helper to gather data and post it to Facebook
        :param album_id: Facebook album id where to repost best of frames
        :param video_title: Move/video title for the frames
        :param reactions_threshold: Threshold determining which frames should be reposted
        :param time_threshold: Time after which a frame's reactions count can be compared with the threshold and
        reposted
        :param yet_to_check_file: file where the queued frames data will be stored for later restarts
        :param store_best_ofs: determines if the best of frames should also be stored locally for later use
        """
        super().__init__(working_dir=working_dir)
        self.facebook_helper: FacebookHelper = facebook_helper
        self.album_id: str = album_id
        self.video_title: str = video_title
        self.reactions_threshold: int = reactions_threshold
        self.time_threshold: timedelta = time_threshold
        normalized_video_title = slugify.slugify(f"Best of {self.video_title}")
        self.working_dir = self.working_dir.joinpath(normalized_video_title)
        self.yet_to_check_file: Path = self.working_dir.joinpath(yet_to_check_file)
        self.yet_to_check: List[FacebookFrame] = []
        self.album_path: Path = self.working_dir.joinpath("album")
        self.frames_dir: Path = self.working_dir.joinpath("frames_to_check")
        self.store_best_ofs: bool = store_best_ofs

        self.logger.info(f"Best of reposting is enabled with a threshold of {self.reactions_threshold} reactions and "
                         f"a time threshold of {self.time_threshold}.")
        self.logger.info(f"Best ofs will be saved locally in the directory '{self.album_path}' and "
                         f"reuploaded in the album with id {self.album_id}.")
        os.makedirs(self.working_dir, exist_ok=True)
        os.makedirs(self.album_path, exist_ok=True)
        os.makedirs(self.frames_dir, exist_ok=True)

    def _check_for_existing_status(self) -> None:
        """
        Checks if a status file already exists in the local file system, and loads it if so.
        """
        if os.path.exists(self.yet_to_check_file):
            self.logger.info(f"Found existing {self.yet_to_check_file} file for best of checks, "
                             f"trying to load it...")
            self.yet_to_check: List[FacebookFrame] = utils.load_obj_from_json_file(self.yet_to_check_file)
            self.yet_to_check.sort(key=lambda yet_to_check_frame: yet_to_check_frame.post_time)

    def _advance_bests(self) -> None:
        """
        Checks if there are frames to repost into the best-of album, and posts them if so.
        """
        self.logger.info(f"Checking for best of reuploading...")
        try:
            while len(self.yet_to_check) > 0 and (self._check_and_post(self.yet_to_check[0])):
                self.yet_to_check.pop(0)
                utils.safe_json_dump(self.yet_to_check_file, self.yet_to_check)
        except FacebookError:
            self.logger.warning("There was a problem during the check of best-ofs", exc_info=True)
        self.logger.info("Done checking for best-ofs.")

    def _check_and_post(self, frame: FacebookFrame) -> bool:
        """
        Checks if the time threshold time has passed, then checks the reactions count against the threshold,
        and if so, reuploads the frame in the best-of album
        :param frame: the frame to be checked
        :return: True if the frame has been checked, False if it's still too early
        """
        elapsed_time = datetime.now() - frame.post_time
        if elapsed_time < self.time_threshold:
            return False
        self.logger.info(f"Checking entry {frame}...")
        if os.path.exists(frame.local_file):
            reactions_total = self.facebook_helper.get_reactions_total_count(frame.post_id)
            if reactions_total > self.reactions_threshold:
                self.logger.info(f"Uploading frame {frame.local_file} to best of album...")
                message = f"Reactions after {int(elapsed_time.total_seconds() / 3600)} hours : " \
                          f"{reactions_total}.\n" + \
                          f"Original post: {frame.url}\n\n" + \
                          frame.text
                self.facebook_helper.post_photo(frame.local_file, message, self.album_id)
                shutil.copyfile(frame.local_file,
                                os.path.join(self.album_path,
                                             f"Frame {frame.number} "
                                             f"post_id {frame.post_id} "
                                             f"photo_id {frame.photo_id} "
                                             f"reactions {reactions_total}.jpg"))
            os.remove(frame.local_file)
        else:
            self.logger.warning(f"File {frame.local_file} is missing. Skipping best of check...")
        return True

    def _queue_frame_for_check(self, frame: FacebookFrame) -> None:
        """
        Adds a frame data to the queue for later checking
        :param frame: the frame to be queued
        """
        self.logger.info(f"Queueing frame {frame.number} for best of checking...")
        # make shallow copy so no parameters from original are overwritten
        frame = copy.copy(frame)
        # copy frame to temp dir
        new_file_path = self.frames_dir.joinpath(frame.local_file.name).resolve(strict=False)
        shutil.copyfile(frame.local_file, new_file_path)
        frame.local_file = new_file_path
        self.yet_to_check.append(frame)
        utils.safe_json_dump(self.yet_to_check_file, self.yet_to_check)

    def _handle_quicker(self) -> None:
        """
        Halves the time threshold and starts a loop to check the remaining frames. Used after the framebot has
        finished posting.
        """
        self.time_threshold /= 2
        while len(self.yet_to_check) > 0:
            self._advance_bests()
            if len(self.yet_to_check) > 0:
                self.logger.info(
                    f"There are still {len(self.yet_to_check)} frames to check for best of reuploading. "
                    f"Sleeping for one hour...")
                time.sleep(timedelta(hours=1).total_seconds())

    def before_upload_loop(self) -> None:
        self._check_for_existing_status()

    def before_frame_upload(self, frame: FacebookFrame) -> None:
        self._advance_bests()

    def after_frame_upload(self, frame: FacebookFrame) -> None:
        self._queue_frame_for_check(frame)

    def after_upload_loop(self) -> None:
        self._handle_quicker()


class MirroredFramePoster(FrameBotPlugin):
    """
    Randomly mirrors and posts a frame with a random chance.
    """

    def __init__(self, facebook_helper: FacebookHelper, album_id: str, ratio: float = 0.5,
                 bot_name: str = "MirrorBot", mirror_original_message: bool = True,
                 extra_message: str = None):
        """
        Constructor
        :param facebook_helper: Helper to gather data and post it to Facebook
        :param album_id: The Facebook album where to post mirrored photos
        :param ratio: The percentage a frame has to be reposted mirrored
        :param bot_name: The bot's name. Used in the default extra message
        :param mirror_original_message: Also mirrors the original text message along with the image
        :param extra_message: Message to attach to the frame. Default adds the bot's name as a sort of signature
        """
        super().__init__()
        self.facebook_helper: FacebookHelper = facebook_helper
        self.album_id: str = album_id
        self.ratio: float = ratio
        self.bot_name: str = bot_name
        self.mirror_original_message: bool = mirror_original_message
        if extra_message is None:
            extra_message = f"Just a randomly mirrored image.\n-{self.bot_name}"
        self.extra_message = extra_message
        self.logger.info(f"Random mirroring is enabled with ratio {self.ratio}. Mirrored frames will be "
                         f"posted to the album with id {self.album_id}.")

    def _mirror_frame(self, frame: FacebookFrame) -> Image:
        """
        Mirrors a frame and returns it
        :param frame: Frame to be mirrored
        :return the mirrored frame
        """
        im = Image.open(frame.local_file)
        flipped_half = ImageOps.mirror(im.crop((0, 0, im.size[0] // 2, im.size[1])))
        im.paste(flipped_half, (im.size[0] // 2, 0))
        return im

    def _generate_message(self, frame: FacebookFrame) -> str:
        """
        Generates a message from the mirrored frame, depending on the bot settings
        :param frame: the frame to be mirrored
        :return: the generated message
        """
        lines = frame.text.split("\n")
        message = ""
        if self.mirror_original_message:
            message += "\n".join([line[:len(line) // 2] + line[len(line) // 2::-1] for line in lines])
        if self.extra_message != "":
            if self.mirror_original_message:
                message += "\n\n"
            message += self.extra_message
        return message

    def after_frame_upload(self, frame: FacebookFrame) -> None:
        if random() >= (1 - self.ratio / 100):
            self.logger.info("Posting mirrored frame...")
            mirrored_frame = self._mirror_frame(frame)
            frame_text = self._generate_message(frame)
            self.facebook_helper.post_photo(mirrored_frame, frame_text, self.album_id)


class AlternateFrameCommentPoster(FrameBotPlugin):
    """
    Plugin posting as a comment an alternate version of the same frame, taken from a given directory.
    The files in the alternate directory need to be named as the ones in the main frames directory.
    """

    def __init__(self, facebook_helper: FacebookHelper, alternate_frames_directory: Path, delete_files: bool = False,
                 message_generator: Union[str, Callable[[FacebookFrame], Union[str, None]]] = lambda frame: frame.text):
        """
        Constructor
        :param facebook_helper: facebook_helper: Helper to gather data and post it to Facebook
        :param alternate_frames_directory: the directory where the alternate frames are picked from
        :param delete_files: determines if the alternate frame files need to be deleted after the comment is posted
        :param message_generator: function used to generate the comment message, starting from the input frame, or
        static string to use as comment message
        """
        super().__init__()
        if not alternate_frames_directory.exists():
            raise ValueError(f"Can't initialize AlternateFrameCommentPoster plugin. Provided path for alternate frames"
                             f" doesn't exist: {alternate_frames_directory}")
        self.helper = facebook_helper
        self.frames_directory = alternate_frames_directory
        self.delete_files = delete_files
        self.message_generator = (lambda frame: message_generator) if type(message_generator) is str else \
            message_generator
        self.logger.info(f"Alternate frame posting is enabled. Will post alternate frames as post comments from the"
                         f" directory {self.frames_directory}. Alternate frames will"
                         f" {'' if self.delete_files else 'not'} be deleted.")

    def after_frame_upload(self, frame: FacebookFrame) -> None:
        alternate_frame_path = self.frames_directory.joinpath(frame.local_file.name)
        self.logger.info(f"Posting alternate frame from location {alternate_frame_path}...")
        if not alternate_frame_path.exists():
            raise FileNotFoundError(f"Alternate frame not found in path {alternate_frame_path}. Please check your"
                                    f" configuration and/or directories.")
        message = self.message_generator(frame)
        self.helper.post_comment(object_id=frame.photo_id, message=message, image=alternate_frame_path)
        if self.delete_files:
            alternate_frame_path.unlink()
