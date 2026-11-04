import unittest
from unittest.mock import Mock, patch

import requests

from ollama_backend import OllamaError, find_local_model, generate_json


class OllamaDiscoveryTests(unittest.TestCase):
    @patch("ollama_backend.requests.get")
    def test_selects_configured_installed_model(self, get):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "models": [
                {"name": "llama3.2:3b"},
                {"name": "qwen3:4b"},
            ]
        }
        get.return_value = response

        model, reason = find_local_model("qwen3:4b")

        self.assertEqual(model, "qwen3:4b")
        self.assertIsNone(reason)
        get.assert_called_once_with(
            "http://127.0.0.1:11434/api/tags",
            timeout=(1, 2),
        )

    @patch("ollama_backend.requests.get")
    def test_missing_model_requests_bundled_fallback(self, get):
        response = Mock()
        response.ok = True
        response.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
        get.return_value = response

        model, reason = find_local_model("qwen3:4b")

        self.assertIsNone(model)
        self.assertIn("qwen3:4b", reason)

    @patch("ollama_backend.requests.get", side_effect=requests.ConnectionError)
    def test_stopped_service_requests_bundled_fallback(self, _get):
        model, reason = find_local_model("qwen3:4b")

        self.assertIsNone(model)
        self.assertIn("not running", reason)


class OllamaGenerationTests(unittest.TestCase):
    @patch("ollama_backend.requests.post")
    def test_requests_json_chat_and_returns_message(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {
            "message": {"content": '{"questions": []}'}
        }
        post.return_value = response

        messages = [{"role": "user", "content": "Create quiz questions"}]
        content = generate_json("qwen3:4b", messages)

        self.assertEqual(content, '{"questions": []}')
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "model": "qwen3:4b",
                "messages": messages,
                "format": "json",
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.25,
                    "num_predict": 4096,
                },
            },
        )

    @patch("ollama_backend.requests.post", side_effect=requests.Timeout)
    def test_generation_timeout_is_reported(self, _post):
        with self.assertRaisesRegex(OllamaError, "timed out"):
            generate_json("qwen3:4b", [])

    @patch("ollama_backend.requests.post")
    def test_invalid_chat_response_is_reported(self, post):
        response = Mock()
        response.ok = True
        response.json.return_value = {"message": {}}
        post.return_value = response

        with self.assertRaisesRegex(OllamaError, "invalid chat response"):
            generate_json("qwen3:4b", [])


if __name__ == "__main__":
    unittest.main()
