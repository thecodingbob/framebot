from __future__ import annotations

from datetime import datetime
from enum import Enum
from json import JSONEncoder
from pathlib import Path
from typing import Union, Optional, TypeVar, Generic, Any

T = TypeVar("T")


class FrameStatus(Enum):
    WAITING = 1
    POSTED = 2
    ERROR = 3


class RemoteValue(Generic[T]):

    def __init__(self):
        self._value: Optional[T] = None
        self._last_updated: Optional[datetime] = None

    @property
    def value(self) -> T:
        if not self.has_value():
            raise AttributeError
        return self._value

    @value.setter
    def value(self, value: T):
        self._value = value
        self._last_updated = datetime.now()

    @property
    def last_updated(self) -> datetime:
        return self._last_updated

    def has_value(self):
        return self._value is not None


class FacebookReactionsTotal(RemoteValue[int]):
    pass


class Frame(object):

    def __init__(self, number: int, local_file: Union[str | Path]):
        self.number: int = number
        self.local_file: Path = local_file if type(local_file) is Path else Path(local_file)
        self.status: FrameStatus = FrameStatus.WAITING


class FacebookFrame(Frame):

    def __init__(self, number: int, local_file: Union[str | Path]):
        super().__init__(number, local_file)
        self._post_id: Optional[str] = None
        self.story_id: Optional[str] = None
        self._url: Optional[str] = None
        self.text = Optional[str] = None
        self._post_time: Optional[datetime] = None
        self.reactions_total: FacebookReactionsTotal = FacebookReactionsTotal()

    @property
    def post_id(self) -> Optional[str]:
        return self._post_id

    @property
    def url(self) -> Optional[str]:
        return self._url

    @property
    def post_time(self) -> Optional[datetime]:
        return self._post_time

    def mark_as_posted(self, post_id: str):
        self.status = FrameStatus.POSTED
        self._post_id = post_id
        self._url = f"https://facebook.com/{post_id}"
        self._post_time = datetime.now()


class FrameEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Frame):
            return o.__dict__
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, FrameStatus):
            return ""
        return super().default(o)
