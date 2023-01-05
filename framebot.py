import configparser
import os
import platform
import sys
from datetime import timedelta
from os.path import dirname
from pathlib import Path

from framebot.framebots import SimpleFrameBot
from plugins import BestOfReposter, MirroredFramePoster
from social import FacebookHelper

config_path = Path("config.ini")

config = configparser.ConfigParser()
config.read(config_path, encoding='utf-8')

upload_interval = config.getint("bot_settings", "upload_interval")
frames_directory = config["bot_settings"]["frames_directory"]
frames_ext = config["bot_settings"]["frames_ext"]
frames_naming = config["bot_settings"]["frames_naming"]

reactions_threshold = config.getint("best_of_album_uploader", "reactions_threshold")
wait_hours = config.getint("best_of_album_uploader", "wait_hours")

page_id = config["facebook"]["page_id"]
if page_id == "":
    page_id = input("Insert page id:")
    config["facebook"]["page_id"] = page_id
    with open(config_path, "w") as cfg:
        config.write(cfg)
access_token = config["facebook"]["access_token"]
if access_token == "":
    access_token = input("Insert access token:")
    config["facebook"]["access_token"] = access_token
    with open(config_path, "w") as cfg:
        config.write(cfg)
movie_title = config["bot_settings"]["movie_title"]
if access_token == "":
    movie_title = input("Insert movie title:")
    config["bot_settings"]["movie_title"] = access_token
    with open(config_path, "w") as cfg:
        config.write(cfg)

best_of_reposting_enabled = config.getboolean("best_of_album_uploader", "enabled")
best_of_album_id = config["best_of_album_uploader"]["best_of_album_id"]
mirroring_enabled = config.getboolean("mirroring", "enabled")
mirroring_ratio = config.getfloat("mirroring", "ratio")
mirror_album_id = config["mirroring"]["mirror_album_id"]
best_of_check_file = config["best_of_album_uploader"]["local_file"]
bot_name = config["bot_settings"]["bot_name"]
delete_files = config.getboolean("bot_settings", "delete_files")

op_sys = platform.system()
window_title = f"Framebot - {movie_title}"
if op_sys == "Windows":
    os.system(f"title {window_title}")
elif op_sys == "Linux":
    sys.stdout.write(f"\x1b]2;{window_title}\x07")

enabled_string = f'enabled with threshold {reactions_threshold} and {wait_hours} wait hours' \
    if mirroring_enabled else 'disabled'
print(
    f"Starting bot named {bot_name} for {movie_title}. Frames will be picked from directory {frames_directory} "
    f"with {frames_ext} extension."
    f"\nRandom mirroring is {('enabled with ratio ' + str(mirroring_ratio)) if mirroring_enabled else 'disabled'}."
    f"\nBest of reposting is "
    f"{enabled_string}."
    f"\nThe bot will try to post a frame every {upload_interval} seconds and will "
    f"{'' if delete_files else 'not '}delete those after it's done.\n")

working_dir = Path(dirname(config_path))
facebook_helper = FacebookHelper(access_token=access_token, page_id=page_id)

plugins = []
if best_of_reposting_enabled:
    plugins.append(BestOfReposter(
        album_id=best_of_album_id, facebook_helper=facebook_helper, video_title=movie_title,
        reactions_threshold=reactions_threshold, time_threshold=timedelta(hours=wait_hours),
        working_dir=working_dir)
    )
if mirroring_enabled:
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
