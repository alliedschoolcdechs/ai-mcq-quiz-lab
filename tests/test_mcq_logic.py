import random
import unittest

from mcq_logic import generate_question_items


class SourceGroundedQuestionTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "id": "F1",
                "concept": "RAM",
                "definition": (
                    "temporary memory used to store data and programs "
                    "currently being processed"
                ),
                "unit": "Computer memory",
            },
            {
                "id": "F2",
                "concept": "ROM",
                "definition": (
                    "non-volatile memory that stores permanent instructions "
                    "needed to start a computer"
                ),
                "unit": "Computer memory",
            },
            {
                "id": "F3",
                "concept": "Cache memory",
                "definition": (
                    "small high-speed memory that stores frequently used "
                    "data near the processor"
                ),
                "unit": "Computer memory",
            },
            {
                "id": "F4",
                "concept": "Virtual memory",
                "definition": (
                    "a storage technique that uses disk space to extend "
                    "available memory when RAM is full"
                ),
                "unit": "Computer memory",
            },
            {
                "id": "F5",
                "concept": "Input device",
                "definition": (
                    "hardware used to enter data and instructions into "
                    "a computer"
                ),
                "unit": "Computer hardware",
            },
            {
                "id": "F6",
                "concept": "Output device",
                "definition": (
                    "hardware that presents processed information to a user"
                ),
                "unit": "Computer hardware",
            },
        ]

    def test_builds_source_backed_four_choice_questions_without_a_model(self):
        questions = generate_question_items(
            self.records,
            5,
            rng=random.Random(7),
        )

        self.assertEqual(len(questions), 5)
        for question in questions:
            target = next(
                record for record in self.records
                if record["id"] == question["source_fact_id"]
            )
            self.assertEqual(question["answer"], target["concept"])
            self.assertEqual(len(question["options"]), 4)
            self.assertEqual(
                len({option.casefold() for option in question["options"]}),
                4,
            )
            self.assertIn(question["answer"], question["options"])
            self.assertTrue(question["question"].endswith("?"))
            self.assertGreaterEqual(len(question["question"]), 20)

    def test_question_text_uses_function_wording_when_source_supports_it(self):
        questions = generate_question_items(
            self.records,
            6,
            rng=random.Random(1),
        )

        ram = next(question for question in questions if question["answer"] == "RAM")
        self.assertIn("used to store", ram["question"])
        self.assertEqual(ram["question_type"], "function")

    def test_memory_question_uses_same_topic_as_its_distractors(self):
        questions = generate_question_items(
            self.records,
            6,
            rng=random.Random(7),
        )

        ram = next(question for question in questions if question["answer"] == "RAM")
        memory_concepts = {"RAM", "ROM", "Cache memory", "Virtual memory"}
        self.assertTrue(set(ram["options"]).issubset(memory_concepts))

    def test_filtered_targets_can_use_related_facts_as_distractors(self):
        questions = generate_question_items(
            [self.records[0]],
            1,
            distractor_records=self.records[1:],
            rng=random.Random(2),
        )

        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["answer"], "RAM")
        self.assertEqual(len(questions[0]["options"]), 4)

    def test_refuses_to_make_four_choice_questions_with_too_few_concepts(self):
        questions = generate_question_items(
            self.records[:3],
            3,
            rng=random.Random(3),
        )

        self.assertEqual(questions, [])

    def test_rejects_generic_there_label_as_question_target_or_option(self):
        generic_concept = {
            "id": "F0",
            "concept": "There",
            "definition": (
                "are three common types of ROM which are PROM, EPROM "
                "and EEPROM used in computer memory systems"
            ),
            "unit": "Computer memory",
        }

        questions = generate_question_items(
            [generic_concept, *self.records[:3]],
            4,
            rng=random.Random(3),
        )

        self.assertNotIn(
            "There",
            [option for question in questions for option in question["options"]],
        )
        self.assertTrue(all(question["answer"] != "There" for question in questions))


if __name__ == "__main__":
    unittest.main()
