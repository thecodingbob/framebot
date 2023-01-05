"""
Contains data classes definitions
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Union, Optional, TypeVar, Generic, Callable

from social import FacebookHelper, FacebookPostPhotoResponse

T = TypeVar("T")


class RemoteValue(Generic[T]):
    """
    Value to be fetched remotely.
    """
    def __init__(self, fetcher: Callable[[], T]):
        """
        Constructor
        :param fetcher: function used to fetch the value when needed
        """
        self._value: Optional[T] = None
        self._last_updated: Optional[datetime] = None
        self._fetcher = fetcher

    @property
    def value(self) -> T:
        """
        The object's value. Triggers the fetcher if the value was never set.
        :return: the object value
        """
        if self._value is None:
            self.refresh()
        return self._value

    def refresh(self):
        """
        Refreshes the object value by triggering the fetcher function
        """
        self._value = self._fetcher()
        self._last_updated = datetime.now()

    @property
    def last_updated(self) -> datetime:
        """
        When the object was fetched the last time
        :return: the last updated time
        """
        return self._last_updated

    def __eq__(self, o: object) -> bool:
        if type(o) is type(self):
            return self.__dict__ == o.__dict__
        return NotImplemented


class FacebookReactionsTotal(RemoteValue[int]):
    """
    Reactions count for a facebook post
    """
    def __init__(self, post_id: str, facebook_helper: FacebookHelper):
        """
        Constructor
        :param post_id: the post story id
        :param facebook_helper: helper to gather data from Facebook
        """
        self.post_id = post_id
        super().__init__(lambda: facebook_helper.get_reactions_total_count(self.post_id))


class FacebookFrame(object):
    """
    Object representing a Facebook frame (image)
    """
    def __init__(self, number: int, local_file: Union[str | Path]):
        """
        Constructor
        :param number: the frame number
        :param local_file: the local file where the image is stored
        """
        self.number: int = number
        self.local_file: Path = local_file if type(local_file) is Path else Path(local_file)
        self._photo_id: Optional[str] = None
        self._post_id: Optional[str] = None
        self._url: Optional[str] = None
        self.text: Optional[str] = None
        self._post_time: Optional[datetime] = None
        self._reactions_total: Optional[FacebookReactionsTotal] = None

    @property
    def photo_id(self) -> Optional[str]:
        """
        The Facebook's photo id after the frame has been posted
        :return: the post id
        """
        return self._photo_id

    @property
    def url(self) -> Optional[str]:
        """
        The Facebook post url after it has been posted
        :return: the url
        """
        return self._url

    @property
    def post_time(self) -> Optional[datetime]:
        """
        The time when the frame has been posted
        :return: the time
        """
        return self._post_time

    @property
    def post_id(self) -> Optional[str]:
        if self._post_id is None:
            return None
        return self._post_id

    @property
    def reactions_total(self) -> Optional[int]:
        if self._reactions_total is None:
            return None
        return self._reactions_total.value

    def mark_as_posted(self, post_response: FacebookPostPhotoResponse, facebook_helper: FacebookHelper):
        """
        Marks a frame as posted and assings values to post id, url, post time, story id and reactions total
        :param facebook_helper: helper to get story id and reaction count
        :param post_response: the post response containg photo and post id
        """
        if post_response is None:
            raise ValueError("Post response for a posted frame can't be None!")
        self._photo_id = post_response.photo_id
        self._url = f"https://facebook.com/{self._photo_id}"
        self._post_time = datetime.now()
        self._post_id = post_response.post_id
        self._reactions_total = FacebookReactionsTotal(post_id=self._post_id, facebook_helper=facebook_helper)

    def __eq__(self, o: object) -> bool:
        if type(o) is type(self):
            return self.__dict__ == o.__dict__
        return NotImplemented

    def __str__(self) -> str:
        return str({
            "number": self.number,
            "local_file": self.local_file,
            "text": self.text,
            "post_id": self.photo_id,
            "post_time": self.post_time,
            "story_id": self.photo_id,
            "reactions_total": self.reactions_total
                })
