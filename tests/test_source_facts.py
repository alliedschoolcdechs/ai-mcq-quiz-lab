import random
import unittest

from mcq_logic import generate_question_items
from source_facts import definition_fragment, extract_exam_facts


class SourceFactExtractionTests(unittest.TestCase):
    def test_extracts_defined_concepts_and_function_statements(self):
        source_lines = [
            {
                "text": (
                    "RAM is temporary volatile memory that stores data and "
                    "programs currently being used by the processor."
                ),
                "page": 1,
                "unit": "Computer memory",
            },
            {
                "text": (
                    "CPU processes instructions and performs calculations "
                    "required to execute programs currently running on "
                    "the computer."
                ),
                "page": 2,
                "unit": "Computer hardware",
            },
        ]

        facts = extract_exam_facts(source_lines)

        self.assertEqual([fact["topic"] for fact in facts], ["RAM", "CPU"])
        self.assertEqual(
            definition_fragment(facts[0]),
            "temporary volatile memory that stores data and programs currently being used by the processor",
        )
        self.assertTrue(definition_fragment(facts[1]).startswith("processes instructions"))

    def test_skips_headings_and_unreliable_example_text(self):
        source_lines = [
            {"text": "Chapter 1: Computer Systems", "is_heading": True},
            {
                "text": (
                    "For example, the computer may use RAM and ROM in several "
                    "different ways during a task. ROM is non-volatile memory "
                    "that stores startup instructions needed by a computer."
                ),
            },
        ]

        facts = extract_exam_facts(source_lines)

        self.assertEqual([fact["topic"] for fact in facts], ["ROM"])

    def test_rejects_garbled_ocr_sentence_and_concept(self):
        source_lines = [
            {
                "text": (
                    "FEV WEN [Uieweleitetatelan7-0(519)> is a process that "
                    "organizes important data for students."
                ),
            },
            {
                "text": (
                    "RAM is temporary volatile memory [OCR debris] that stores "
                    "data and programs currently used by the processor."
                ),
            },
        ]

        facts = extract_exam_facts(source_lines)

        self.assertEqual(facts, [])

    def test_rejects_malformed_extracted_concepts_and_ocr_artifacts(self):
        source_lines = [
            {
                "text": (
                    "Adocument which exists and is accessible through internet "
                    "is a webpage, while a set of webpages is a termed as Website."
                ),
            },
            {
                "text": (
                    "Words the website is static and once accessed by the user; "
                    "it will be loaded from the server where you have hosted it."
                ),
            },
            {
                "text": (
                    "The installer is an executable file {.exe extension) and "
                    "you just need to | Visual Studio 2022 double click to start "
                    "the installation."
                ),
            },
            {
                "text": (
                    "Point to note: The website is static and once accessed by "
                    "the user; it will be loaded from the server where you have "
                    "hosted it."
                ),
            },
        ]

        self.assertEqual(extract_exam_facts(source_lines), [])

    def test_clean_web_facts_generate_questions_with_related_options(self):
        source_lines = [
            {
                "text": (
                    "Adocument which exists and is accessible through internet "
                    "is a webpage, while a set of webpages is a termed as Website."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "Words the website is static and once accessed by the user; "
                    "it will be loaded from the server where you have hosted it."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "The installer is an executable file {.exe extension) and "
                    "you just need to | Visual Studio 2022 double click to start "
                    "the installation."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "A webpage is a document that can be accessed through the "
                    "internet using a browser."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "A website is a collection of related webpages published "
                    "under a common domain name."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "A static website displays the same fixed content to every "
                    "visitor each time it is opened."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "Afront-end of a website is the visible part built with "
                    "HTML CSS and JavaScript for users."
                ),
                "unit": "Web development",
            },
            {
                "text": (
                    "The back-end of a website processes requests and manages "
                    "data on the hosting server."
                ),
                "unit": "Web development",
            },
        ]
        facts = extract_exam_facts(source_lines)
        records = [
            {
                "id": f"F{index}",
                "concept": fact["topic"],
                "definition": definition_fragment(fact),
                "unit": fact.get("unit"),
            }
            for index, fact in enumerate(facts, start=1)
        ]

        questions = generate_question_items(
            records,
            5,
            rng=random.Random(11),
        )

        self.assertEqual(
            {record["concept"] for record in records},
            {
                "Webpage",
                "Website",
                "Static website",
                "Front-end of a website",
                "Back-end of a website",
            },
        )
        self.assertEqual(len(questions), 5)
        self.assertTrue(
            all(
                set(question["options"]).issubset(
                    {
                        "Webpage",
                        "Website",
                        "Static website",
                        "Front-end of a website",
                        "Back-end of a website",
                    }
                )
                for question in questions
            )
        )

    def test_keeps_clean_acronym_concepts(self):
        source_lines = [{
            "text": (
                "CPU processes instructions and performs calculations "
                "required to execute programs currently running on "
                "the computer."
            ),
        }]

        facts = extract_exam_facts(source_lines)

        self.assertEqual([fact["topic"] for fact in facts], ["CPU"])

    def test_rejects_existential_there_as_a_concept(self):
        source_lines = [{
            "text": (
                "There are three common types of ROM which are PROM, EPROM "
                "and EEPROM used in computer memory systems."
            ),
        }]

        facts = extract_exam_facts(source_lines)

        self.assertEqual(facts, [])

    def test_extracted_text_can_generate_a_complete_quiz(self):
        source_lines = [
            {"text": (
                "RAM is temporary volatile memory that stores data and programs "
                "currently being used by the processor."
            ), "unit": "Computer memory"},
            {"text": (
                "ROM is non-volatile memory that stores startup instructions "
                "needed by a computer."
            ), "unit": "Computer memory"},
            {"text": (
                "Cache memory is small high-speed memory that stores frequently "
                "used data near the processor."
            ), "unit": "Computer memory"},
            {"text": (
                "Virtual memory is a storage technique that uses disk space to "
                "extend available memory when RAM is full."
            ), "unit": "Computer memory"},
            {"text": (
                "CPU processes instructions and performs calculations required "
                "to execute programs currently running on the computer."
            ), "unit": "Computer hardware"},
        ]
        facts = extract_exam_facts(source_lines)
        records = [
            {
                "id": f"F{index}",
                "concept": fact["topic"],
                "definition": definition_fragment(fact),
                "unit": fact.get("unit"),
            }
            for index, fact in enumerate(facts, start=1)
        ]

        questions = generate_question_items(
            records,
            5,
            rng=random.Random(12),
        )

        self.assertEqual(len(facts), 5)
        self.assertEqual(len(questions), 4)
        self.assertNotIn(
            "CPU",
            [question["answer"] for question in questions],
        )
        self.assertTrue(all(len(question["options"]) == 4 for question in questions))


if __name__ == "__main__":
    unittest.main()
