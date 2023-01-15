import argparse
import configparser
import os
import platform
import shutil
import sys
from datetime import timedelta
from importlib import resources
from pathlib import Path
from typing import List

from .framebots import SimpleFrameBot
from .plugins import BestOfReposter, MirroredFramePoster, FrameBotPlugin, AlternateFrameCommentPoster
from .social import FacebookHelper
from .utils import get_logger

logger = get_logger("main")


def _init_best_of_reposter(config: configparser.ConfigParser, facebook_helper: FacebookHelper,
                           movie_title: str, working_dir: Path, plugins: List[FrameBotPlugin]) -> None:
    if config.has_section("best_of_album_uploader"):
        bof_uploader_settings = config["best_of_album_uploader"]
        best_of_reposting_enabled = bof_uploader_settings.getboolean("enabled")
        if best_of_reposting_enabled:
            reactions_threshold = bof_uploader_settings.getint("reactions_threshold")
            wait_hours = bof_uploader_settings.getint("wait_hours")
            best_of_album_id = bof_uploader_settings.get("best_of_album_id")
            plugins.append(BestOfReposter(
                album_id=best_of_album_id, facebook_helper=facebook_helper, video_title=movie_title,
                reactions_threshold=reactions_threshold, time_threshold=timedelta(hours=wait_hours),
                working_dir=working_dir)
            )


def _init_mirrored_frame_poster(config: configparser.ConfigParser, facebook_helper: FacebookHelper,
                                bot_name: str, plugins: List[FrameBotPlugin]) -> None:
    if config.has_section("mirroring"):
        mirroring_settings = config["mirroring"]
        mirroring_enabled = mirroring_settings.getboolean("enabled")
        if mirroring_enabled:
            mirroring_ratio = mirroring_settings.getfloat("ratio")
            mirror_album_id = mirroring_settings["mirror_album_id"]
            plugins.append(
                MirroredFramePoster(album_id=mirror_album_id, facebook_helper=facebook_helper,
                                    bot_name=bot_name, ratio=mirroring_ratio)
            )


def _init_config_parser(config_directory: Path) -> configparser.ConfigParser:
    config_path = config_directory.joinpath("config.ini")

    if not config_path.exists():
        logger.warning(f"No 'config.ini' file found in the provided directory: {config_directory}.")
        logger.info("Would you like to generate a config.ini file in the provided location? (yes/no)")
        user_input = input()

        yes_choices = ['yes', 'y']

        if user_input.lower() in yes_choices:
            logger.info(f"Generating config.ini file in {config_directory}...")
            shutil.copy(resources.files("framebot.resources").joinpath("config.ini"), config_directory)
            logger.info("config.ini file generated. Please edit the configuration values according to your preferences"
                        " and then press any key.")
            input()
        else:
            logger.warning("The bot needs a configuration file in order to initialize. Please create or generate one in"
                           " your directory of choice.")
            exit()

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    return config


def _configure_window(movie_title: str) -> None:
    op_sys = platform.system()
    window_title = f"Framebot - {movie_title}"
    if op_sys == "Windows":
        os.system(f"title {window_title}")
    elif op_sys == "Linux":
        sys.stdout.write(f"\x1b]2;{window_title}\x07")


def _init_facebook_helper(config: configparser.ConfigParser) -> FacebookHelper:
    facebook_settings = config["facebook"]
    page_id = facebook_settings.get("page_id")
    access_token = facebook_settings.get("access_token")
    return FacebookHelper(access_token=access_token, page_id=page_id)


def _init_alternate_frame_poster(config: configparser.ConfigParser, facebook_helper: FacebookHelper,
                                 delete_files: bool, working_dir: Path, plugins: List[FrameBotPlugin], ) -> None:
    if config.has_section("alternate_frame_poster"):
        alternate_frame_poster_settings = config["alternate_frame_poster"]
        alternate_enabled = alternate_frame_poster_settings.getboolean("enabled")
        if alternate_enabled:
            alternate_directory = Path(alternate_frame_poster_settings.get("alternate_frames_directory"))
            if not alternate_directory.is_absolute():
                alternate_directory = working_dir.joinpath(alternate_directory).resolve()
            comment_text = alternate_frame_poster_settings.get("comment_text")
            plugins.append(
                AlternateFrameCommentPoster(alternate_frames_directory=alternate_directory,
                                            facebook_helper=facebook_helper, delete_files=delete_files,
                                            message_generator=comment_text)
            )


def main():
    parser = init_argparse()
    args = parser.parse_args()

    config_directory = args.directory

    config = _init_config_parser(config_directory)

    bot_settings = config["bot_settings"]
    upload_interval = timedelta(seconds=bot_settings.getint("upload_interval"))
    frames_directory = Path(bot_settings.get("frames_directory"))
    frames_ext = bot_settings.get("frames_ext")
    frames_naming = bot_settings.get("frames_naming")
    movie_title = bot_settings.get("movie_title")
    bot_name = bot_settings.get("bot_name")
    delete_files = bot_settings.getboolean("delete_files")

    _configure_window(movie_title)

    working_dir = Path(config_directory)
    if not frames_directory.is_absolute():
        frames_directory = working_dir.joinpath(frames_directory).resolve()
    facebook_helper = _init_facebook_helper(config)

    plugins = []

    _init_best_of_reposter(config, facebook_helper, movie_title, working_dir, plugins)
    _init_mirrored_frame_poster(config, facebook_helper, bot_name, plugins)
    _init_alternate_frame_poster(config, facebook_helper, delete_files, working_dir, plugins)

    bot = SimpleFrameBot(facebook_helper=facebook_helper, video_title=movie_title,
                         upload_interval=upload_interval, delete_files=delete_files, bot_name=bot_name,
                         frames_ext=frames_ext,
                         frames_directory=frames_directory, frames_naming=frames_naming, plugins=plugins,
                         working_dir=working_dir)
    bot.start()


def init_argparse() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        prog="Framebot",
        usage=f"framebot -d directory",
        description="Starts a framebot using configuration found inside a 'config.ini' present in the provided"
                    " directory."
    )
    arg_parser.add_argument("-d", "--directory", type=Path, metavar="Configuration directory",
                            help="Where the 'config.ini' file is stored.", required=True)
    return arg_parser


if __name__ == '__main__':
    main()
