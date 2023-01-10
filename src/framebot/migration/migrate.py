import datetime
import json
import os
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Union
from unittest.mock import Mock

from slugify import slugify

from ..model import FacebookFrame
from ..plugins import BestOfReposter
from ..utils import safe_json_dump
from ..framebots import LAST_FRAME_UPLOADED_FILE, SimpleFrameBot
from ..social import FacebookHelper


def _get_old_album_name(movie_title: str) -> str:
    return "".join(
        x for x in f"Bestof_{movie_title.replace(os.path.sep, '-').replace(' ', '_')}" if
        (x.isalnum()) or x in "._- ")


def backup_bof_reposter_stuff(source_dir: Union[Path, str]) -> None:
    target_backup_dir = Path(source_dir).joinpath("migration_backup")
    target_backup_dir.mkdir()
    shutil.copy(source_dir.joinpath("bofc.json"), target_backup_dir)
    shutil.copytree(source_dir.joinpath("albums"), target_backup_dir.joinpath("albums"))


def migrate_bofc_json(source_dir: Union[Path, str], target_dir: Union[Path, str], framebot: SimpleFrameBot) -> None:
    with open(source_dir.joinpath("bofc.json"), "r") as f:
        old_bofc = json.load(f)

    old_frames = old_bofc["list"]
    new_frames = []
    frames_to_check_path = target_dir.joinpath("frames_to_check")
    frames_to_check_path.mkdir()
    for frame in old_frames:
        frame_file_name = Path(frame["path"]).name
        new_frame_path = frames_to_check_path.joinpath(frame_file_name).resolve(strict=False)
        shutil.copy(source_dir.joinpath("frames").joinpath(frame_file_name), new_frame_path)
        new_frame = FacebookFrame(
            local_file=new_frame_path,
            number=frame["frame_number"]
        )
        new_frame.photo_id = frame["post_id"]
        new_frame.post_id = frame["post_id"]  # only valid during migration
        new_frame.url = f"https://facebook.com/{new_frame.photo_id}"
        new_frame.reactions_total = None
        new_frame.post_time = datetime.datetime.fromisoformat(frame["time"])
        new_frame.text = framebot._get_default_message(new_frame.number)
        new_frames.append(new_frame)
    safe_json_dump(target_dir.joinpath("bofc.json"), new_frames)


def _get_framebot(source_dir: Union[Path, str], config: ConfigParser) -> SimpleFrameBot:
    movie_title = config["bot_settings"]["movie_title"]
    frames_naming = config["bot_settings"]["frames_naming"]
    frames_ext = config["bot_settings"]["frames_ext"]
    framebot = SimpleFrameBot(video_title=movie_title, frames_naming=frames_naming, frames_ext=frames_ext,
                              facebook_helper=Mock(spec=FacebookHelper),
                              frames_directory=source_dir.joinpath("frames"),
                              working_dir=source_dir)
    assert framebot.total_frames_number > 0, "Framebot did not load the frames correctly!"
    return framebot


def migrate(source_dir: Union[Path, str], target_dir: Union[Path, str] = None):
    print(f"Migrating framebot configuration from {source_dir} to {target_dir}...")
    config_file = "config.ini"
    if target_dir is None:
        target_dir = source_dir
    source_dir = source_dir.absolute()
    target_dir = target_dir.absolute()
    if target_dir == source_dir:
        print("Backing up old files...")
        backup_bof_reposter_stuff(source_dir)
    else:
        old_frames_path = source_dir.joinpath("frames")
        new_frames_path = target_dir.joinpath("frames")

        print(f"Copying frames directory from {old_frames_path} to {new_frames_path}...")
        shutil.copytree(old_frames_path, new_frames_path)

        old_config_file = source_dir.joinpath(config_file)
        new_config_file = target_dir.joinpath(config_file)
        print(f"Copying config file from {old_config_file} to {new_config_file}...")
        shutil.copy(old_config_file, new_config_file)

        old_last_frame_uploaded_file = source_dir.joinpath(LAST_FRAME_UPLOADED_FILE)
        new_last_frame_uploaded_file = target_dir.joinpath(LAST_FRAME_UPLOADED_FILE)
        print(f"Copying config file from {old_last_frame_uploaded_file} to {new_last_frame_uploaded_file}...")
        shutil.copy(old_last_frame_uploaded_file, new_last_frame_uploaded_file)

    config = ConfigParser()
    config.read(source_dir.joinpath(config_file), encoding='utf-8')
    movie_title = config["bot_settings"]["movie_title"]
    framebot = _get_framebot(source_dir, config)

    old_album_path = source_dir.joinpath("albums").joinpath(_get_old_album_name(movie_title))
    plugins_dir = target_dir.joinpath("plugins")
    bof_reposter_dir = plugins_dir.joinpath(BestOfReposter.__name__).joinpath(slugify(f"Best of {movie_title}"))
    bof_reposter_dir.mkdir(parents=True)

    print("Migrating bofc.json file and yet to check frames...")
    migrate_bofc_json(source_dir, bof_reposter_dir, framebot)

    new_album_path = bof_reposter_dir.joinpath("album")
    print(f"Copying bof album directory from {old_album_path} to {new_album_path}...")
    shutil.copytree(old_album_path, new_album_path)

    print("Done.")
