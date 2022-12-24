"""
Contains data classes definitions
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Union, Optional, TypeVar, Generic, Any

T = TypeVar("T")


class FrameStatus(Enum):
    WAITING = 1
    POSTED = 2
    ERROR = 3


class RemoteValue(Generic[T]):
    """
    Value to be fetched remotely.
    """
    def __init__(self):
        self._value: Optional[T] = None
        self._last_updated: Optional[datetime] = None

    @property
    def value(self) -> T:
        """
        The object's value. Raises an exception if the object wasn't ever set.
        :return: the object value
        """
        if not self.has_value():
            raise AttributeError
        return self._value

    @value.setter
    def value(self, value: T):
        """
        Setter for the object value
        :param value: the value
        """
        self._value = value
        self._last_updated = datetime.now()

    @property
    def last_updated(self) -> datetime:
        """
        When the object was fetched the last time
        :return: the last updated time
        """
        return self._last_updated

    def has_value(self):
        """
        checks if value has ever be fetched
        :return: true if there is a value, false otherwise
        """
        return self._value is not None


class FacebookReactionsTotal(RemoteValue[int]):
    """
    Wrapper for containing a post's reaction number
    """
    pass


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
        self.status: FrameStatus = FrameStatus.WAITING
        self._post_id: Optional[str] = None
        self.story_id: Optional[str] = None
        self._url: Optional[str] = None
        self.text = Optional[str] = None
        self._post_time: Optional[datetime] = None
        self.reactions_total: FacebookReactionsTotal = FacebookReactionsTotal()

    @property
    def post_id(self) -> Optional[str]:
        """
        The Facebook's post id after the frame has been posted
        :return: the post id
        """
        return self._post_id

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

    def mark_as_posted(self, post_id: str):
        """
        Marks a frame as posted and assings values to post id, url and post time
        :param post_id: the post id
        """
        self.status = FrameStatus.POSTED
        self._post_id = post_id
        self._url = f"https://facebook.com/{post_id}"
        self._post_time = datetime.now()


