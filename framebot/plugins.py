from __future__ import annotations

import copy
import shutil
import time
from datetime import timedelta, datetime
from typing import List, Type

import utils
from framebots import Framebot
from pathlib import Path
import os

from model import Frame, FacebookFrame
from social import FacebookHelper


class FrameBotPlugin(utils.LoggingObject):

    def __init__(self, framebot: Framebot, depends_on: List[Type[FrameBotPlugin]] = None):
        super().__init__()
        self.logger.info(f"Initializing plugin {type(self).__name__}")
        if depends_on is None:
            depends_on = []
        self.depends_on: List[Type[FrameBotPlugin]] = depends_on
        self.framebot: Framebot = framebot

    def before_upload_loop(self) -> None:
        pass

    def after_upload_loop(self) -> None:
        pass

    def before_frame_upload(self, frame: Frame) -> None:
        pass

    def after_frame_upload(self, frame: FacebookFrame) -> None:
        pass


class BestOfReposter(FrameBotPlugin):

    def __init__(self, framebot: Framebot, facebook_helper: FacebookHelper, album_id: str,
                 video_title: str, reactions_threshold: int = 50,
                 time_threshold: timedelta = timedelta(days=1),
                 local_directory: Path = Path("plugins").joinpath("bof_reposter"),
                 yet_to_check_file: str = "bofc.json",
                 store_best_ofs: bool = True):
        super().__init__(framebot)
        self.facebook_helper: FacebookHelper = facebook_helper
        self.album_id: str = album_id
        self.video_title: str = video_title
        self.reactions_threshold: int = reactions_threshold
        self.time_threshold: timedelta = time_threshold
        self.local_directory: Path = local_directory
        self.yet_to_check_file: Path = self.local_directory.joinpath(yet_to_check_file)
        self.yet_to_check: List[FacebookFrame] = []
        normalized_video_title = "".join(
            x for x in f"Bestof_{self.video_title.replace(os.path.sep, '-').replace(' ', '_')}" if
            (x.isalnum()) or x in "._- ")
        self.album_path: Path = self.local_directory.joinpath("albums").joinpath(normalized_video_title)
        self.frames_dir: Path = self.local_directory.joinpath("frames_to_check").joinpath(normalized_video_title)
        self.store_best_ofs: bool = store_best_ofs

        self.logger.info(f"Best of reposting is enabled with threshold {self.reactions_threshold} and "
                         f"{self.time_threshold} time threshold.")
        self.logger.info(f"Best ofs will be saved locally in the directory '{self.album_path}' and "
                         f"reuploaded in the album with id {self.album_id}.")
        os.makedirs(self.local_directory, exist_ok=True)
        os.makedirs(self.album_path, exist_ok=True)
        os.makedirs(self.frames_dir, exist_ok=True)

    def _check_for_existing_status(self) -> None:
        if os.path.exists(self.yet_to_check_file):
            self.logger.info(f"Found existing {self.yet_to_check_file} file for best of checks, "
                             f"trying to load it...")
            self.yet_to_check = utils.load_obj_from_json_file(self.yet_to_check_file)

    def _advance_bests(self) -> None:
        """
        Checks if there are frames to repost into the best-of album, and posts those if there are.
        """
        self.logger.info(f"Checking for best of reuploading...")
        checked_all = False
        modified = False
        try:
            while (not checked_all) and len(self.yet_to_check) > 0:
                frame_to_check = self.yet_to_check[0]
                timestamp = frame_to_check.post_time
                elapsed_time = datetime.now() - timestamp
                if elapsed_time < self.time_threshold:
                    checked_all = True
                else:
                    self.logger.info(f"Checking entry {frame_to_check}...")
                    frame_to_check.story_id = self.facebook_helper.get_story_id(frame_to_check.post_id)
                    frame_to_check.reactions = self.facebook_helper.get_reactions(frame_to_check.story_id)
                    if frame_to_check.reactions > self.reactions_threshold:
                        self.logger.info(f"Uploading frame {frame_to_check.local_file} to best of album...")
                        message = f"Reactions after {elapsed_time.total_seconds() // 3600} hours : " \
                                  f"{frame_to_check.reactions}.\n" + \
                                  f"Original post: {frame_to_check.url}\n\n" + \
                                  self.get_default_message(frame_to_check.number)
                        if os.path.exists(frame_to_check.local_file):
                            self.facebook_helper.upload_photo(frame_to_check.local_file, message, self.album_id)
                            shutil.copyfile(frame_to_check.local_file,
                                            os.path.join(self.album_path,
                                                         f"Frame {frame_to_check.number } "
                                                         f"id {frame_to_check.story_id} "
                                                         f"reactions {frame_to_check.reactions}"))
                        else:
                            self.logger.info(f"File {frame_to_check.local_file} is missing. Skipping uploading to best "
                                             f"of album...")
                    else:
                        os.remove(frame_to_check.local_file)
                    self.yet_to_check.pop(0)
                    utils.safe_json_dump(self.yet_to_check_file, self.yet_to_check)
                    modified = True
        except Exception as e:
            self.logger.warning("There was a problem during the check of best-ofs", exc_info=True)
        finally:
            if modified:
                utils.safe_json_dump(self.yet_to_check_file, self.yet_to_check)
        self.logger.info("Done checking for best-ofs.")

    def _queue_frame_for_check(self, frame: FacebookFrame) -> None:
        self.logger.info(f"Queueing frame {frame.number} for best of checking...")
        # copy frame to temp dir
        frame = copy.copy(frame)
        new_file_path = self.frames_dir.joinpath(frame.local_file.name)
        shutil.copyfile(frame.local_file, new_file_path)
        frame.local_file = new_file_path
        self.yet_to_check.append(frame)
        utils.safe_json_dump(self.yet_to_check_file, self.yet_to_check)

    def _handle_quicker(self) -> None:
        self.time_threshold /= 2
        while self.yet_to_check:
            self._advance_bests()
            if self.yet_to_check:
                self.logger.info(
                    f"There are still {len(self.yet_to_check)} frames to check for best of reuploading. "
                    f"Sleeping for one hour...")
                time.sleep(timedelta(hours=1).total_seconds())

    def before_upload_loop(self) -> None:
        self._check_for_existing_status()

    def before_frame_upload(self, frame: Frame) -> None:
        self._advance_bests()

    def after_frame_upload(self, frame: FacebookFrame) -> None:
        self._queue_frame_for_check(frame)

    def after_upload_loop(self) -> None:
        self._handle_quicker()
