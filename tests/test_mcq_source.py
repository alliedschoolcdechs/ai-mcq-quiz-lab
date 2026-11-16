import unittest

from mcq_source import (
    mcq_lines_from_table,
    parse_mcq_source,
    select_answered_mcqs,
)


class McqSourceParsingTests(unittest.TestCase):
    def test_ignores_numbered_section_heading_followed_by_labeled_steps(self):
        lines = [
            "5 Computer Software",
            "A. 5.6 Programming Software",
            "B. Create the Project Files:",
            "C. Open the Project Folder in Visual Studio Code:",
            "D. Create HTML, CSS, and JavaScript Files:",
            "Answer Key: 1-D",
        ]

        questions = parse_mcq_source(lines)

        self.assertEqual(questions, [])

    def test_keeps_a_real_question_and_uses_its_answer_key(self):
        lines = [
            "1. Which software is used to create web pages?",
            "A. Presentation software",
            "B. Spreadsheet software",
            "C. Web development software",
            "D. Database software",
            "Answer Key: 1-C",
        ]

        questions = parse_mcq_source(lines)

        self.assertEqual(len(questions), 1)
        self.assertEqual(
            questions[0]["question"],
            "Which software is used to create web pages?",
        )
        self.assertEqual(questions[0]["answer"], "Web development software")
        self.assertEqual(select_answered_mcqs(questions, 1), questions)

    def test_reads_an_inline_correct_answer(self):
        lines = [
            "1. Which software is used to create web pages?",
            "A. Presentation software",
            "B. Spreadsheet software",
            "C. Web development software",
            "D. Database software",
            "Correct Answer: (C)",
        ]

        questions = parse_mcq_source(lines)

        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["answer"], "Web development software")

    def test_preserves_source_option_labels_and_resolves_shuffled_answer_key(self):
        questions = parse_mcq_source([
            "1. Which option is first in the source answer key?",
            "C) Third choice",
            "A) First choice",
            "D) Fourth choice",
            "B) Second choice",
            "Answer Key: 1-A",
        ])

        self.assertEqual(
            questions[0]["options"],
            ["Third choice", "First choice", "Fourth choice", "Second choice"],
        )
        self.assertEqual(questions[0]["option_labels"], ["C", "A", "D", "B"])
        self.assertEqual(questions[0]["answer"], "First choice")
        self.assertEqual(questions[0]["answer_index"], 1)

    def test_imports_mcq_bank_table_options_and_answer(self):
        lines = mcq_lines_from_table(
            [
                "Question Text",
                "Option A",
                "Option B",
                "Option C",
                "Option D",
                "Correct Answer",
            ],
            [
                [
                    "Which software creates web pages?",
                    "Spreadsheet software",
                    "Presentation software",
                    "Web development software",
                    "Database software",
                    "Web development software",
                ]
            ],
        )

        questions = parse_mcq_source(lines)

        self.assertEqual(len(questions), 1)
        self.assertEqual(
            questions[0]["question"],
            "Which software creates web pages?",
        )
        self.assertEqual(
            questions[0]["options"],
            [
                "Spreadsheet software",
                "Presentation software",
                "Web development software",
                "Database software",
            ],
        )
        self.assertEqual(questions[0]["answer"], "Web development software")
        self.assertEqual(questions[0]["answer_index"], 2)

    def test_preserves_question_page_and_uses_answer_key(self):
        lines = [
            {"text": "1. Which software is used to create web pages?", "page": 7},
            {"text": "A. Presentation software", "page": 7},
            {"text": "B. Spreadsheet software", "page": 7},
            {"text": "C. Web development software", "page": 7},
            {"text": "D. Database software", "page": 7},
            {"text": "Answer Key: 1-C", "page": 8},
        ]

        questions = parse_mcq_source(lines)

        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["answer"], "Web development software")
        self.assertEqual(questions[0]["page"], 7)

    def test_selects_answered_questions_and_skips_unanswered_mcqs(self):
        unanswered = {
            "question": "Which software is used to create web pages?",
            "options": [
                "Presentation software",
                "Spreadsheet software",
                "Web development software",
                "Database software",
            ],
            "answer": None,
        }
        answered = {
            **unanswered,
            "question": "Which option is correct?",
            "answer": "Web development software",
        }

        selected = select_answered_mcqs([unanswered, answered, answered], 1)

        self.assertEqual(selected, [answered])

    def test_returns_no_questions_when_the_document_has_no_usable_answers(self):
        questions = parse_mcq_source([
            "1. Which software is used to create web pages?",
            "A. Presentation software",
            "B. Spreadsheet software",
            "C. Web development software",
            "D. Database software",
        ])

        self.assertEqual(len(questions), 1)
        self.assertIsNone(questions[0]["answer"])
        self.assertEqual(select_answered_mcqs(questions, 5), [])

    def test_ignores_answer_text_that_is_not_one_of_the_options(self):
        question = {
            "question": "Which software is used to create web pages?",
            "options": ["A", "B", "C", "D"],
            "answer": "E",
        }

        self.assertEqual(select_answered_mcqs([question], 1), [])


if __name__ == "__main__":
    unittest.main()
