import unittest

from attempt_review import (
    attempt_option_lines,
    escape_question_html,
    question_option_labels,
    training_feedback,
)


class AttemptReviewTests(unittest.TestCase):
    def test_escapes_question_text_for_the_same_literal_display(self):
        question = "Which tag prints <html> & *literal* text?"

        self.assertEqual(
            escape_question_html(question),
            "Which tag prints &lt;html&gt; &amp; *literal* text?",
        )

    def test_preserves_the_displayed_option_order_and_source_labels(self):
        question = {
            "options": ["Database", "Spreadsheet", "Presentation", "Web editor"],
            "option_labels": ["C", "A", "D", "B"],
        }

        self.assertEqual(
            question_option_labels(question),
            ["C", "A", "D", "B"],
        )
        self.assertEqual(
            attempt_option_lines(
                question["options"],
                question_option_labels(question),
                "Spreadsheet",
                "Database",
            ),
            [
                "C. Database (Correct answer)",
                "A. Spreadsheet (Your answer)",
                "D. Presentation",
                "B. Web editor",
            ],
        )

    def test_uses_the_same_fallback_labels_as_the_quiz(self):
        question = {
            "options": ["One", "Two", "Three", "Four"],
            "option_labels": ["A", "B"],
        }

        self.assertEqual(question_option_labels(question), list("ABCD"))

    def test_training_feedback_shows_source_grounded_explanation(self):
        question = {
            "answer": "RAM",
            "explanation": "RAM stores data and programs currently being processed.",
        }

        feedback = training_feedback(question, "ROM")

        self.assertFalse(feedback["is_correct"])
        self.assertEqual(feedback["correct_answer"], "RAM")
        self.assertEqual(
            feedback["explanation"],
            question["explanation"],
        )

    def test_training_feedback_is_honest_when_imported_mcq_has_no_reason(self):
        question = {"answer": "Database"}

        feedback = training_feedback(question, "Database")

        self.assertTrue(feedback["is_correct"])
        self.assertEqual(feedback["correct_answer"], "Database")
        self.assertIn("does not include an explanation", feedback["explanation"])


if __name__ == "__main__":
    unittest.main()
