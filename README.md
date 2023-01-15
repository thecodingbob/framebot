# framebot
A Facebook framebot supporting the reupload of most reacted frames and random mirroring.

## Requirements
- Python >= 3.7: https://www.python.org/downloads/

## Installation
```
pip install pyframebot
```
If you're on Linux/Mac, depending on your configuration, you may have to use pip3 and sudo. 
## Update to the latest version
```
pip install --upgrade pyframebot
```
## Usage
- Create a page on Facebook
- Take note of your Page id. You can find it in the "about" section of your page
- Generate a Facebook app here: https://developers.facebook.com/apps
- Configure it to be able to post on behalf of your page (a more in depth guide may come in the future)
- Generate an access token for your page here: https://developers.facebook.com/tools/explorer/
- Copy the `config.ini` file (https://github.com/thecodingbob/framebot/blob/main/src/framebot/resources/config.ini) from this repo in the folder where you want to store your framebot configuration and data
- Paste the generated access token and the page id in the `config.ini` file 
- Configure the other options in the `config.ini` file as you like
- Put the frames you want to post in the `frames/` directory in the same parent directory where you put the configuration file (or change the folder name in the `config.ini` file and put the frames in the folder with that name)
- Open a powershell/bash/any shell you like window in the directory where you cloned this repository and run `framebot -d config_directory`, where `config_directory` is the directory where you stored the configuration files
## Configuration
You can change the bot's behavior editing the options in the `config.ini` file, which is divided in four sections:
- **facebook**
  - *page_id* - Your page's id. You can get it in the "about" section of the page or in the access token debugger.
  - *access_token* - The access token the bot needs to post on your page. See the Usage section.
- **bot_settings** 
  - *upload_interval* - Seconds the bot will wait in between frame postings. Change this to make the bot post more or less often. Don't set it too small, or you'll quickly end your API usages and end up blocked for hours.
  - *movie_title* - The title of the video/movie you want to show in each post.
  - *bot_name* - The bot's name. As now, it's only used when posting mirrored images. You can give it a funny name you like, or you can ignore him and just let it call himself "Bot".
  - *delete_files* - Set this to True if you want the bot to delete the frame files after they're not needed anymore. Can break the bot if you stop it while it's uploading files or checking for best-ofs.
  - *frames_directory* - The directory from where the bot pulls the frames
  - *frames_ext* - The file extension of the frame files
  - *frames_naming* - How your frames are named. Enter your naming pattern and use `$N$` to specify where the frame number is in the pattern. For example: `frame$N$` if your frames are named like `frame0001.jpg, frame0002.jpg`, etc.
- **best_of_album_uploader**
  - *enabled* - Set this to `True` if you want the bot to check the reactions your frames got after a fixed amount of time, and repost it on an album if those exceed a fixed the threshold. If you don't want this feature, set this option to False.
  - *best_of_album_id* - The id of the album where to repost the most reacted frames. You have to create this manually, since Facebook's API don't support programmatic album creation. You can find an album's id in the url: `https://www.facebook.com/media/set/?vanity=page&set=a.album_id`.
  - *reactions_threshold* - The threshold for reposting. Frames with more than that will be reposted. Set this according to the average reaction number you expect on popular frames.
  - *wait_hours* - Number of hours a frame is given to accumulate reactions, before it's checked for reposting.
- **mirroring**
  - *enabled* - Set this to `True` if you want your bot to randomly mirror an image at the horizontal center and repost it.
  - *mirror_album_id* - Same as *best_of_album_id*, but for mirrored photos. If you just want those pics to be uploaded in your page's timeline, set this to the same value as *page_id*.
  - *ratio* - Every frame will have a ratio% chance of being mirrored.
- **alternate_frame_poster**
  - *enabled* - Set this to `True` if you want your bot to post an alternate version of the same frame in the post's comments. This is useful, for example, if you want to also post the raw frame (i.e. the frame without subtitle)
  - *alternate_frames_directory* - Directory where to pick the alternate frames from. Be sure to use the same naming structure for the alternate frames.
  - *comment_text* - Message you want the bot to append to the comment. Set it to blank if you don't want your bot to add a text message to the alternate frame.
## Migration from an older version
If you updated the framebot and plan to run it on an existing configuration, you need first to execute the migration 
script. This is only necessary if your framebot didn't finish to upload all the frames from a previous video. If you 
are starting over with a new video, just follow the usage guide and configure it again.

It is advised to do a backup of your running configuration files and frames before running the script.

To run the migration script, position yourself in the directory where your cloned this repository, powershell/bash/any
shell you like window, and run 
```
framebot-migrate -s source_directory [-t target_directory]
```

where `source_directory` is the directory where the existing configuration is, and `target_directory` is the directory
where you want the migrated framebot configuration to be stored. If you omit the `target_directory` parameter, the 
configuration will be migrated into the same `source_directory`.

