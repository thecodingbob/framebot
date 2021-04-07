# framebot
A Facebook framebot supporting reuploading of most reacted frames and random mirroring.

This project is still in a very early stage.
## Requirements
- Python >= 3.7: https://www.python.org/downloads/

You can install the other required packages with `pip install -r requirements.txt`. You may have to use pip3 and sudo if you're on Linux/Mac, depending on your configuration.
## Usage
- Create a page on Facebook
- Take not of your Page id. You can find it in the "about" section of your page
- Generate a page access token here: http://maxbots.ddns.net/token/
- Paste the generated token and the page id in the `config.ini` file 
- Configure the other options in the `config.ini` file as you like
- Put the frames you want to post in the `frames/` directory 
- Open a powershell/bash/any shell you like window in the directory where you extracted the files and run `python framebot.py`
## Configuration
You can change the bot's behavior editing the options in the `config.ini` file, which is divide in four sections:
- **facebook**
  - *page_id* - Your page's id. You can get it in the about section of the page.
  - *access_token* - The access token the bot needs to post on your page. See the Usage section.
- **bot_settings** 
  - *upload_interval* - Change this to make the bot post frames more or less often. Don't set it too small or you'll quickly end your API usages and end up blocked for hours.
  - *movie_title* - The title of the video/movie you want to show in each post.
  - *bot_name* - The bot's name. As now it's only used when posting mirrored images. You can give it a funny name you like, or you can ignore him and just let it call himself "Bot".
  - *delete_files* - Set this to True if you want the bot to delete the frame files after they're not needed anymore. Can break the bot if you stop it while it's uploading files or checking for best-ofs.
- **best_of_album_uploader**
  - *enabled* - Set this to `True` if you want the bot to check the reactions your frames got after a fixed amount of time, and repost it in an album if those exceed a fixed the threshold. If you don't want this feature, set this option to False.
  - *local_file* - The file the bot will use to store information about frames posted but not yet checked for reposting. You can leave this option as is (DON'T DELETE THIS!), it's just a filename.
  - *best_of_album_id* - The id of the album where to repost the most reacted frames. You have to create this manually, since Facebook's API don't support programmatic album creation. You can find an album's id in the url: `https://www.facebook.com/media/set/?vanity=page&set=a.album_id`.
  - *reactions_threshold* - The threshold for reposting. Frames with more than that will be reposted. Set this according to the average reaction number you expect on popular frames.
  - *wait_hours* - Number of hours a frame is given to accumulate reactions, before it's checked for reposting.
- **mirroring**
  - *enabled* - Set this to `True` if you want your bot to randomly mirror an image at the horizontal center and repost it.
  - *mirror_album_id* - Same as *best_of_album_id*, but for mirrored photos. If you just want those pics to be uploaded in your page's timeline, set this to the same value as *page_id*.
  - *ratio* - Every frame will have a ratio% chance of being mirrored.
