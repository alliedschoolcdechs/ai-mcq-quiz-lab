import sqlite3
import tempfile
import unittest
from pathlib import Path

from local_storage import LocalStorage


class LocalStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = LocalStorage(
            Path(self.temp_dir.name) / "data" / "quiz.sqlite3"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_attempt(self, attempt_id, name, student_class, completed_at):
        return {
            "attemptId": attempt_id,
            "studentName": name,
            "studentClass": student_class,
            "fileName": "Computer Grade 9.pdf",
            "quizMode": "Examination",
            "questionSource": "generated",
            "graded": True,
            "scorePct": 80,
            "correctCount": 4,
            "total": 5,
            "startedAt": "2026-11-14T10:00:00+00:00",
            "completedAt": completed_at,
            "durationSeconds": 90,
            "answers": [{"question": "Q1", "selectedAnswer": "A"}],
        }

    def test_saves_and_reloads_full_attempt_records(self):
        attempt = self.make_attempt(
            "attempt-1", "Alex Morgan", "Grade 9A", "2026-11-14T10:01:30+00:00"
        )

        self.storage.save_attempt(attempt)
        reloaded = LocalStorage(self.storage.database_path).list_attempts()

        self.assertEqual(reloaded, [attempt])
        self.assertEqual(reloaded[0]["answers"], attempt["answers"])

    def test_filters_attempts_by_student_and_class_case_insensitively(self):
        self.storage.save_attempt(
            self.make_attempt(
                "attempt-1", "Alex Morgan", "Grade 9A",
                "2026-11-14T10:01:30+00:00",
            )
        )
        self.storage.save_attempt(
            self.make_attempt(
                "attempt-2", "Sam Lee", "Grade 10B",
                "2026-11-14T10:02:30+00:00",
            )
        )

        filtered = self.storage.list_attempts("alex", "grade 9")

        self.assertEqual([attempt["attemptId"] for attempt in filtered], ["attempt-1"])

    def test_retrying_identical_attempt_is_idempotent(self):
        attempt = self.make_attempt(
            "attempt-1", "Alex Morgan", "Grade 9A", "2026-11-14T10:01:30+00:00"
        )

        self.storage.save_attempt(attempt)
        self.storage.save_attempt(attempt)

        self.assertEqual(len(self.storage.list_attempts()), 1)

    def test_rejects_reuse_of_attempt_id_for_different_record(self):
        original = self.make_attempt(
            "attempt-1", "Alex Morgan", "Grade 9A", "2026-11-14T10:01:30+00:00"
        )
        conflicting = {**original, "studentName": "Someone else"}
        self.storage.save_attempt(original)

        with self.assertRaises(sqlite3.IntegrityError):
            self.storage.save_attempt(conflicting)

    def test_document_cache_persists_and_keeps_only_recent_entries(self):
        for index in range(12):
            self.storage.save_document_cache_entry(
                f"cache-{index}",
                {"fileName": f"book-{index}.pdf", "facts": []},
            )

        cache = self.storage.load_document_cache()

        self.assertEqual(len(cache), 10)
        self.assertNotIn("cache-0", cache)
        self.assertIn("cache-11", cache)

    def test_admin_password_is_stored_as_a_salted_hash_and_persists(self):
        password = "a-long-local-admin-password"

        self.assertFalse(self.storage.has_admin_password())
        self.assertFalse(self.storage.verify_admin_password(password))
        self.assertTrue(self.storage.configure_admin_password(password))

        reloaded = LocalStorage(self.storage.database_path)
        self.assertTrue(reloaded.has_admin_password())
        self.assertTrue(reloaded.verify_admin_password(password))
        self.assertFalse(reloaded.verify_admin_password("incorrect-password"))
        with reloaded._connect() as connection:
            row = connection.execute(
                "SELECT salt, password_hash FROM admin_credentials"
            ).fetchone()
        self.assertNotEqual(row["password_hash"], password.encode("utf-8"))
        self.assertEqual(len(row["salt"]), 16)

    def test_admin_password_can_only_be_configured_once(self):
        self.assertTrue(
            self.storage.configure_admin_password("first-admin-password")
        )
        self.assertFalse(
            self.storage.configure_admin_password("second-admin-password")
        )
        self.assertTrue(
            self.storage.verify_admin_password("first-admin-password")
        )
        self.assertFalse(
            self.storage.verify_admin_password("second-admin-password")
        )

    def test_rejects_short_admin_password(self):
        with self.assertRaisesRegex(ValueError, "at least 12 characters"):
            self.storage.configure_admin_password("too-short")


if __name__ == "__main__":
    unittest.main()
