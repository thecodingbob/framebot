"""
Contains helper methods and classes for social media upload and data gathering
"""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import timedelta
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Union, Dict, List

from PIL.Image import Image
from requests import request, Response

from .utils import LoggingObject


class RequestMethod(Enum):
    """
    Simple enumeration to correctly set request methods
    """
    GET = "get"
    POST = "post"


@dataclass
class FacebookPostPhotoResponse:
    """
    Contains the data the Facebook Graph API response returns after posting a photo
    """

    def __init__(self, api_response: Dict):
        """
        Constructor
        :param api_response: json response from the Graph API
        """
        self.photo_id = api_response["id"]
        self.post_id = api_response["post_id"]


class FacebookHelper(LoggingObject):
    """
    Helper to interact with the Facebook Graph API
    """
    DEFAULT_RETRY_MINUTES = timedelta(minutes=1)
    DEFAULT_MAX_RETRIES = 5

    BASE_URL = "https://graph.facebook.com"
    API_VERSION = 16.0
    FIELDS_QUERY_PARAM = "fields"
    CONNECTION_QUERY_PARAM = "connection"
    STORY_ID_FIELD = "page_story_id"
    REACTIONS_FIELD = "reactions"

    def __init__(self, access_token: str):
        """
        Constructor
        :param access_token: Access token for the Facebook page
        """
        super().__init__()
        self.access_token: str = access_token
        self._init_page_details()
        self.logger.info(f"Initialized GraphAPI for Facebook. "
                         f"Page id is {self.page_id} and page name is '{self.page_name}'.")

    def _init_page_details(self) -> None:
        """
        Initializes the page details, namely page_name and page_id. Serves also as a fail-fast test for the
        provided access token.
        :return:
        """
        resp = self.get_object(object_id="me", fields=["name,id"])
        self.page_name = resp["name"]
        self.page_id = resp["id"]

    def _default_query_params(self) -> Dict:
        """
        Provides the default query parameters needed to be included in every request
        :return: the default query parametrs
        """
        return {"access_token": self.access_token, "format": "json"}

    def _base_request(self, method: RequestMethod, object_id: str, connection: str = None,
                      query_parameters: Dict = None, files: Dict = None, data: Dict = None) -> Dict:
        """
        Generic request to the Graph API
        :param method: the HTTP method for the request
        :param object_id: Facebook object id, e.g. a post or an album
        :param connection: e.g. comments or photos
        :param query_parameters: extra query parameters for the requests
        :param files: files to upload with the request, e.g. an image
        :param data: request body. Can contain, for example, a comment
        :return: The Graph API response in json format
        """
        if query_parameters is None:
            query_parameters = {}
        query_parameters = {**self._default_query_params(), **query_parameters}

        request_url = f"{self.BASE_URL}/v{self.API_VERSION}/{object_id}" + \
                      (f"/{connection}" if connection is not None else "")
        self.logger.debug(f"Firing {method.value} request to {request_url} with parameters {query_parameters}")

        response = request(method=method.value, url=request_url, params=query_parameters, files=files, data=data)

        if response.ok:
            return response.json()

        if response.status_code == 400:
            raise FacebookError(response.json())

        raise RequestError(response)

    def get_object(self, object_id: str, fields: List[str] = None) -> Dict:
        """
        Retrieves an object and some of its fields.
        :param object_id: the wanted Facebook object's id
        :param fields: wanted fields for the object, e.g. story id or reactions
        :return: the Graph API json response
        """
        return self._base_request(RequestMethod.GET, object_id=object_id,
                                  query_parameters={self.FIELDS_QUERY_PARAM: ",".join(fields)})

    def post_object(self, object_id: str, connection: str, files: Dict = None, data: Dict = None) -> Dict:
        """
        Posts a file or some data
        :param object_id: the parent object id where to post the object
        :param connection: e.g. comments or photos
        :param files: files to upload
        :param data: data to upload, e.g. a comment
        :return: the Graph API json response
        """
        return self._base_request(RequestMethod.POST, object_id=object_id, connection=connection, files=files,
                                  data=data)

    def _get_story_id(self, object_id: str) -> str:
        """
        Returns the story id for a given post. Here for compatibility reasons after code changes.
        :param object_id: the object id
        :return: the story id
        """
        return self.get_object(object_id=object_id, fields=[self.STORY_ID_FIELD])[self.STORY_ID_FIELD]

    def post_photo(self, image: Union[Path, str, Image], message: str, album_id: str = None) -> \
            FacebookPostPhotoResponse:
        """
        Uploads a photo to a specific album, or to the news feed if no album id is specified
        :param image: The image to be posted. Could be a path to an image file or a PIL Image
        :param message: The message used as image description
        :param album_id: The album where to post the image
        :return the response object containing photo id and post id
        """
        if album_id is None:
            album_id = self.page_id
        with open_image_stream(image) as im:
            response = self.post_object(object_id=album_id, connection="photos", files={"source": im},
                                        data={"message": message})
        return FacebookPostPhotoResponse(response)

    def post_comment(self, object_id: str, image: Union[Path, str, Image] = None, message: str = None) -> str:
        """
        Uploads a comment to a specific post. At least one between image and message must not be None.
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
                response = self.post_object(object_id=object_id, connection="comments", files={"source": im},
                                            data={"message": message})
        else:
            response = self.post_object(object_id=object_id, connection="comments", data={"message": message})
        return response['id']

    def get_reactions_total_count(self, post_id: str) -> int:
        """
        Gathers the total reactions count for a post
        :param post_id: the post's story id
        :return: the total reaction count
        """
        try:
            return self.get_object(object_id=post_id,
                                   fields=[f"{self.REACTIONS_FIELD}.summary(total_count)"]
                                   )[self.REACTIONS_FIELD]["summary"]["total_count"]

        except FacebookError as e:
            if e.code == 100:  # nonexisting field, e.g. that's a normal photo id from old version of the bot
                self.logger.warning(f"Tried calling 'get_reactions_total_count' with a photo id instead of a post id."
                                    f"This should only happen right after migrating from an old framebot version.")
                return self.get_reactions_total_count(self._get_story_id(post_id))
            raise e


@contextmanager
def open_image_stream(image: Union[Path, str, Image]) -> Union[bytes, BytesIO]:
    """
    Abstracts the image stream opening code between Path objects, strings representing paths and PIL images
    :param image: a Path object pointing to the image, a string containing the path to the image, or a PIL image
    :return: a stream for the image data
    """
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


class RequestError(Exception):
    """
    An error regarding an HTTP request
    """

    def __init__(self, response: Response):
        self.status_code = response.status_code
        self.response_body = response.text
        super().__init__(f"Error in the request: {self.status_code} - {self.response_body}")


class FacebookError(Exception):
    """
    An error from the Facebook Graph API
    """

    def __init__(self, json_data: Dict):
        json_data = json_data["error"]
        self.type: str = json_data["type"]
        self.code: int = json_data["code"]
        self.message: str = json_data["message"]
        self.fbtrace_id: str = json_data["fbtrace_id"]
        super().__init__(f"Graph API error: {json_data}")
