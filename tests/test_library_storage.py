import tempfile
import unittest
from pathlib import Path

from library_storage import (
    DuplicateLibraryFileError,
    add_library_file,
)


class LibraryStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.library_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_rejects_identical_content_with_a_different_name(self):
        original = add_library_file(
            self.library_dir,
            "lesson.pdf",
            b"same lesson content",
            {".pdf", ".docx"},
        )

        with self.assertRaisesRegex(DuplicateLibraryFileError, "lesson.pdf"):
            add_library_file(
                self.library_dir,
                "copy.docx",
                b"same lesson content",
                {".pdf", ".docx"},
            )

        self.assertEqual(
            [path.name for path in self.library_dir.iterdir()],
            [original.name],
        )

    def test_keeps_different_content_with_a_colliding_name(self):
        add_library_file(
            self.library_dir,
            "lesson.pdf",
            b"original content",
            {".pdf"},
        )

        saved_path = add_library_file(
            self.library_dir,
            "lesson.pdf",
            b"updated content",
            {".pdf"},
        )

        self.assertEqual(saved_path.name, "lesson (2).pdf")
        self.assertEqual(saved_path.read_bytes(), b"updated content")


if __name__ == "__main__":
    unittest.main()
