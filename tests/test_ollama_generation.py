import json
import random
import unittest
from unittest.mock import Mock, patch

import requests

from ollama_generation import (
    OllamaError,
    generate_mcqs_with_ollama,
    list_ollama_models,
)
from source_facts import extract_exam_facts


class OllamaGenerationTests(unittest.TestCase):
    def setUp(self):
        source_lines = [
            {
                "text": (
                    "A webpage is a document that can be accessed through the "
                    "internet using a browser."
                ),
                "unit": "Web development",
                "page": 1,
            },
            {
                "text": (
                    "A website is a collection of related webpages published "
                    "under a common domain name."
                ),
                "unit": "Web development",
                "page": 1,
            },
            {
                "text": (
                    "A static website displays the same fixed content to every "
                    "visitor each time it is opened."
                ),
                "unit": "Web development",
                "page": 2,
            },
            {
                "text": (
                    "The front-end of a website is the visible part built with "
                    "HTML CSS and JavaScript for users."
                ),
                "unit": "Web development",
                "page": 2,
            },
            {
                "text": (
                    "The back-end of a website processes requests and manages "
                    "data on the hosting server."
                ),
                "unit": "Web development",
                "page": 3,
            },
        ]
        self.facts = extract_exam_facts(source_lines)

    def _chat_response(self, distractor_ids=None):
        def respond(*args, **kwargs):
            payload = kwargs["json"]
            prompt = payload["messages"][1]["content"]
            target_json = prompt.split(
                "TARGETS AND ALLOWED DISTRACTORS:\n", 1
            )[1].split("\nSOURCE CONCEPTS:", 1)[0]
            target = json.loads(target_json)[0]
            selected_distractors = (
                distractor_ids
                if distractor_ids is not None
                else target["allowed_distractor_ids"][:3]
            )
            result = {
                "questions": [{
                    "source_fact_id": target["id"],
                    "question": "Which concept best fits this source-backed scenario?",
                    "distractor_fact_ids": selected_distractors,
                }]
            }
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "message": {"content": json.dumps(result)}
            }
            return response

        return respond

    @patch("ollama_generation.requests.get")
    def test_lists_installed_models(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "models": [
                {"name": "qwen2.5:7b"},
                {"name": "llama3.2:3b"},
                {"name": "qwen2.5:7b"},
                {},
            ]
        }
        mock_get.return_value = response

        self.assertEqual(
            list_ollama_models("http://127.0.0.1:11434"),
            ["llama3.2:3b", "qwen2.5:7b"],
        )
        mock_get.assert_called_once_with(
            "http://127.0.0.1:11434/api/tags",
            timeout=3,
        )

    @patch("ollama_generation.requests.get", side_effect=requests.ConnectionError)
    def test_reports_when_ollama_is_unavailable(self, _mock_get):
        with self.assertRaisesRegex(OllamaError, "Could not reach Ollama"):
            list_ollama_models("http://127.0.0.1:11434")

    @patch("ollama_generation.requests.post")
    def test_generates_questions_with_source_validated_choices(self, mock_post):
        mock_post.side_effect = self._chat_response()

        questions = generate_mcqs_with_ollama(
            self.facts,
            self.facts,
            1,
            "qwen2.5:7b",
            base_url="http://127.0.0.1:11434",
            rng=random.Random(4),
        )

        self.assertEqual(len(questions), 1)
        question = questions[0]
        self.assertEqual(len(question["options"]), 4)
        self.assertIn(question["answer"], question["options"])
        self.assertEqual(question["correct_answer_index"], question["options"].index(question["answer"]))
        self.assertTrue(question["explanation"])
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen2.5:7b")
        self.assertFalse(payload["stream"])
        self.assertIsInstance(payload["format"], dict)

    @patch("ollama_generation.requests.post")
    def test_rejects_distractors_outside_the_source_concept_map(self, mock_post):
        mock_post.side_effect = self._chat_response(["F2", "F3", "F999"])

        questions = generate_mcqs_with_ollama(
            self.facts,
            self.facts,
            1,
            "qwen2.5:7b",
            base_url="http://127.0.0.1:11434",
            rng=random.Random(4),
        )

        self.assertEqual(questions, [])

    def test_rejects_invalid_ollama_urls(self):
        with self.assertRaisesRegex(OllamaError, "OLLAMA_BASE_URL"):
            list_ollama_models("file:///tmp/ollama")


if __name__ == "__main__":
    unittest.main()
