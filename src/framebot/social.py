"""
Contains helper methods and classes for social media upload and data gathering
"""
import time
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Union

from pyfacebook import GraphAPI, FacebookError
from PIL.Image import Image

from .utils import LoggingObject


class FacebookPostPhotoResponse:

    def __init__(self, photo_id: str, post_id: str):
        self.photo_id = photo_id
        self.post_id = post_id

    @classmethod
    def from_response_dict(cls, api_response: dict):
        return cls(api_response["id"], api_response["post_id"])

    def __eq__(self, o: object) -> bool:
        if type(o) is type(self):
            return self.__dict__ == o.__dict__
        return NotImplemented

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)


class FacebookHelper(LoggingObject):
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
        self.graph: GraphAPI = GraphAPI(access_token=access_token)

        self.logger.info(f"Initialized GraphAPI for Facebook. Page id is {self.page_id}.")

    def upload_photo(self, image: Union[Path, str, Image], message: str, album_id: str = None,
                     max_retries: int = 5, retry_time: timedelta = timedelta(minutes=3)) -> FacebookPostPhotoResponse:
        """
        Uploads a photo to a specific album, or to the news feed if no album id is specified
        :param retry_time: time to wait if a failure occurs, before the next retry
        :param max_retries: max number of retries before giving up
        :param image: The image to be posted. Could be a path to an image file or a PIL Image
        :param message: The message used as image description
        :param album_id: The album where to post the image
        :return the response object containing photo id and post id
        """
        if album_id is None:
            album_id = self.page_id
        uploaded = False
        retry_count = 0
        while not uploaded:
            try:
                if issubclass(type(image), (str, Path)):
                    with open(image, "rb") as im:
                        response = self.graph.post_object(object_id=album_id, connection="photos",
                                                          files={"source": im}, data={"message": message})
                else:
                    with BytesIO() as im_stream:
                        image.save(im_stream, "jpeg")
                        response = self.graph.post_object(object_id=album_id, connection="photos",
                                                          files={"source": im_stream.getvalue()},
                                                          data={"message": message})
                uploaded = True
                return FacebookPostPhotoResponse.from_response_dict(response)
            except FacebookError as e:
                self.logger.warning("Exception occurred during photo upload.", exc_info=True)
                if retry_count < max_retries:
                    retry_secs = retry_time.total_seconds() if "spam" not in str(e) else retry_time.total_seconds() * 10
                    self.logger.warning(f"Retrying photo upload after {retry_secs} seconds.")
                    time.sleep(retry_secs)
                else:
                    self.logger.error("Unable to post even after several retries. Check what's happening.")
                    raise e
                retry_count += 1

    def get_reactions_total_count(self, post_id: str) -> int:
        """
        Gathers the total reactions count for a post
        :param post_id: the post's story id
        :return: the total reaction count
        """
        try:
            return self.graph.get_object(object_id=post_id, fields="reactions.summary(total_count)")["reactions"][
                "summary"]["total_count"]
        except FacebookError as e:
            if e.code == 100:  # nonexisting field, e.g. that's a normal photo id from old version of the bot
                self.logger.warning(f"Tried calling 'get_reactions_total_count' with a photo id instead of a post id."
                                    f"This should only happen right after migrating from an old framebot version.")
                return self.get_reactions_total_count(self._get_story_id(post_id))
            raise e

    def _get_story_id(self, object_id: str) -> str:
        """
        Returns the story id for a given post. Here for compatibility reasons after code changes.
        :param object_id: the object id
        :return: the story id
        """
        return self.graph.get_object(object_id=object_id, fields="page_story_id")["page_story_id"]
