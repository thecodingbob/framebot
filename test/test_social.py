import unittest
from io import IOBase
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from PIL import Image
from requests import Response

from framebot.social import FacebookHelper, open_image_stream, FacebookError
from test import RESOURCES_DIR

PHOTO_ID = "1"
POST_ID = "123_" + PHOTO_ID
REACTIONS = 1230

ACCESS_TOKEN = "dummy"
PAGE_ID = "dummy_id"
PAGE_NAME = "Test Page"

DUMMY_IMAGE = RESOURCES_DIR.joinpath("dummy.jpg")


class TestFacebookHelper(TestCase):

    @patch("framebot.social.request")
    def setUp(self, mock_request_method: MagicMock) -> None:
        self.mock_request_method = mock_request_method

        # Ensuring page id and page name get correctly set
        mock_response = MagicMock(Response)
        mock_response.json.return_value = {"name": PAGE_NAME, "id": PAGE_ID}
        self.mock_request_method.return_value = mock_response

        self.testee = FacebookHelper(access_token=ACCESS_TOKEN)
        self.mock_request_method.reset_mock()

    def test_init_page_details(self):
        self.assertEqual(PAGE_ID, self.testee.page_id)
        self.assertEqual(PAGE_NAME, self.testee.page_name)

    def test_default_query_params(self):
        self.assertEqual({"access_token": ACCESS_TOKEN, "format": "json"}, self.testee._default_query_params())

    def test_base_request(self):
        pass

    def test_get_object(self):
        pass

    def test_post_object(self):
        pass

    def test_post_photo(self):
        self._test_post_photo(DUMMY_IMAGE)
        self._test_post_photo(DUMMY_IMAGE, "some_album")

    def _test_post_photo(self, src_image: Path, album_id=None):
        mock_post_object: MagicMock = MagicMock(self.testee.post_object)
        mock_post_object.return_value = {"id": PHOTO_ID, "post_id": POST_ID}
        self.testee.post_object = mock_post_object

        test_message = "Test photo upload"
        response = self.testee.post_photo(src_image, test_message, album_id)
        self.assertEqual(response.photo_id, PHOTO_ID)
        self.assertEqual(response.post_id, POST_ID)

        mock_post_object.assert_called_once()
        call_args = mock_post_object.call_args
        call_args = call_args.kwargs
        image = call_args['files']['source']

        self.assertTrue(image.closed)
        self.assertEqual(str(src_image), image.name)

        self.assertEqual(test_message, call_args['data']['message'])
        self.assertEqual((PAGE_ID if album_id is None else album_id), call_args['object_id'])
        self.assertEqual("photos", call_args['connection'])

    def test_get_reactions_count(self):
        mock_get_object: MagicMock = MagicMock(self.testee.get_object)
        mock_get_object.return_value = {"reactions": {"summary": {"total_count": REACTIONS}}}
        self.testee.get_object = mock_get_object

        reactions = self.testee.get_reactions_total_count(POST_ID)

        self.assertEqual(REACTIONS, reactions)
        mock_get_object.assert_called_once_with(object_id=POST_ID, fields=["reactions.summary(total_count)"])

        mock_get_object.reset_mock()
        # called with a photo id
        story_id = "story_id"

        mock_get_object.side_effect = [FacebookError({
            "error": {
                "code": 100,
                "message": "Tried accessing nonexisting field (reactions)",
                "type": "Nonexisting field",
                "fbtrace_id": ""
            }
        }),
            {"page_story_id": story_id},
            {"reactions": {"summary": {"total_count": REACTIONS}}}
        ]
        reactions = self.testee.get_reactions_total_count(POST_ID)
        self.assertEqual(REACTIONS, reactions)
        self.assertEqual(3, mock_get_object.call_count)
        expected_calls = [
            call(object_id=POST_ID, fields=["reactions.summary(total_count)"]),
            call(object_id=POST_ID, fields=["page_story_id"]),
            call(object_id=story_id, fields=["reactions.summary(total_count)"])
        ]
        mock_get_object.assert_has_calls(expected_calls)

    def test_post_comment(self):
        # Image and message both None
        post_id = "post_id"
        self.assertRaises(ValueError, self.testee.post_comment, post_id)

        mock_post_object: MagicMock = MagicMock(self.testee.post_object)
        expected_comment_id = "comment_id"
        mock_post_object.return_value = {"id": expected_comment_id}
        self.testee.post_object = mock_post_object

        # only image
        comment_id = self.testee.post_comment(object_id=post_id, image=DUMMY_IMAGE)
        self.assertEqual(expected_comment_id, comment_id)
        mock_post_object.assert_called_once()

        # only message
        comment_id = self.testee.post_comment(object_id=post_id, message="message")
        self.assertEqual(expected_comment_id, comment_id)
        self.assertEqual(2, mock_post_object.call_count)

        # both image and message
        comment_id = self.testee.post_comment(object_id=post_id, image=DUMMY_IMAGE, message="message")
        self.assertEqual(expected_comment_id, comment_id)
        self.assertEqual(3, mock_post_object.call_count)

        # check empty string conversion
        comment_id = self.testee.post_comment(object_id=post_id, image=DUMMY_IMAGE, message="")
        self.assertEqual(expected_comment_id, comment_id)
        self.assertEqual(4, mock_post_object.call_count)
        call_args = mock_post_object.call_args
        call_args = call_args.kwargs
        self.assertEqual({"message": None}, call_args["data"])


class TestStaticMethods(TestCase):

    def test_open_image_stream(self):
        for image_variant in [DUMMY_IMAGE, str(DUMMY_IMAGE), Image.open(DUMMY_IMAGE)]:
            with open_image_stream(image_variant) as im_stream:
                self.assertTrue(issubclass(type(im_stream), IOBase))
            self.assertTrue(im_stream.closed)


if __name__ == '__main__':
    unittest.main()
