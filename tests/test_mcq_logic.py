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

    def test_builds_source_backed_four_choice_questions_locally(self):
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

    def test_difficulty_changes_distractor_similarity(self):
        easy_questions = generate_question_items(
            self.records,
            6,
            rng=random.Random(7),
            difficulty="Easy",
        )
        hard_questions = generate_question_items(
            self.records,
            6,
            rng=random.Random(7),
            difficulty="Hard",
        )

        easy_ram = next(q for q in easy_questions if q["answer"] == "RAM")
        hard_ram = next(q for q in hard_questions if q["answer"] == "RAM")
        self.assertNotEqual(easy_ram["options"], hard_ram["options"])

    def test_rejects_unsupported_difficulty(self):
        with self.assertRaisesRegex(ValueError, "difficulty must be"):
            generate_question_items(self.records, 1, difficulty="Expert")

    def test_omits_near_duplicate_definition_as_distractor(self):
        near_duplicate = {
            "id": "F7",
            "concept": "Cache storage",
            "definition": self.records[2]["definition"],
            "unit": "Computer memory",
        }
        questions = generate_question_items(
            [*self.records, near_duplicate],
            7,
            rng=random.Random(7),
        )

        cache_question = next(
            q for q in questions if q["answer"] == "Cache memory"
        )
        self.assertNotIn("Cache storage", cache_question["options"])

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
