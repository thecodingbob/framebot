import argparse
import configparser
import os
import platform
import sys
from datetime import timedelta
from os.path import dirname
from pathlib import Path

from .framebots import SimpleFrameBot
from .plugins import BestOfReposter, MirroredFramePoster
from .social import FacebookHelper
from .utils import get_logger


def main():
    parser = init_argparse()
    args = parser.parse_args()

    config_directory = args.directory

    logger = get_logger("main")

    config_path = config_directory.joinpath("config.ini")

    if not config_path.exists():
        logger.error(f"No 'config.ini' file found in the provided directory: {config_directory}."
                     f" Unable to start the bot.")
        exit()

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    bot_settings = config["bot_settings"]
    upload_interval = timedelta(seconds=bot_settings.getint("upload_interval"))
    frames_directory = Path(bot_settings.get("frames_directory"))
    frames_ext = bot_settings.get("frames_ext")
    frames_naming = bot_settings.get("frames_naming")
    movie_title = bot_settings.get("movie_title")
    bot_name = bot_settings.get("bot_name")
    delete_files = bot_settings.getboolean("delete_files")

    facebook_settings = config["facebook"]
    page_id = facebook_settings.get("page_id")
    access_token = facebook_settings.get("access_token")

    op_sys = platform.system()
    window_title = f"Framebot - {movie_title}"
    if op_sys == "Windows":
        os.system(f"title {window_title}")
    elif op_sys == "Linux":
        sys.stdout.write(f"\x1b]2;{window_title}\x07")

    working_dir = Path(dirname(config_path))
    if not frames_directory.is_absolute():
        frames_directory = working_dir.joinpath(frames_directory).resolve()
    facebook_helper = FacebookHelper(access_token=access_token, page_id=page_id)

    plugins = []

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

    mirroring_settings = config["mirroring"]
    mirroring_enabled = mirroring_settings.getboolean("enabled")
    if mirroring_enabled:
        mirroring_ratio = config.getfloat("mirroring", "ratio")
        mirror_album_id = config["mirroring"]["mirror_album_id"]
        plugins.append(
            MirroredFramePoster(album_id=mirror_album_id, facebook_helper=facebook_helper,
                                bot_name=bot_name, ratio=mirroring_ratio, working_dir=working_dir)
        )

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
