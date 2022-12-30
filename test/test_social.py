import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Union
from unittest import TestCase
from unittest.mock import MagicMock, patch, DEFAULT

import facebook

from social import FacebookHelper

from test import RESOURCES_DIR

POST_ID = "1"
STORY_ID = "123_" + POST_ID
REACTIONS = 1230

ACCESS_TOKEN = "dummy"
PAGE_ID = "dummy_id"

DUMMY_IMAGE = RESOURCES_DIR.joinpath("dummy.jpg")


class TestFacebookHelper(TestCase):
    GRAPH_API_CLASS = "facebook.GraphAPI"

    @patch(GRAPH_API_CLASS)
    def setUp(self, mock_graph_api) -> None:
        self.testee = FacebookHelper(access_token=ACCESS_TOKEN, page_id=PAGE_ID)
        self.mock_graph: MagicMock = self.testee.graph

    def test_upload_photo(self):
        self._test_upload_photo(DUMMY_IMAGE)
        self._test_upload_photo(str(DUMMY_IMAGE))
        self._test_upload_photo(BytesIO())
        self._test_upload_photo(DUMMY_IMAGE, "some_album")

    def test_upload_photo_errors(self):
        test_message = "You'll never see this"

        mock_method: MagicMock = self.mock_graph.put_photo
        mock_method.side_effect = FileNotFoundError

        self.assertRaises(FileNotFoundError, self.testee.upload_photo, DUMMY_IMAGE, test_message)
        mock_method.assert_called_once()

        mock_method.reset_mock()

        mock_method.side_effect = facebook.GraphAPIError(result=None)
        max_retries = 2
        retry_time = timedelta()
        self.assertRaises(facebook.GraphAPIError, self.testee.upload_photo, image=DUMMY_IMAGE, message=test_message,
                          max_retries=max_retries, retry_time=retry_time)
        self.assertEqual(max_retries + 1, mock_method.call_count)

        mock_method.reset_mock()
        mock_method.side_effect = [facebook.GraphAPIError(result=None), DEFAULT]
        self._test_upload_photo(DUMMY_IMAGE, max_retries=max_retries, retry_time=retry_time,
                                expected_calls=2)

    def _test_upload_photo(self, src_image: Union[Path, str, BytesIO], album_id=None, max_retries=0,
                           retry_time=timedelta(), expected_calls=1):
        mock_method: MagicMock = self.mock_graph.put_photo
        mock_method.return_value = {'id': POST_ID}

        test_message = "Test photo upload"
        photo_id = self.testee.upload_photo(src_image, test_message, album_id, max_retries, retry_time)
        self.assertEqual(photo_id, POST_ID)

        self.assertEqual(expected_calls, mock_method.call_count)
        call_args = mock_method.call_args.kwargs
        image = call_args['image']
        if type(src_image) is not BytesIO:
            self.assertTrue(image.closed)
            self.assertEqual('rb', image.mode)
            self.assertEqual(str(src_image), image.name)
        else:
            self.assertEqual(src_image.getvalue(), image)

        self.assertEqual(test_message, call_args['message'])
        self.assertEqual((PAGE_ID if album_id is None else album_id) + "/photos", call_args['album_path'])

        mock_method.reset_mock()

    def test_get_story_id(self):
        mock_method: MagicMock = self.mock_graph.get_object
        mock_method.return_value = {"page_story_id": STORY_ID}

        story_id = self.testee.get_story_id(POST_ID)

        self.assertEqual(STORY_ID, story_id)
        mock_method.assert_called_once_with(POST_ID, fields="page_story_id")

    def test_get_reactions_count(self):
        mock_method: MagicMock = self.mock_graph.get_object
        mock_method.return_value = {"reactions": {"summary": {"total_count": REACTIONS}}}

        reactions = self.testee.get_reactions_total_count(STORY_ID)

        self.assertEqual(REACTIONS, reactions)
        mock_method.assert_called_once_with(id=STORY_ID, fields="reactions.summary(total_count)")


if __name__ == '__main__':
    unittest.main()
