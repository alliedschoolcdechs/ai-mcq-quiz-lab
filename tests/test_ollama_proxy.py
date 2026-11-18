import json
import os
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch

from ollama_proxy import OllamaProxyHandler, OllamaProxyServer


class OllamaProxyTests(unittest.TestCase):
    def setUp(self):
        self.previous_token = os.environ.get("OLLAMA_PROXY_TOKEN")
        self.token = "test-token-that-is-at-least-32-characters-long"
        os.environ["OLLAMA_PROXY_TOKEN"] = self.token
        self.server = OllamaProxyServer(("127.0.0.1", 0), OllamaProxyHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.previous_token is None:
            os.environ.pop("OLLAMA_PROXY_TOKEN", None)
        else:
            os.environ["OLLAMA_PROXY_TOKEN"] = self.previous_token

    def test_requires_bearer_token_before_forwarding(self):
        with patch("ollama_proxy.requests.get") as mock_get:
            with self.assertRaises(HTTPError) as error:
                urlopen(f"{self.base_url}/api/tags")

        self.assertEqual(error.exception.code, 401)
        error.exception.close()
        mock_get.assert_not_called()

    @patch("ollama_proxy.requests.get")
    def test_forwards_authenticated_model_list_request(self, mock_get):
        response = Mock(
            status_code=200,
            content=b'{"models":[]}',
            headers={"Content-Type": "application/json"},
        )
        mock_get.return_value = response
        request = Request(
            f"{self.base_url}/api/tags",
            headers={"Authorization": f"Bearer {self.token}"},
        )

        with urlopen(request) as result:
            self.assertEqual(json.loads(result.read()), {"models": []})

        mock_get.assert_called_once_with(
            "http://127.0.0.1:11434/api/tags",
            timeout=5,
        )

    @patch("ollama_proxy.requests.post")
    def test_forwards_only_authenticated_chat_requests(self, mock_post):
        response = Mock(
            status_code=200,
            content=b'{"message":{"content":"{}"}}',
            headers={"Content-Type": "application/json"},
        )
        mock_post.return_value = response
        body = b'{"model":"qwen2.5:7b","stream":false}'
        request = Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(request) as result:
            self.assertEqual(result.status, 200)

        mock_post.assert_called_once_with(
            "http://127.0.0.1:11434/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            timeout=300,
        )

    @patch("ollama_proxy.requests.get")
    def test_rejects_endpoints_other_than_model_list(self, mock_get):
        request = Request(
            f"{self.base_url}/admin",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request)

        self.assertEqual(error.exception.code, 404)
        error.exception.close()
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
