import unittest

from mcq_import import parse_imported_mcqs


class ImportedMcqParsingTests(unittest.TestCase):
    def test_ignores_numbered_section_heading_followed_by_labeled_steps(self):
        lines = [
            "5 Computer Software",
            "A. 5.6 Programming Software",
            "B. Create the Project Files:",
            "C. Open the Project Folder in Visual Studio Code:",
            "D. Create HTML, CSS, and JavaScript Files:",
            "Answer Key: 1-D",
        ]

        questions = parse_imported_mcqs(lines)

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

        questions = parse_imported_mcqs(lines)

        self.assertEqual(len(questions), 1)
        self.assertEqual(
            questions[0]["question"],
            "Which software is used to create web pages?",
        )
        self.assertEqual(questions[0]["answer"], "Web development software")


if __name__ == "__main__":
    unittest.main()
