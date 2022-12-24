"""
Contains data classes definitions
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Union, Optional, TypeVar, Generic, Any, Callable

from social import FacebookHelper

T = TypeVar("T")


class FrameStatus(Enum):
    WAITING = 1
    POSTED = 2
    ERROR = 3


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
        self._value = self._fetcher
        self._last_updated = datetime.now()

    @property
    def last_updated(self) -> datetime:
        """
        When the object was fetched the last time
        :return: the last updated time
        """
        return self._last_updated


class FacebookStoryId(RemoteValue[str]):
    """
    Represents the story id for a Facebook post.
    """
    def __init__(self, post_id: str, facebook_helper: FacebookHelper):
        """
        Constructor
        :param post_id: the post id
        :param facebook_helper: helper to gather data from Facebook
        """
        self.post_id = post_id
        super().__init__(lambda p_id: facebook_helper.get_story_id(self.post_id))


class FacebookReactionsTotal(RemoteValue[int]):
    """
    Reactions count for a facebook post
    """
    def __init__(self, story_id: FacebookStoryId, facebook_helper: FacebookHelper):
        """
        Constructor
        :param story_id: the post story id
        :param facebook_helper: helper to gather data from Facebook
        """
        self.story_id = story_id
        super().__init__(lambda s_id: facebook_helper.get_reactions_total_count(self.story_id.value))


class FacebookFrame(object):
    """
    Object representing a Facebook frame (image)
    """
    def __init__(self, number: int, local_file: Union[str | Path], facebook_helper: FacebookHelper):
        """
        Constructor
        :param number: the frame number
        :param local_file: the local file where the image is stored
        """
        self.number: int = number
        self.local_file: Path = local_file if type(local_file) is Path else Path(local_file)
        self.status: FrameStatus = FrameStatus.WAITING
        self._post_id: Optional[str] = None
        self._story_id: Optional[FacebookStoryId] = None
        self._url: Optional[str] = None
        self.text = Optional[str] = None
        self._post_time: Optional[datetime] = None
        self._reactions_total: Optional[FacebookReactionsTotal] = None
        self.facebook_helper = facebook_helper

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

    @property
    def story_id(self) -> Optional[str]:
        if self._story_id is None:
            return None
        return self._story_id.value

    @property
    def reactions_total(self) -> Optional[int]:
        if self._reactions_total is None:
            return None
        return self._reactions_total.value

    def mark_as_posted(self, post_id: str):
        """
        Marks a frame as posted and assings values to post id, url, post time, story id and reactions total
        :param post_id: the post id
        """
        self.status = FrameStatus.POSTED
        self._post_id = post_id
        self._url = f"https://facebook.com/{post_id}"
        self._post_time = datetime.now()
        self._story_id = FacebookStoryId(post_id=post_id, facebook_helper=self.facebook_helper)
        self._reactions_total = FacebookReactionsTotal(story_id=self._story_id, facebook_helper=self.facebook_helper)
