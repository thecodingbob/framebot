import logging
import shutil
import unittest
import tempfile
from pathlib import Path

import jsonpickle

from framebot.utils import get_logger, LoggingObject, safe_json_dump


class TestUtils(unittest.TestCase):

    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir)

    def test_safe_json_dump(self):
        test_json_file = self.test_dir.joinpath("test_json.json")
        test_obj = {"intParam": 1, "strParam": "test"}
        safe_json_dump(test_json_file, test_obj)
        self.assertTrue(test_json_file.exists())
        with open(test_json_file, "r") as f:
            read_obj = f.read()
            read_obj = jsonpickle.decode(read_obj)
            self.assertEqual(read_obj, test_obj)
        test_json_file.unlink()
        safe_json_dump(str(test_json_file), test_obj)
        self.assertTrue(test_json_file.exists())
        with open(test_json_file, "r") as f:
            read_obj = f.read()
            read_obj = jsonpickle.decode(read_obj)
            self.assertEqual(read_obj, test_obj)

    def test_get_logger(self):
        logger_name = "test_logger"
        level = logging.DEBUG
        logger = get_logger(logger_name, level)
        self.assertEqual(logger.name, logger_name)
        self.assertEqual(logger.level, level)

        # default level
        logger = get_logger(logger_name)
        self.assertEqual(logger.level, logging.INFO)
        # None parameters
        with self.assertRaises(ValueError):
            get_logger(None, level)
        with self.assertRaises(ValueError):
            get_logger(logger_name, None)

    def test_logging_object(self):
        logging_object = LoggingObject()
        self.assertEqual(logging_object.logger.name, type(logging_object).__name__)

        class LoggingObjectSubclass(LoggingObject):
            pass

        logging_object = LoggingObjectSubclass()
        self.assertEqual(logging_object.logger.name, LoggingObjectSubclass.__name__)


if __name__ == '__main__':
    unittest.main()
