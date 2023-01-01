"""
Contains helper methods and classes for social media upload and data gathering
"""
import time
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Union

import facebook
from PIL.Image import Image

import utils


class FacebookHelper(utils.LoggingObject):
    """
    Helper to interact with the Facebook Graph API
    """

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

    def upload_photo(self, image: Union[Path, str, Image], message: str, album: str = None,
                     max_retries: int = 5, retry_time: timedelta = timedelta(minutes=3)) -> str:
        """
        Uploads a photo to a specific album, or to the news feed if no album id is specified.
        :param retry_time: time to wait if a failure occurs, before the next retry
        :param max_retries: max number of retries before giving up
        :param image: The image to be posted. Could be a path to an image file or a PIL Image
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
                if issubclass(type(image), (str, Path)):
                    with open(image, "rb") as im:
                        page_post_id = self.graph.put_photo(image=im, message=message, album_path=album + "/photos")[
                            'id']
                else:
                    with BytesIO() as im_stream:
                        image.save(im_stream, "jpeg")
                        page_post_id = \
                            self.graph.put_photo(image=im_stream.getvalue(), message=message,
                                                 album_path=album + "/photos")['id']
                uploaded = True
            except facebook.GraphAPIError as e:
                self.logger.warning("Exception occurred during photo upload.", exc_info=True)
                if retry_count < max_retries:
                    retry_secs = retry_time.total_seconds() if "spam" not in str(e) else retry_time.total_seconds() * 10
                    self.logger.warning(f"Retrying photo upload after {retry_secs} seconds.")
                    time.sleep(retry_secs)
                else:
                    self.logger.error("Unable to post even after several retries. Check what's happening.")
                    raise e
                retry_count += 1
        return page_post_id

    def get_story_id(self, post_id: str) -> str:
        """
        Returns the story id for a given post. Useful to get reactions.
        :param post_id: the post id
        :return: the story id
        """
        return self.graph.get_object(post_id, fields="page_story_id")["page_story_id"]

    def get_reactions_total_count(self, story_id: str) -> int:
        """
        Gathers the total reactions count for a post
        :param story_id: the post's story id
        :return: the total reaction count
        """
        return self.graph.get_object(id=story_id, fields="reactions.summary(total_count)")["reactions"][
            "summary"]["total_count"]
