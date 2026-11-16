import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class LocalStorage:
    _ADMIN_PASSWORD_ITERATIONS = 600_000

    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    student_class TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    record_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS attempts_completed_at_idx
                ON attempts (completed_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_cache (
                    cache_key TEXT PRIMARY KEY,
                    entry_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL
                )
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_attempt(self, attempt):
        record_json = json.dumps(attempt, ensure_ascii=False)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO attempts (
                    attempt_id, student_name, student_class, completed_at,
                    record_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    attempt["attemptId"],
                    attempt["studentName"],
                    attempt["studentClass"],
                    attempt["completedAt"],
                    record_json,
                ),
            )
            if cursor.rowcount == 0:
                existing = connection.execute(
                    "SELECT record_json FROM attempts WHERE attempt_id = ?",
                    (attempt["attemptId"],),
                ).fetchone()
                if existing is None or existing["record_json"] != record_json:
                    raise sqlite3.IntegrityError(
                        "Attempt ID already exists with different record data."
                    )

    def list_attempts(self, student_filter="", class_filter=""):
        student_filter = student_filter.strip().casefold()
        class_filter = class_filter.strip().casefold()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_json
                FROM attempts
                ORDER BY completed_at DESC, attempt_id DESC
                """
            ).fetchall()
        attempts = [json.loads(row["record_json"]) for row in rows]
        return [
            attempt
            for attempt in attempts
            if student_filter
            in str(attempt.get("studentName", "")).casefold()
            and class_filter
            in str(attempt.get("studentClass", "")).casefold()
        ]

    def load_document_cache(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT cache_key, entry_json FROM document_cache ORDER BY rowid"
            ).fetchall()
        return {
            row["cache_key"]: json.loads(row["entry_json"])
            for row in rows
        }

    def save_document_cache_entry(self, cache_key, entry, max_entries=10):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO document_cache (cache_key, entry_json)
                VALUES (?, ?)
                """,
                (cache_key, json.dumps(entry, ensure_ascii=False)),
            )
            connection.execute(
                """
                DELETE FROM document_cache
                WHERE cache_key IN (
                    SELECT cache_key
                    FROM document_cache
                    ORDER BY rowid DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (max_entries,),
            )

    def has_admin_password(self):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM admin_credentials WHERE id = 1"
            ).fetchone()
        return row is not None

    def configure_admin_password(self, password):
        if len(password) < 12:
            raise ValueError("The admin password must be at least 12 characters.")

        salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self._ADMIN_PASSWORD_ITERATIONS,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO admin_credentials (id, salt, password_hash)
                VALUES (1, ?, ?)
                """,
                (salt, password_hash),
            )
        return cursor.rowcount == 1

    def verify_admin_password(self, password):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT salt, password_hash FROM admin_credentials WHERE id = 1"
            ).fetchone()
        if row is None:
            return False
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            row["salt"],
            self._ADMIN_PASSWORD_ITERATIONS,
        )
        return hmac.compare_digest(password_hash, row["password_hash"])
