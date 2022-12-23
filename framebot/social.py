import time
from io import BytesIO
from pathlib import Path
from typing import Union

import facebook

import utils
from model import FacebookFrame


class FacebookHelper(utils.LoggingObject):

    def __init__(self, access_token: str, page_id: str):
        """
        Constructor
        :param access_token: Access token for the Facebook page
        :param page_id: Id of the Facebook page
        """
        super().__init__()
        self.access_token: str = access_token
        self.page_id: str = page_id
        self.graph: facebook.GraphAPI = facebook.GraphAPI(access_token)

        self.logger.info(f"Initialized GraphAPI for Facebook. Page id is {self.page_id}.")

    def upload_photo(self, image: Union[Path, str, BytesIO], message: str, album: str = None) -> str:
        """
        Uploads a photo to a specific album, or to the news feed if no album id is specified.
        :param image: The image to be posted. Could be a path to an image file or a BytesIO object containing the image
        data
        :param message: The message used as image description
        :param album: The album where to post the image
        :return the resulting post id
        """
        if album is None:
            album = self.page_id
        uploaded = False
        retry_count = 0
        while not uploaded:
            try:
                if type(image) in [str, Path]:
                    with open(image, "rb") as im:
                        page_post_id = self.graph.put_photo(image=im, message=message, album_path=album + "/photos")[
                            'id']
                else:
                    page_post_id = \
                        self.graph.put_photo(image=image.getvalue(), message=message, album_path=album + "/photos")[
                            'id']
                uploaded = True
            except Exception as e:
                self.logger.warning("Exception occurred during photo upload.", exc_info=True)
                if retry_count < 5:
                    self.logger.warning("Retrying photo upload...")
                    time.sleep(60 * 30 if "spam" in str(e) else 180)
                else:
                    self.logger.error("Unable to post even after several retries. Check what's happening. Bot is"
                                      " shutting down.")
                    exit()
                retry_count += 1
        return page_post_id

    def get_story_id(self, post_id: str) -> str:
        return self.graph.get_object(post_id, fields="page_story_id")["page_story_id"]

    def get_reactions(self, story_id: str) -> int:
        return self.graph.get_object(id=story_id, fields="reactions.summary(total_count)")["reactions"][
            "summary"]["total_count"]
