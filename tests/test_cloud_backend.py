import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cloud_backend import (
    CloudBackendError,
    FirebaseClient,
    FirebaseConfig,
    _decode_value,
    _encode_value,
    format_display_name,
    load_firebase_config,
    verify_firebase_id_token,
)


class FirestoreValueTests(unittest.TestCase):
    def test_firestore_values_round_trip(self):
        value = {
            "title": "Quiz",
            "graded": True,
            "score": 82.5,
            "total": 5,
            "answers": [
                {"question": "Q1", "selected": None},
                {"question": "Q2", "selected": "B"},
            ],
        }
        encoded = _encode_value(value)
        decoded = _decode_value(encoded)
        self.assertEqual(value, decoded)

    def test_unsupported_field_type_is_rejected(self):
        with self.assertRaises(TypeError):
            _encode_value(object())


class FirebaseConfigTests(unittest.TestCase):
    def test_loads_required_web_app_settings(self):
        config_data = {
            "apiKey": "public-api-key",
            "projectId": "school-quizzes",
            "appId": "1:123:web:abc",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "firebase_config.json"
            path.write_text(json.dumps(config_data), encoding="utf-8")
            config = load_firebase_config(path)

        self.assertEqual(config.project_id, "school-quizzes")
        self.assertEqual(config.auth_domain, "school-quizzes.firebaseapp.com")

    def test_loads_streamlit_secrets_mapping(self):
        config = load_firebase_config({
            "apiKey": "public-api-key",
            "projectId": "school-quizzes",
            "appId": "1:123:web:abc",
        })

        self.assertEqual(config.api_key, "public-api-key")
        self.assertEqual(config.project_id, "school-quizzes")

    def test_rejects_incomplete_streamlit_secrets_mapping(self):
        with self.assertRaisesRegex(CloudBackendError, "missing required"):
            load_firebase_config({"apiKey": "public-api-key"})

    def test_missing_config_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaisesRegex(CloudBackendError, "not found"):
                load_firebase_config(path)

    def test_incomplete_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "firebase_config.json"
            path.write_text('{"apiKey":"key"}', encoding="utf-8")
            with self.assertRaisesRegex(CloudBackendError, "missing required"):
                load_firebase_config(path)

    def test_non_object_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "firebase_config.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(CloudBackendError, "JSON object"):
                load_firebase_config(path)


class FirebaseClientTests(unittest.TestCase):
    def setUp(self):
        self.config = FirebaseConfig(
            api_key="key",
            project_id="school-quizzes",
            app_id="1:123:web:abc",
            auth_domain="school-quizzes.firebaseapp.com",
        )
        self.client = FirebaseClient(self.config, "test-id-token")

    def test_duplicate_attempt_retry_is_idempotent_for_same_user(self):
        attempt = {"attemptId": "attempt-1", "uid": "student-1"}
        self.client._request = Mock(
            side_effect=CloudBackendError("HTTP 409 ALREADY_EXISTS")
        )
        self.client.get_document = Mock(return_value=attempt)

        self.client.save_attempt(attempt)

        self.client.get_document.assert_called_once_with("attempts", "attempt-1")

    def test_duplicate_attempt_owned_by_another_user_is_rejected(self):
        attempt = {"attemptId": "attempt-1", "uid": "student-1"}
        self.client._request = Mock(
            side_effect=CloudBackendError("HTTP 409 ALREADY_EXISTS")
        )
        self.client.get_document = Mock(
            return_value={"attemptId": "attempt-1", "uid": "student-2"}
        )

        with self.assertRaisesRegex(CloudBackendError, "does not belong"):
            self.client.save_attempt(attempt)

    def test_document_is_created_when_patch_reports_missing(self):
        self.client._request = Mock(
            side_effect=[
                CloudBackendError("HTTP 404 NOT_FOUND"),
                {"name": "users/student-1"},
            ]
        )

        result = self.client.put_document(
            "users",
            "student-1",
            {"email": "student@example.com"},
        )

        self.assertEqual(result["_id"], "student-1")
        self.assertEqual(self.client._request.call_args_list[1].args[0], "POST")

    def test_student_attempt_query_is_scoped_to_uid(self):
        self.client._request = Mock(return_value=[
            {
                "document": {
                    "name": "projects/school-quizzes/databases/(default)/documents/attempts/a1",
                    "fields": {
                        "uid": {"stringValue": "student-1"},
                        "scorePct": {"integerValue": "80"},
                    },
                }
            }
        ])

        attempts = self.client.list_user_attempts("student-1")

        self.assertEqual(attempts[0]["uid"], "student-1")
        self.assertEqual(attempts[0]["scorePct"], 80)
        request_payload = self.client._request.call_args.kwargs["payload"]
        user_filter = request_payload["structuredQuery"]["where"]["fieldFilter"]
        self.assertEqual(user_filter["field"]["fieldPath"], "uid")
        self.assertEqual(user_filter["value"]["stringValue"], "student-1")

    @patch("cloud_backend.requests.post")
    def test_google_firebase_user_is_verified(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "users": [{
                "localId": "verified-uid",
                "email": "Student@School.example",
                "emailVerified": True,
                "displayName": "Student",
                "providerUserInfo": [{"providerId": "google.com"}],
            }]
        }
        post.return_value = response

        user = verify_firebase_id_token(self.config, "valid-token")

        self.assertEqual(user["uid"], "verified-uid")
        self.assertEqual(user["email"], "Student@School.example")
        self.assertEqual(user["displayName"], "Student")
        post.assert_called_once()

    @patch("cloud_backend.requests.post")
    def test_missing_google_display_name_does_not_fall_back_to_email(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "users": [{
                "localId": "verified-uid",
                "email": "student@example.com",
                "emailVerified": True,
                "providerUserInfo": [{"providerId": "google.com"}],
            }]
        }
        post.return_value = response

        user = verify_firebase_id_token(self.config, "valid-token")

        self.assertEqual(user["displayName"], "")

    @patch("cloud_backend.requests.post")
    def test_non_google_identity_is_rejected(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "users": [{
                "localId": "verified-uid",
                "email": "student@example.com",
                "emailVerified": True,
                "providerUserInfo": [{"providerId": "password"}],
            }]
        }
        post.return_value = response

        with self.assertRaisesRegex(CloudBackendError, "Google account"):
            verify_firebase_id_token(self.config, "valid-token")


class DisplayNameTests(unittest.TestCase):
    def test_formats_first_and_last_name(self):
        self.assertEqual(format_display_name("  Alex   Morgan  Lee "), "Alex Lee")

    def test_uses_neutral_fallback_when_name_is_missing(self):
        self.assertEqual(format_display_name(""), "Student")


if __name__ == "__main__":
    unittest.main()
