import unittest
from datetime import timedelta
from io import BytesIO, BufferedReader, IOBase
from pathlib import Path
from typing import Union
from unittest import TestCase
from unittest.mock import MagicMock, patch, DEFAULT, call

from PIL import Image
from pyfacebook import FacebookError

from framebot.social import FacebookHelper, open_image_stream
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

    def test_post_photo(self):
        self._test_post_photo(DUMMY_IMAGE)
        self._test_post_photo(DUMMY_IMAGE, "some_album")

    def _test_post_photo(self, src_image: Path, album_id=None):
        mock_method: MagicMock = self.mock_graph.post_object
        mock_method.return_value = {"id": PHOTO_ID, "post_id": POST_ID}

        test_message = "Test photo upload"
        response = self.testee.post_photo(src_image, test_message, album_id)
        self.assertEqual(response.photo_id, PHOTO_ID)
        self.assertEqual(response.post_id, POST_ID)

        mock_method.assert_called_once()
        call_args = mock_method.call_args
        if type(call_args.kwargs) == dict:
            call_args = call_args.kwargs
        else:
            # python 3.7
            call_args = call_args[1]
        image = call_args['files']['source']

        self.assertTrue(image.closed)
        self.assertEqual(str(src_image), image.name)

        self.assertEqual(test_message, call_args['data']['message'])
        self.assertEqual((PAGE_ID if album_id is None else album_id), call_args['object_id'])
        self.assertEqual("photos", call_args['connection'])

        mock_method.reset_mock()

    def test_post_with_retry(self):
        object_id = "id"
        connection = "connection"
        files = {"source": "fake"}
        data = {"message": "test message"}

        mock_method: MagicMock = self.mock_graph.post_object
        mock_method.side_effect = FileNotFoundError

        self.assertRaises(FileNotFoundError, self.testee._post_with_retry, object_id=object_id,
                          connection=connection, files=files, data=data)
        mock_method.assert_called_once_with(object_id=object_id, connection=connection, files=files, data=data)

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
        self.assertRaises(FacebookError, self.testee._post_with_retry, object_id=object_id, connection=connection,
                          max_retries=max_retries, retry_time=retry_time)
        self.assertEqual(max_retries + 1, mock_method.call_count)

        mock_method.reset_mock()
        expected_result = {"id": object_id}
        mock_method.side_effect = [fake_error, expected_result]
        result = self.testee._post_with_retry(object_id=object_id, connection=connection, max_retries=max_retries,
                                              retry_time=retry_time)
        self.assertEqual(max_retries, mock_method.call_count)
        self.assertEqual(expected_result, result)
        mock_method.assert_called_with(object_id=object_id, connection=connection, files=None, data=None)

        # access token expired
        mock_method.reset_mock()
        fake_error.code = 190
        mock_method.side_effect = fake_error
        self.assertRaises(FacebookError, self.testee._post_with_retry, object_id, connection)

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

    def test_post_comment(self):
        # Image and message both None
        post_id = "post_id"
        self.assertRaises(ValueError, self.testee.post_comment, post_id)

        mock_method: MagicMock = self.mock_graph.post_object
        expected_comment_id = "comment_id"
        mock_method.return_value = {"id": expected_comment_id}

        # only image
        comment_id = self.testee.post_comment(object_id=post_id, image=DUMMY_IMAGE)
        self.assertEqual(expected_comment_id, comment_id)
        mock_method.assert_called_once()

        # only message
        comment_id = self.testee.post_comment(object_id=post_id, message="message")
        self.assertEqual(expected_comment_id, comment_id)
        self.assertEqual(2, mock_method.call_count)

        # both image and message
        comment_id = self.testee.post_comment(object_id=post_id, image=DUMMY_IMAGE, message="message")
        self.assertEqual(expected_comment_id, comment_id)
        self.assertEqual(3, mock_method.call_count)

        # check empty string conversion
        comment_id = self.testee.post_comment(object_id=post_id, image=DUMMY_IMAGE, message="")
        self.assertEqual(expected_comment_id, comment_id)
        self.assertEqual(4, mock_method.call_count)
        call_args = mock_method.call_args
        if type(call_args.kwargs) == dict:
            call_args = call_args.kwargs
        else:
            # python 3.7
            call_args = call_args[1]
        self.assertEqual({"message": None}, call_args["data"])



class TestStaticMethods(TestCase):

    def test_open_image_stream(self):
        for image_variant in [DUMMY_IMAGE, str(DUMMY_IMAGE), Image.open(DUMMY_IMAGE)]:
            with open_image_stream(image_variant) as im_stream:
                self.assertTrue(issubclass(type(im_stream), IOBase))
            self.assertTrue(im_stream.closed)


if __name__ == '__main__':
    unittest.main()
