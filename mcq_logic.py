import math
import random
import re

from source_facts import (
    definition_fragment,
    is_readable_source_text,
    is_valid_concept_label,
)


_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been",
    "before", "being", "between", "both", "but", "can", "could", "does",
    "each", "for", "from", "has", "have", "into", "its", "may", "more",
    "most", "not", "of", "often", "on", "or", "other", "our", "over",
    "same", "should", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through",
    "to", "under", "used", "using", "was", "were", "which", "while",
    "with", "would",
}

_ACTION_PATTERNS = (
    (re.compile(r"\bused\s+to\s+(.+)$", re.IGNORECASE), "is used to"),
    (re.compile(r"\b(allows|enables|helps|stores|converts|calculates|"
                r"measures|represents|provides|produces|transfers|"
                r"transmits|controls|supports|creates|identifies|"
                r"classifies|connects|manages|executes|processes|"
                r"communicates|accepts|sends|receives|displays|prints|"
                r"reads|writes|operates|uses|requires|performs|"
                r"determines|indicates|translates|locates|examines|"
                r"organizes|repeats|groups|evaluates|defines|builds|"
                r"assembles|transforms)\s+(.+)$", re.IGNORECASE),
     None),
    (re.compile(r"\b(?:is|are)\s+responsible\s+for\s+(.+)$", re.IGNORECASE),
     "is responsible for"),
)
_SCENARIO_VERBS = {
    "accepts": "accept",
    "allows": "allow",
    "builds": "build",
    "calculates": "calculate",
    "classifies": "classify",
    "communicates": "communicate",
    "connects": "connect",
    "controls": "control",
    "creates": "create",
    "defines": "define",
    "determines": "determine",
    "displays": "display",
    "enables": "enable",
    "evaluates": "evaluate",
    "executes": "execute",
    "examines": "examine",
    "groups": "group",
    "identifies": "identify",
    "indicates": "indicate",
    "locates": "locate",
    "manages": "manage",
    "measures": "measure",
    "operates": "operate",
    "performs": "perform",
    "prints": "print",
    "processes": "process",
    "provides": "provide",
    "reads": "read",
    "receives": "receive",
    "repeats": "repeat",
    "sends": "send",
    "stores": "store",
    "supports": "support",
    "transforms": "transform",
    "translates": "translate",
    "transmits": "transmit",
    "transfers": "transfer",
    "uses": "use",
    "writes": "write",
}
_SCENARIO_VERBS.update(
    {verb: verb for verb in set(_SCENARIO_VERBS.values())}
)
_SCENARIO_ACTION_PATTERNS = (
    re.compile(r"\bused to\s+([a-z]+)\s+(.+)$", re.IGNORECASE),
    re.compile(r"\b(?:that|which)\s+([a-z]+)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\s*([a-z]+)\s+(.+)$", re.IGNORECASE),
)

QUESTION_STYLES = (
    "Balanced",
    "Direct recall",
    "Conceptual",
    "FBISE-style",
)


def resolve_generation_preferences(template, custom_prompt, difficulty):
    """Apply supported style and difficulty keywords to local generation."""
    if template not in QUESTION_STYLES:
        raise ValueError("template must be a supported question style")
    if str(difficulty).casefold() not in {"easy", "medium", "hard"}:
        raise ValueError("difficulty must be Easy, Medium, or Hard")

    question_style = template
    resolved_difficulty = difficulty
    prompt = str(custom_prompt or "").casefold()
    style_patterns = {
        "Direct recall": r"\b(recall|definition|direct)\b",
        "Conceptual": r"\b(conceptual|understanding|reasoning|explain)\b",
        "FBISE-style": r"\b(fbise|application|scenario|practical)\b",
    }
    difficulty_patterns = {
        "Easy": r"\b(easy|simple|basic|beginner)\b",
        "Medium": r"\b(medium|moderate|balanced)\b",
        "Hard": r"\b(hard|challenging|difficult|advanced)\b",
    }
    matched_styles = [
        style for style, pattern in style_patterns.items()
        if re.search(pattern, prompt)
    ]
    matched_difficulties = [
        level for level, pattern in difficulty_patterns.items()
        if re.search(pattern, prompt)
    ]

    conflict = len(matched_styles) > 1 or len(matched_difficulties) > 1
    if not conflict:
        if matched_styles:
            question_style = matched_styles[0]
        if matched_difficulties:
            resolved_difficulty = matched_difficulties[0]
    return {
        "question_style": question_style,
        "difficulty": resolved_difficulty,
        "recognized": bool(matched_styles or matched_difficulties) and not conflict,
        "conflict": conflict,
    }


def _normalize_token(token):
    token = token.casefold()
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith(("ing", "ed")):
        token = token[:-3]
        if len(token) > 3 and token[-1] == token[-2]:
            token = token[:-1]
    elif len(token) > 4 and token.endswith("es"):
        token = token[:-2]
    elif len(token) > 3 and token.endswith("s"):
        token = token[:-1]
    return token


def _tokens(text):
    return {
        normalized
        for token in re.findall(r"[A-Za-z][A-Za-z'-]*", text)
        if (normalized := _normalize_token(token)) not in _STOP_WORDS
        and len(normalized) > 2
    }


def _cosine_similarity(left, right, inverse_frequency):
    if not left or not right:
        return 0.0
    left_weights = {
        word: inverse_frequency.get(word, 1.0)
        for word in left
    }
    right_weights = {
        word: inverse_frequency.get(word, 1.0)
        for word in right
    }
    dot_product = sum(
        weight * right_weights.get(word, 0.0)
        for word, weight in left_weights.items()
    )
    left_norm = math.sqrt(sum(weight * weight for weight in left_weights.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right_weights.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot_product / (left_norm * right_norm)


def build_concept_map(records):
    token_sets = {
        record["id"]: _tokens(
            f"{record['concept']} {record['definition']}"
        )
        for record in records
    }
    definition_token_sets = {
        record["id"]: _tokens(record["definition"])
        for record in records
    }
    document_frequency = {}
    for tokens in token_sets.values():
        for token in tokens:
            document_frequency[token] = document_frequency.get(token, 0) + 1
    total_records = len(records)
    inverse_frequency = {
        token: math.log(1 + total_records / (1 + frequency))
        for token, frequency in document_frequency.items()
    }

    concept_map = {}
    for target in records:
        related_concepts = []
        for alternative in records:
            if alternative["id"] == target["id"]:
                continue
            similarity = _cosine_similarity(
                token_sets[target["id"]],
                token_sets[alternative["id"]],
                inverse_frequency,
            )
            target_unit = target.get("unit_group") or target.get("unit")
            alternative_unit = (
                alternative.get("unit_group") or alternative.get("unit")
            )
            same_unit = bool(
                target_unit
                and alternative_unit
                and str(target_unit).casefold() == str(alternative_unit).casefold()
            )
            definition_tokens = definition_token_sets[alternative["id"]]
            target_definition_tokens = definition_token_sets[target["id"]]
            shared_definition_tokens = (
                definition_tokens & target_definition_tokens
            )
            definition_union = definition_tokens | target_definition_tokens
            definition_overlap = (
                len(shared_definition_tokens) / len(definition_union)
                if definition_union else 0.0
            )
            if definition_overlap >= 0.9 or not (same_unit or similarity >= 0.1):
                continue
            related_concepts.append({
                "concept": alternative["concept"],
                "record": alternative,
                "similarity": similarity,
                "same_unit": same_unit,
                "label_overlap": bool(
                    _tokens(target["concept"])
                    & _tokens(alternative["concept"])
                ),
            })
        concept_map[target["id"]] = related_concepts
    return concept_map


def _question_for(record, rng, question_style="Balanced"):
    definition = re.sub(r"\s+", " ", record["definition"]).strip().rstrip(".!?")
    scenario_action = None
    for pattern in _SCENARIO_ACTION_PATTERNS:
        match = pattern.search(definition)
        if match and match.group(1).casefold() in _SCENARIO_VERBS:
            scenario_action = (
                f"{_SCENARIO_VERBS[match.group(1).casefold()]} "
                f"{match.group(2).rstrip('.!?')}"
            )
            break

    if question_style == "Direct recall":
        return rng.choice((
            f"Which computer concept is described by this source fact: {definition}?",
            f"Which concept best matches this textbook description: {definition}?",
        ))
    if question_style == "Conceptual":
        if scenario_action:
            return rng.choice((
                f"A computer must {scenario_action}. Which concept provides this capability?",
                f"Which concept best supports a computer that must {scenario_action}?",
                f"If a computer needs to {scenario_action}, which concept is most relevant?",
                f"What concept would address the need to {scenario_action} in a computer?",
            ))
        return rng.choice((
            "A computer must meet this source-backed requirement: "
            f"{definition}. Which concept best fits?",
            f"Which concept would meet this computer-system requirement: {definition}?",
            f"A system has this requirement: {definition}. Which concept applies?",
        ))
    if question_style == "FBISE-style":
        if scenario_action:
            return rng.choice((
                "A computer system must "
                f"{scenario_action}. Which concept is the most suitable choice?",
                "In a system that must "
                f"{scenario_action}, which concept should be selected?",
                "A system needs to "
                f"{scenario_action}. Which concept best meets the requirement?",
            ))
        return rng.choice((
            "A computer system must meet this source-backed requirement: "
            f"{definition}. Which concept should be selected?",
            f"Which concept should a designer choose for this requirement: {definition}?",
        ))
    if scenario_action:
        return rng.choice((
            f"Which concept would a computer use to {scenario_action}?",
            f"What concept provides a computer with the ability to {scenario_action}?",
            f"A computer needs to {scenario_action}. Which concept supports this task?",
            f"Which computer concept is suited to the task of {scenario_action}?",
        ))
    for pattern, fixed_verb in _ACTION_PATTERNS:
        match = pattern.search(definition)
        if not match:
            continue
        if fixed_verb:
            action = f"{fixed_verb} {match.group(1).rstrip('.!?')}"
            return rng.choice((
                f"Which concept {action}?",
                f"What concept {action}?",
            ))
        else:
            verb, rest = match.groups()
            action = f"{verb.casefold()} {rest.rstrip('.!?')}"
            return rng.choice((
                f"Which concept {action}?",
                f"What concept {action}?",
            ))
    return rng.choice((
        f"Which concept matches this description: {definition}?",
        f"What concept is described by: {definition}?",
        f"Which source concept best fits this requirement: {definition}?",
    ))


def generate_question_items(
    records,
    num_questions,
    distractor_records=None,
    rng=None,
    difficulty="Medium",
    question_style="Balanced",
):
    """Build source-grounded questions with related, document-derived distractors."""
    rng = rng or random.SystemRandom()
    difficulty = str(difficulty).casefold()
    if difficulty not in {"easy", "medium", "hard"}:
        raise ValueError("difficulty must be Easy, Medium, or Hard")
    if question_style not in QUESTION_STYLES:
        raise ValueError("question_style must be a supported question style")
    target_records = [
        record for record in records
        if isinstance(record.get("id"), str)
        and isinstance(record.get("concept"), str)
        and isinstance(record.get("definition"), str)
        and is_valid_concept_label(record["concept"].strip())
        and is_readable_source_text(record["definition"])
        and record["definition"].strip()
    ]
    if len(target_records) < 1:
        return []

    usable_records = []
    seen_concepts = set()
    for record in target_records + list(distractor_records or []):
        if (
            not isinstance(record.get("id"), str)
            or not isinstance(record.get("concept"), str)
            or not isinstance(record.get("definition"), str)
            or not is_valid_concept_label(record["concept"].strip())
            or not is_readable_source_text(record["definition"])
            or not record["definition"].strip()
        ):
            continue
        concept_key = record["concept"].casefold()
        if concept_key in seen_concepts:
            continue
        seen_concepts.add(concept_key)
        usable_records.append(record)
    if len(usable_records) < 4:
        return []

    concept_map = build_concept_map(usable_records)

    target_ids = {record["id"] for record in target_records}
    shuffled_targets = [
        record for record in usable_records
        if record["id"] in target_ids
    ]
    rng.shuffle(shuffled_targets)
    reserved_answers = {
        record["concept"].casefold()
        for record in shuffled_targets[:num_questions]
    }
    questions = []
    distractor_usage = {}

    for target in shuffled_targets:
        ranked_distractors = []
        for relation in concept_map[target["id"]]:
            alternative = relation["record"]
            similarity = relation["similarity"]
            same_unit = relation["same_unit"]
            label_overlap = relation["label_overlap"]
            score = similarity + (0.12 if same_unit else 0.0)
            score += 0.08 if label_overlap else 0.0
            if similarity > 0.88:
                score -= (similarity - 0.88) * 2
            if difficulty == "easy":
                score = similarity - (0.12 if same_unit else 0.0)
            elif difficulty == "hard":
                score = similarity + (0.12 if same_unit else 0.0)
                score += 0.08 if label_overlap else 0.0
            ranked_distractors.append(
                (
                    score,
                    alternative["concept"].casefold(),
                    alternative,
                    same_unit,
                    similarity,
                )
            )

        ranked_distractors.sort(
            key=lambda item: (
                item[0] if difficulty == "easy" else -item[0],
                item[1],
            )
        )
        related_distractors = ranked_distractors
        if len(related_distractors) < 3:
            continue
        ranked_distractors = related_distractors

        non_answer_distractors = [
            item for item in ranked_distractors
            if item[2]["concept"].casefold() not in reserved_answers
        ]
        if len(non_answer_distractors) >= 3:
            ranked_distractors = non_answer_distractors

        unused_distractors = [
            item for item in ranked_distractors
            if distractor_usage.get(item[2]["concept"].casefold(), 0) == 0
        ]
        if len(unused_distractors) >= 3:
            selected_distractors = unused_distractors
        else:
            selected_distractors = sorted(
                ranked_distractors,
                key=lambda item: (
                    distractor_usage.get(item[2]["concept"].casefold(), 0),
                    item[0] if difficulty == "easy" else -item[0],
                    item[1],
                ),
            )
        distractors = [item[2] for item in selected_distractors[:3]]
        if len({item["concept"].casefold() for item in distractors}) < 3:
            continue

        options = [target["concept"], *(item["concept"] for item in distractors)]
        rng.shuffle(options)
        definition = target["definition"].casefold()
        question_type = (
            "function"
            if any(pattern.search(definition) for pattern, _ in _ACTION_PATTERNS)
            else "definition"
        )
        questions.append({
            "source_fact_id": target["id"],
            "question": _question_for(target, rng, question_style),
            "question_type": question_type,
            "options": options,
            "answer": target["concept"],
            "concept_tested": target["concept"],
            "correct_answer_index": options.index(target["concept"]),
            "explanation": (
                f"{target['concept']} is correct because the source states that "
                f"{target['definition'].rstrip('.!?')}. The other choices describe "
                "different concepts: "
                + "; ".join(
                    f"{item['concept']} {item['definition'].rstrip('.!?')}"
                    for item in distractors
                )
                + "."
            ),
        })
        for distractor in distractors:
            key = distractor["concept"].casefold()
            distractor_usage[key] = distractor_usage.get(key, 0) + 1
        if len(questions) >= num_questions:
            break
    return questions


def generate_short_answer_items(facts, num_questions):
    """Create concise, source-grounded short-answer questions from extracted facts."""
    questions = []
    seen = set()
    for fact in facts:
        topic = fact.get("topic")
        text = fact.get("text")
        answer = definition_fragment(fact)
        if not isinstance(topic, str) or not isinstance(text, str) or not answer:
            continue

        subject_match = re.match(
            rf"^\s*(?:(?:a|an|the)\s+)?{re.escape(topic)}\b\s*",
            text,
            flags=re.IGNORECASE,
        )
        if subject_match is None:
            continue

        predicate = text[subject_match.end():].strip(" \t,;:-")
        if re.match(r"^(?:means)\b", predicate, flags=re.IGNORECASE):
            question = f"What does {topic} mean?"
        elif re.match(r"^(?:refers\s+to)\b", predicate, flags=re.IGNORECASE):
            question = f"What does {topic} refer to?"
        elif re.match(r"^(?:is|are|was|were)\b", predicate, flags=re.IGNORECASE):
            question = f"What is {topic}?"
        else:
            question = f"What does {topic} do?"

        identity = (question.casefold(), answer.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        questions.append({
            "question": question,
            "answer": answer,
            "topic": topic,
            "source_text": text,
            "page": fact.get("page"),
            "unit": fact.get("unit"),
            "unit_group": fact.get("unit_group"),
        })
        if len(questions) >= num_questions:
            break
    return questions
