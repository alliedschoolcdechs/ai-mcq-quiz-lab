import random
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

    def test_does_not_treat_short_response_questions_as_mcq_choices(self):
        parsed = parse_mcq_source([
            "1. Write answers of the following short response questions.",
            "A. What is the significance of the Most Significant Bit (MSB)?",
            "B. What is a binary digit, and why is it fundamental in computer systems?",
            "C. Why are binary numbers more efficient for computer calculations?",
            "D. How do ASCII and Unicode differ in character representation?",
            "Answer Key: 1-A",
        ])

        self.assertEqual(len(parsed), 1)
        self.assertEqual(
            select_answered_mcqs(parsed, 5),
            [],
        )

    def test_selects_different_random_subsets_from_a_large_mcq_bank(self):
        question_bank = [
            {
                "id": index,
                "question": f"Which source concept is question {index} about?",
                "options": [
                    f"Choice {index}-{label}"
                    for label in "ABCD"
                ],
                "answer": f"Choice {index}-A",
            }
            for index in range(12)
        ]

        first_selection = select_answered_mcqs(
            question_bank,
            4,
            rng=random.Random(11),
        )
        second_selection = select_answered_mcqs(
            question_bank,
            4,
            rng=random.Random(23),
        )

        self.assertEqual(len(first_selection), 4)
        self.assertEqual(len(second_selection), 4)
        self.assertNotEqual(
            {question["id"] for question in first_selection},
            {question["id"] for question in second_selection},
        )


if __name__ == "__main__":
    unittest.main()
