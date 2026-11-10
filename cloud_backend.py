import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests


class CloudBackendError(RuntimeError):
    pass


def format_display_name(display_name):
    if not isinstance(display_name, str):
        return "Student"
    parts = display_name.split()
    if not parts or any("@" in part for part in parts):
        return "Student"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1]}"


@dataclass(frozen=True)
class FirebaseConfig:
    api_key: str
    project_id: str
    app_id: str
    auth_domain: str


def load_firebase_config(config_path):
    if isinstance(config_path, Mapping):
        payload = config_path
        source = "Streamlit secrets"
    else:
        path = Path(config_path)
        if not path.is_file():
            raise CloudBackendError(
                f"Firebase configuration was not found at {path}. "
                "Follow the Firebase setup instructions in README.md."
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CloudBackendError(
                f"Could not read Firebase configuration at {path}: {error}"
            ) from error
        source = f"Firebase configuration at {path}"

    return _parse_firebase_config(payload, source)


def _parse_firebase_config(payload, source):
    if not isinstance(payload, Mapping):
        raise CloudBackendError(
            f"{source} must be a JSON object or TOML table."
        )
    required = ("apiKey", "projectId", "appId")
    missing = [
        key for key in required
        if not isinstance(payload.get(key), str) or not payload[key].strip()
    ]
    if missing:
        raise CloudBackendError(
            f"{source} is missing required values: " + ", ".join(missing)
        )

    project_id = payload["projectId"].strip()
    auth_domain = payload.get(
        "authDomain", f"{project_id}.firebaseapp.com"
    )
    if not isinstance(auth_domain, str) or not auth_domain.strip():
        raise CloudBackendError(
            f"{source} has an invalid authDomain."
        )
    return FirebaseConfig(
        api_key=payload["apiKey"].strip(),
        project_id=project_id,
        app_id=payload["appId"].strip(),
        auth_domain=auth_domain.strip(),
    )


def _encode_value(value):
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_encode_value(item) for item in value]}}
    if isinstance(value, dict):
        return {
            "mapValue": {
                "fields": {
                    str(key): _encode_value(item)
                    for key, item in value.items()
                }
            }
        }
    raise TypeError(f"Unsupported Firestore field type: {type(value).__name__}")


def _decode_value(value):
    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return value["booleanValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "stringValue" in value:
        return value["stringValue"]
    if "arrayValue" in value:
        return [
            _decode_value(item)
            for item in value["arrayValue"].get("values", [])
        ]
    if "mapValue" in value:
        return _decode_fields(value["mapValue"].get("fields", {}))
    raise CloudBackendError("Firestore returned an unsupported field value.")


def _decode_fields(fields):
    return {key: _decode_value(value) for key, value in fields.items()}


class FirebaseClient:
    def __init__(self, config, id_token, timeout=20):
        self.config = config
        self.id_token = id_token
        self.timeout = timeout
        self.documents_url = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{quote(config.project_id, safe='')}/databases/(default)/documents"
        )

    def _request(self, method, url, *, params=None, payload=None):
        headers = {"Authorization": f"Bearer {self.id_token}"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise CloudBackendError(
                f"Could not reach Firebase: {error}"
            ) from error

        if not response.ok:
            try:
                details = response.json().get("error", {}).get("message", "")
            except ValueError:
                details = ""
            message = f"Firebase request failed (HTTP {response.status_code})"
            if details:
                message += f": {details}"
            raise CloudBackendError(message)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as error:
            raise CloudBackendError(
                "Firebase returned an invalid response."
            ) from error

    @staticmethod
    def _document_fields(document):
        decoded = _decode_fields(document.get("fields", {}))
        name = document.get("name", "")
        decoded["_id"] = name.rsplit("/", 1)[-1]
        return decoded

    def get_document(self, collection, document_id):
        url = (
            f"{self.documents_url}/{quote(collection, safe='')}/"
            f"{quote(document_id, safe='')}"
        )
        try:
            document = self._request("GET", url)
        except CloudBackendError as error:
            if "HTTP 404" in str(error):
                return None
            raise
        return self._document_fields(document)

    def put_document(self, collection, document_id, fields):
        encoded_fields = {
            key: _encode_value(value)
            for key, value in fields.items()
        }
        payload = {"fields": encoded_fields}
        url = (
            f"{self.documents_url}/{quote(collection, safe='')}/"
            f"{quote(document_id, safe='')}"
        )
        mask = [("updateMask.fieldPaths", key) for key in fields]
        try:
            document = self._request(
                "PATCH",
                url,
                params=mask,
                payload=payload,
            )
        except CloudBackendError as error:
            if "HTTP 404" not in str(error):
                raise
            try:
                document = self._request(
                    "POST",
                    f"{self.documents_url}/{quote(collection, safe='')}",
                    params={"documentId": document_id},
                    payload=payload,
                )
            except CloudBackendError as create_error:
                if "HTTP 409" not in str(create_error):
                    raise
                document = self._request(
                    "PATCH",
                    url,
                    params=mask,
                    payload=payload,
                )
        return self._document_fields(document)

    def delete_document(self, collection, document_id):
        url = (
            f"{self.documents_url}/{quote(collection, safe='')}/"
            f"{quote(document_id, safe='')}"
        )
        self._request("DELETE", url)

    def delete_document_fields(self, collection, document_id, field_names):
        field_names = tuple(dict.fromkeys(field_names))
        if not field_names:
            return
        url = (
            f"{self.documents_url}/{quote(collection, safe='')}/"
            f"{quote(document_id, safe='')}"
        )
        self._request(
            "PATCH",
            url,
            params=[
                ("updateMask.fieldPaths", field_name)
                for field_name in field_names
            ],
            payload={"fields": {}},
        )

    def list_documents(self, collection, page_size=1000):
        url = f"{self.documents_url}/{quote(collection, safe='')}"
        documents = []
        page_token = None
        while True:
            params = {"pageSize": min(max(page_size, 1), 1000)}
            if page_token:
                params["pageToken"] = page_token
            response = self._request("GET", url, params=params)
            documents.extend(
                self._document_fields(document)
                for document in response.get("documents", [])
            )
            page_token = response.get("nextPageToken")
            if not page_token:
                return documents, False
            if len(documents) >= 10000:
                return documents, True

    def list_user_attempts(self, uid, limit=500):
        query = {
            "structuredQuery": {
                "from": [{"collectionId": "attempts"}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "uid"},
                        "op": "EQUAL",
                        "value": {"stringValue": uid},
                    }
                },
                "limit": min(max(limit, 1), 1000),
            }
        }
        response = self._request(
            "POST",
            f"{self.documents_url}:runQuery",
            payload=query,
        )
        return [
            self._document_fields(item["document"])
            for item in response
            if item.get("document")
        ]

    def save_attempt(self, attempt):
        if "email" in attempt:
            raise CloudBackendError(
                "Quiz attempts must not include an email address."
            )
        attempt_id = attempt["attemptId"]
        url = f"{self.documents_url}/attempts"
        try:
            self._request(
                "POST",
                url,
                params={"documentId": attempt_id},
                payload={
                    "fields": {
                        key: _encode_value(value)
                        for key, value in attempt.items()
                    }
                },
            )
        except CloudBackendError as error:
            if "HTTP 409" not in str(error):
                raise
            existing = self.get_document("attempts", attempt_id)
            if (
                not existing
                or existing.get("uid") != attempt.get("uid")
                or existing.get("attemptId") != attempt_id
            ):
                raise CloudBackendError(
                    "This attempt ID already exists and does not belong to this user."
                ) from error

    def is_admin(self, uid):
        membership = self.get_document("adminMembers", uid)
        return bool(membership and membership.get("active") is True)

    def add_admin_member(self, uid, added_by, added_at):
        return self.put_document(
            "adminMembers",
            uid,
            {
                "uid": uid,
                "active": True,
                "addedBy": added_by,
                "addedAt": added_at,
            },
        )

    def remove_admin_member(self, uid):
        self.delete_document("adminMembers", uid)


def verify_firebase_id_token(config, id_token, timeout=20):
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:lookup"
        f"?key={quote(config.api_key, safe='')}"
    )
    try:
        response = requests.post(
            url,
            json={"idToken": id_token},
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise CloudBackendError(
            f"Could not verify the Google sign-in with Firebase: {error}"
        ) from error
    if not response.ok:
        try:
            details = response.json().get("error", {}).get("message", "")
        except ValueError:
            details = ""
        message = "Firebase rejected the sign-in token."
        if details:
            message += f" {details}"
        raise CloudBackendError(message)

    try:
        users = response.json().get("users", [])
    except ValueError as error:
        raise CloudBackendError(
            "Firebase returned an invalid sign-in response."
        ) from error
    if not users:
        raise CloudBackendError("Firebase returned no user for this sign-in.")

    user = users[0]
    email = user.get("email", "").strip()
    if not user.get("localId") or not email or not user.get("emailVerified"):
        raise CloudBackendError(
            "Use a Google account with a verified email address."
        )
    provider_ids = {
        provider.get("providerId")
        for provider in user.get("providerUserInfo", [])
    }
    if "google.com" not in provider_ids:
        raise CloudBackendError("Sign in with a Google account.")
    return {
        "uid": user["localId"],
        "displayName": (
            user.get("displayName", "").strip()
            if isinstance(user.get("displayName"), str)
            else ""
        ),
        "photoUrl": user.get("photoUrl", ""),
    }
