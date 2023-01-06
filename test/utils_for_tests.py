import os
import shutil
import tempfile
import unittest
from pathlib import Path

from framebot.model import FacebookFrame

from test import RESOURCES_DIR


class FileWritingTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        os.chdir(self.test_dir)

    def tearDown(self) -> None:
        if Path(os.getcwd()) == self.test_dir:
            os.chdir("/")
        shutil.rmtree(self.test_dir)


def generate_test_frame() -> FacebookFrame:
    test_frame = FacebookFrame(number=1, local_file=RESOURCES_DIR.joinpath("dummy.jpg"))
    test_frame.text = "This is a test frame. \nIt has no purpose outside of the tests."
    return test_frame
