import configparser
import os
import platform
import sys

from framebot.framebot_core import FrameBot

config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

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

op_sys = platform.system()
window_title = f"Framebot - {movie_title}"
if op_sys == "Windows":
    os.system(f"title {window_title}")
elif op_sys == "Linux":
    sys.stdout.write(f"\x1b]2;{window_title}\x07")

print(f"Starting bot named {bot_name} for {movie_title}. Frames will be picked from directory {frames_directory} with "
      f"{frames_ext} extension."
      f"\nThe bot will try to post a frame every "
      f"{upload_interval} seconds and will {'' if delete_files else 'not '}delete those after it's done.\n")

mirroring_message = f"\nRandom mirroring is"
mirroring_message += f"{('enabled with ratio ' + str(mirroring_ratio)) if mirroring_enabled else 'disabled'}."
print(mirroring_message)

bestof_message = f"\nBest of reposting is "
if best_of_reposting_enabled:
    bestof_message += f"enabled with threshold {reactions_threshold} and {wait_hours} wait hours."
else:
    bestof_message += "disabled"
print(bestof_message)

bot = FrameBot(access_token=access_token, page_id=page_id, movie_title=movie_title,
               mirror_photos_album_id=mirror_album_id,
               best_of_reactions_threshold=reactions_threshold,
               best_of_wait_hours=wait_hours, best_of_to_check_file=best_of_check_file,
               upload_interval=upload_interval, best_of_album_id=best_of_album_id,
               mirroring_enabled=mirroring_enabled, best_of_reposting_enabled=best_of_reposting_enabled,
               mirroring_ratio=mirroring_ratio, delete_files=delete_files, bot_name=bot_name, frames_ext=frames_ext,
               frames_directory=frames_directory)

bot.start_upload()
