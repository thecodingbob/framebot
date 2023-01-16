"""
Contains helper methods and classes for social media upload and data gathering
"""
import time
from contextlib import contextmanager
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Union, Dict

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
    DEFAULT_RETRY_MINUTES = timedelta(minutes=1)
    DEFAULT_MAX_RETRIES = 5

    def __init__(self, access_token: str, page_id: str, timeout: timedelta = timedelta(seconds=20)):
        """
        Constructor
        :param access_token: Access token for the Facebook page
        :param page_id: Id of the Facebook page
        :param timeout: timeout for the http requests
        """
        super().__init__()
        self.access_token: str = access_token
        self.page_id: str = page_id
        # Ignoring the float warning here. The pyfacebook library incorrectly expects an integer, but then passes
        # the value to the requests module, which in turn expects a float
        self.graph: GraphAPI = GraphAPI(access_token=access_token, timeout=timeout.total_seconds())

        self.logger.info(f"Initialized GraphAPI for Facebook. Page id is {self.page_id}.")

    def post_photo(self, image: Union[Path, str, Image], message: str, album_id: str = None,
                   max_retries: int = DEFAULT_MAX_RETRIES, retry_time: timedelta = DEFAULT_RETRY_MINUTES) \
            -> FacebookPostPhotoResponse:
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
        with open_image_stream(image) as im:
            response = self._post_with_retry(object_id=album_id, connection="photos", files={"source": im},
                                             data={"message": message}, max_retries=max_retries,
                                             retry_time=retry_time)
        return FacebookPostPhotoResponse.from_response_dict(response)

    def post_comment(self, object_id: str, image: Union[Path, str, Image] = None, message: str = None,
                     max_retries: int = DEFAULT_MAX_RETRIES, retry_time: timedelta = DEFAULT_RETRY_MINUTES) -> str:
        """
        Uploads a comment to a specific post. At least one between image and message must not be None.
        :param retry_time: time to wait if a failure occurs, before the next retry
        :param max_retries: max number of retries before giving up
        :param image: The image to be posted. Could be a path to an image file or a PIL Image, or None
        :param message: The comment message, if any
        :param object_id: The post where to append the comment
        :return the comment id
        """
        if message == "":
            # empty string causes an exception with the fb api
            message = None
        if image is None and message is None:
            raise ValueError("At least one between image and message must not be None.")
        if image is not None:
            with open_image_stream(image) as im:
                response = self._post_with_retry(object_id=object_id, connection="comments", files={"source": im},
                                                 data={"message": message}, max_retries=max_retries,
                                                 retry_time=retry_time)
        else:
            response = self._post_with_retry(object_id=object_id, connection="comments", data={"message": message},
                                             max_retries=max_retries, retry_time=retry_time)
        return response['id']

    def _post_with_retry(self, object_id: str, connection: str, files: Dict = None, data: Dict = None,
                         max_retries: int = DEFAULT_MAX_RETRIES, retry_time: timedelta = DEFAULT_RETRY_MINUTES) -> Dict:
        retry_count = 0
        while True:
            try:
                return self.graph.post_object(object_id=object_id, connection=connection, files=files, data=data)
            except FacebookError as e:
                if e.code == 190:
                    self.logger.error("Expired access token. Cannot post")
                    raise e
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


@contextmanager
def open_image_stream(image: Union[Path, str, Image]) -> Union[bytes, BytesIO]:
    if issubclass(type(image), (str, Path)):
        im_stream = open(image, "rb")
        output = im_stream
    else:
        im_stream = BytesIO()
        image.save(im_stream, "jpeg")
        im_stream.seek(0)
        output = im_stream
    try:
        yield output
    finally:
        im_stream.close()
