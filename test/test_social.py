import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Union
from unittest import TestCase
from unittest.mock import MagicMock, patch, DEFAULT, call

from PIL import Image
from pyfacebook import FacebookError

from framebot.social import FacebookHelper
from test import RESOURCES_DIR

PHOTO_ID = "1"
POST_ID = "123_" + PHOTO_ID
REACTIONS = 1230

ACCESS_TOKEN = "dummy"
PAGE_ID = "dummy_id"

DUMMY_IMAGE = RESOURCES_DIR.joinpath("dummy.jpg")


class TestFacebookHelper(TestCase):

    @patch("framebot.social.GraphAPI")
    def setUp(self, mock_graph_api_class: MagicMock) -> None:
        self.testee = FacebookHelper(access_token=ACCESS_TOKEN, page_id=PAGE_ID)
        self.mock_graph: MagicMock = self.testee.graph

    def test_upload_photo(self):
        self._test_upload_photo(DUMMY_IMAGE)
        self._test_upload_photo(str(DUMMY_IMAGE))
        self._test_upload_photo(Image.open(DUMMY_IMAGE))
        self._test_upload_photo(DUMMY_IMAGE, "some_album")

    def test_upload_photo_errors(self):
        test_message = "You'll never see this"

        mock_method: MagicMock = self.mock_graph.post_object
        mock_method.side_effect = FileNotFoundError

        self.assertRaises(FileNotFoundError, self.testee.upload_photo, DUMMY_IMAGE, test_message)
        mock_method.assert_called_once()

        mock_method.reset_mock()

        fake_error = FacebookError(kwargs={
            "error": {
                "code": 1,
                "message": "Not really an error"
            }
        })

        mock_method.side_effect = fake_error
        max_retries = 2
        retry_time = timedelta()
        self.assertRaises(FacebookError, self.testee.upload_photo, image=DUMMY_IMAGE, message=test_message,
                          max_retries=max_retries, retry_time=retry_time)
        self.assertEqual(max_retries + 1, mock_method.call_count)

        mock_method.reset_mock()
        mock_method.side_effect = [fake_error, DEFAULT]
        self._test_upload_photo(DUMMY_IMAGE, max_retries=max_retries, retry_time=retry_time,
                                expected_calls=2)

    def _test_upload_photo(self, src_image: Union[Path, str, Image.Image], album_id=None, max_retries=0,
                           retry_time=timedelta(), expected_calls=1):
        mock_method: MagicMock = self.mock_graph.post_object
        mock_method.return_value = {"id": PHOTO_ID, "post_id": POST_ID}

        test_message = "Test photo upload"
        response = self.testee.upload_photo(src_image, test_message, album_id, max_retries, retry_time)
        self.assertEqual(response.photo_id, PHOTO_ID)
        self.assertEqual(response.post_id, POST_ID)

        self.assertEqual(expected_calls, mock_method.call_count)
        call_args = mock_method.call_args
        if type(call_args.kwargs) == dict:
            call_args = call_args.kwargs
        else:
            # python 3.7
            call_args = call_args[1]
        image = call_args['files']['source']
        if not issubclass(type(src_image), Image.Image):
            self.assertTrue(image.closed)
            self.assertEqual('rb', image.mode)
            self.assertEqual(str(src_image), image.name)
        else:
            with BytesIO() as im_bytes:
                src_image.save(im_bytes, "jpeg")
                self.assertEqual(im_bytes.getvalue(), image)

        self.assertEqual(test_message, call_args['data']['message'])
        self.assertEqual((PAGE_ID if album_id is None else album_id), call_args['object_id'])
        self.assertEqual("photos", call_args['connection'])

        mock_method.reset_mock()

    def test_get_reactions_count(self):
        mock_method: MagicMock = self.mock_graph.get_object
        mock_method.return_value = {"reactions": {"summary": {"total_count": REACTIONS}}}

        reactions = self.testee.get_reactions_total_count(POST_ID)

        self.assertEqual(REACTIONS, reactions)
        mock_method.assert_called_once_with(object_id=POST_ID, fields="reactions.summary(total_count)")

        mock_method.reset_mock()
        # called with a photo id
        story_id = "story_id"
        mock_method.side_effect = [FacebookError(kwargs={
            "error": {
                "code": 100,
                "message": "Tried accessing nonexisting field (reactions)"
            }
        }),
            {"page_story_id": story_id},
            {"reactions": {"summary": {"total_count": REACTIONS}}}
        ]
        reactions = self.testee.get_reactions_total_count(POST_ID)
        self.assertEqual(REACTIONS, reactions)
        self.assertEqual(3, mock_method.call_count)
        expected_calls = [
            call(object_id=POST_ID, fields="reactions.summary(total_count)"),
            call(object_id=POST_ID, fields="page_story_id"),
            call(object_id=story_id, fields="reactions.summary(total_count)")
        ]
        mock_method.assert_has_calls(expected_calls)


if __name__ == '__main__':
    unittest.main()
