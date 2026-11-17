import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_accounts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            legacy_admin = connection.execute(
                "SELECT salt, password_hash FROM admin_credentials WHERE id = 1"
            ).fetchone()
            has_admin_account = connection.execute(
                "SELECT 1 FROM admin_accounts LIMIT 1"
            ).fetchone()
            if legacy_admin is not None and has_admin_account is None:
                connection.execute(
                    """
                    INSERT INTO admin_accounts (
                        username, salt, password_hash, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        "admin",
                        legacy_admin["salt"],
                        legacy_admin["password_hash"],
                        datetime.now(timezone.utc).isoformat(),
                    ),
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

    @staticmethod
    def _normalize_admin_username(username):
        if not isinstance(username, str):
            raise ValueError("Enter an admin username or email address.")
        username = username.strip()
        if not 3 <= len(username) <= 128:
            raise ValueError("Admin usernames must be between 3 and 128 characters.")
        return username

    @staticmethod
    def _validate_admin_password(password):
        if not isinstance(password, str) or len(password) < 12:
            raise ValueError("The admin password must be at least 12 characters.")

    @staticmethod
    def _hash_admin_password(password, salt):
        LocalStorage._validate_admin_password(password)
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            LocalStorage._ADMIN_PASSWORD_ITERATIONS,
        )

    def has_admin_accounts(self):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM admin_accounts LIMIT 1"
            ).fetchone()
        return row is not None

    def _insert_admin_account(self, connection, username, password):
        salt = secrets.token_bytes(16)
        password_hash = self._hash_admin_password(password, salt)
        try:
            connection.execute(
                """
                INSERT INTO admin_accounts (
                    username, salt, password_hash, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    salt,
                    password_hash,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        except sqlite3.IntegrityError as error:
            if "admin_accounts.username" in str(error):
                raise ValueError(
                    "An admin account with this username already exists."
                ) from error
            raise

    def create_first_admin_account(self, username, password):
        username = self._normalize_admin_username(username)
        self._validate_admin_password(password)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM admin_accounts LIMIT 1"
            ).fetchone() is not None:
                return False
            self._insert_admin_account(connection, username, password)
        return True

    def add_admin_account(self, username, password):
        username = self._normalize_admin_username(username)
        self._validate_admin_password(password)
        with self._connect() as connection:
            self._insert_admin_account(connection, username, password)
        return True

    def verify_admin_account(self, username, password):
        try:
            username = self._normalize_admin_username(username)
            self._validate_admin_password(password)
        except ValueError:
            return False
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT salt, password_hash
                FROM admin_accounts
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            return False
        password_hash = self._hash_admin_password(password, row["salt"])
        return hmac.compare_digest(password_hash, row["password_hash"])

    def list_admin_accounts(self):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT username, created_at
                FROM admin_accounts
                ORDER BY username COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

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
