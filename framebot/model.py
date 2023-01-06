"""
Contains data classes definitions
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Union, Optional


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
        self.photo_id: Optional[str] = None
        self.post_id: Optional[str] = None
        self.url: Optional[str] = None
        self.text: Optional[str] = None
        self.post_time: Optional[datetime] = None

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
            "story_id": self.photo_id
        })
