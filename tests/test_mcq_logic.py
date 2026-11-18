import random
import unittest

from mcq_logic import (
    build_concept_map,
    generate_question_items,
    generate_short_answer_items,
    resolve_generation_preferences,
)
from source_facts import extract_exam_facts


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

        self.assertEqual(len(questions), 4)
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
        self.assertIn("store data", ram["question"])
        self.assertEqual(ram["question_type"], "function")

    def test_compound_function_question_preserves_verb_agreement(self):
        target = {
            "id": "B1",
            "concept": "Back-end",
            "definition": (
                "processes requests and manages data on a hosting server"
            ),
            "unit": "Web development",
        }
        distractors = [
            {
                "id": "D1",
                "concept": "Website",
                "definition": (
                    "collection of related webpages hosted on a web server"
                ),
                "unit": "Web development",
            },
            {
                "id": "D2",
                "concept": "Database",
                "definition": (
                    "organized collection of data stored and retrieved "
                    "by a server"
                ),
                "unit": "Web development",
            },
            {
                "id": "D3",
                "concept": "Web server",
                "definition": (
                    "computer that stores and delivers webpages to users"
                ),
                "unit": "Web development",
            },
        ]

        questions = generate_question_items(
            [target],
            1,
            distractor_records=distractors,
            rng=random.Random(3),
        )

        self.assertEqual(len(questions), 1)
        self.assertIn(
            "processes requests and manages data",
            questions[0]["question"],
        )
        self.assertNotIn(
            "to process requests and manages data",
            questions[0]["question"],
        )

    def test_question_style_changes_generated_stems(self):
        questions = {
            style: generate_question_items(
                self.records,
                6,
                rng=random.Random(1),
                question_style=style,
            )
            for style in ("Balanced", "Direct recall", "Conceptual", "FBISE-style")
        }

        self.assertIn(
            "description",
            next(q for q in questions["Direct recall"] if q["answer"] == "RAM")["question"],
        )
        self.assertIn(
            "store",
            next(q for q in questions["Conceptual"] if q["answer"] == "RAM")["question"],
        )
        self.assertIn(
            "store",
            next(q for q in questions["FBISE-style"] if q["answer"] == "RAM")["question"],
        )

    def test_custom_prompt_overrides_supported_style_and_difficulty(self):
        preferences = resolve_generation_preferences(
            "Balanced",
            "Create challenging application questions.",
            "Easy",
        )

        self.assertEqual(preferences["question_style"], "FBISE-style")
        self.assertEqual(preferences["difficulty"], "Hard")
        self.assertTrue(preferences["recognized"])

    def test_unsupported_custom_prompt_preserves_selected_controls(self):
        preferences = resolve_generation_preferences(
            "Conceptual",
            "Add a fun fact after each question.",
            "Medium",
        )

        self.assertEqual(preferences["question_style"], "Conceptual")
        self.assertEqual(preferences["difficulty"], "Medium")
        self.assertFalse(preferences["recognized"])

    def test_conflicting_custom_prompt_preserves_selected_controls(self):
        preferences = resolve_generation_preferences(
            "Balanced",
            "Make questions easy and challenging.",
            "Medium",
        )

        self.assertEqual(preferences["question_style"], "Balanced")
        self.assertEqual(preferences["difficulty"], "Medium")
        self.assertTrue(preferences["conflict"])

    def test_memory_question_uses_same_topic_as_its_distractors(self):
        questions = generate_question_items(
            self.records,
            6,
            rng=random.Random(7),
        )

        ram = next(question for question in questions if question["answer"] == "RAM")
        memory_concepts = {"RAM", "ROM", "Cache memory", "Virtual memory"}
        self.assertTrue(set(ram["options"]).issubset(memory_concepts))

    def test_conceptual_stem_frames_the_source_fact_as_a_task(self):
        questions = generate_question_items(
            self.records,
            6,
            rng=random.Random(1),
            question_style="Conceptual",
        )

        ram = next(question for question in questions if question["answer"] == "RAM")
        self.assertIn("store", ram["question"])
        self.assertIn("concept", ram["question"].casefold())
        self.assertNotIn("RAM", ram["question"])

    def test_same_concept_can_produce_different_question_stems(self):
        question_stems = {
            generate_question_items(
                [self.records[0]],
                1,
                distractor_records=self.records[1:4],
                rng=random.Random(seed),
            )[0]["question"]
            for seed in range(12)
        }

        self.assertGreaterEqual(len(question_stems), 3)

    def test_concept_map_links_source_concepts_by_unit_and_meaning(self):
        unrelated_record = {
            "id": "F7",
            "concept": "Water cycle",
            "definition": (
                "natural process that circulates water through the "
                "atmosphere and oceans"
            ),
            "unit": "Geography",
        }
        concept_map = build_concept_map([*self.records, unrelated_record])

        ram_neighbors = {
            item["concept"] for item in concept_map["F1"]
        }

        self.assertIn("ROM", ram_neighbors)
        self.assertIn("Cache memory", ram_neighbors)
        self.assertIn("Virtual memory", ram_neighbors)
        self.assertNotIn("Water cycle", ram_neighbors)

    def test_distractor_concepts_do_not_repeat_when_a_large_pool_is_available(self):
        labels = [
            "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
            "Golf", "Hotel", "India", "Juliett", "Kilo", "Lima", "Mike",
            "November", "Oscar", "Papa", "Quebec", "Romeo", "Sierra",
            "Tango", "Uniform", "Victor", "Whiskey", "Xray",
        ]
        records = [
            {
                "id": f"M{index}",
                "concept": f"Memory concept {label}",
                "definition": (
                    f"memory method {label} handles a distinct computer task "
                    f"using separate hardware resources for the {label} context"
                ),
                "unit": "Computer memory",
            }
            for index, label in enumerate(labels)
        ]

        questions = generate_question_items(
            records,
            5,
            rng=random.Random(9),
        )
        all_options = [
            option
            for question in questions
            for option in question["options"]
        ]
        distractors = [
            option
            for question in questions
            for option in question["options"]
            if option != question["answer"]
        ]

        self.assertEqual(len(questions), 5)
        self.assertEqual(len(distractors), 15)
        self.assertEqual(
            len({option.casefold() for option in distractors}),
            len(distractors),
        )
        self.assertEqual(
            len({option.casefold() for option in all_options}),
            len(all_options),
        )

    def test_omits_question_when_three_related_distractors_are_unavailable(self):
        target = {
            "id": "T1",
            "concept": "Cache memory",
            "definition": (
                "small high-speed memory that stores frequently used data "
                "near the processor"
            ),
        }
        unrelated_records = [
            {
                "id": "U1",
                "concept": "Water cycle",
                "definition": (
                    "natural process that circulates water through the "
                    "atmosphere and oceans"
                ),
            },
            {
                "id": "U2",
                "concept": "Rock formation",
                "definition": (
                    "geological process that creates layers of sediment "
                    "over long periods"
                ),
            },
            {
                "id": "U3",
                "concept": "Musical rhythm",
                "definition": (
                    "pattern that organizes beats and accents in a musical "
                    "composition"
                ),
            },
        ]

        questions = generate_question_items(
            [target],
            1,
            distractor_records=unrelated_records,
            rng=random.Random(3),
        )

        self.assertEqual(questions, [])

    def test_does_not_use_same_unit_as_the_only_distractor_relationship(self):
        target = {
            "id": "W1",
            "concept": "Webpage",
            "definition": "document accessible through an internet connection",
            "unit": "Web development",
        }
        unrelated_records = [
            {
                "id": "U1",
                "concept": "Installer",
                "definition": "executable program launched to install software",
                "unit": "Web development",
            },
            {
                "id": "U2",
                "concept": "Numbered list",
                "definition": "ordered sequence that displays numerals and letters",
                "unit": "Web development",
            },
            {
                "id": "U3",
                "concept": "Point to note",
                "definition": "reminder that highlights an important instruction",
                "unit": "Web development",
            },
        ]

        questions = generate_question_items(
            [target],
            1,
            distractor_records=unrelated_records,
            rng=random.Random(3),
        )

        self.assertEqual(questions, [])

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

    def test_rejects_unsupported_question_style(self):
        with self.assertRaisesRegex(ValueError, "question_style must be"):
            generate_question_items(
                self.records,
                1,
                question_style="Unrecognized",
            )

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

    def test_builds_short_answers_from_source_definition_and_function_facts(self):
        source_lines = [
            {
                "text": (
                    "RAM is temporary memory used to store data and programs "
                    "currently being processed by a computer."
                ),
                "page": 2,
                "unit": "Computer memory",
            },
            {
                "text": (
                    "The CPU processes instructions and controls operations "
                    "in a computer system to execute programs."
                ),
                "page": 3,
                "unit": "Computer hardware",
            },
        ]
        facts = extract_exam_facts(source_lines)

        questions = generate_short_answer_items(facts, 5)

        self.assertEqual(len(questions), 2)
        ram = next(question for question in questions if question["topic"] == "RAM")
        cpu = next(question for question in questions if question["topic"] == "CPU")
        self.assertEqual(ram["question"], "What is RAM?")
        self.assertIn("temporary memory", ram["answer"])
        self.assertEqual(cpu["question"], "What does CPU do?")
        self.assertIn("processes instructions", cpu["answer"])
        self.assertEqual(ram["page"], 2)


if __name__ == "__main__":
    unittest.main()
