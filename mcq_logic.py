import math
import random
import re

from source_facts import is_readable_source_text, is_valid_concept_label


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

_QUESTION_TEMPLATES = (
    "Which concept is described as “{definition}”?",
    "According to the source, which concept matches this description: “{definition}”?",
    "The material describes one concept as “{definition}”. Which term is it?",
    "What term in the material corresponds to this description: “{definition}”?",
)


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


def _question_for(record, index):
    definition = re.sub(r"\s+", " ", record["definition"]).strip().rstrip(".!?")
    for pattern, fixed_verb in _ACTION_PATTERNS:
        match = pattern.search(definition)
        if not match:
            continue
        if fixed_verb:
            action = f"{fixed_verb} {match.group(1).rstrip('.!?')}"
        else:
            verb, rest = match.groups()
            action = f"{verb.casefold()} {rest.rstrip('.!?')}"
        if index % 3 == 2:
            return f"The source describes a concept that {action}. Which one is it?"
        prefix = "Which concept" if index % 3 == 0 else "Which concept in the material"
        return f"{prefix} {action}?"
    template = _QUESTION_TEMPLATES[index % len(_QUESTION_TEMPLATES)]
    return template.format(definition=definition)


def generate_question_items(
    records,
    num_questions,
    distractor_records=None,
    rng=None,
):
    """Build source-grounded questions with related, document-derived distractors."""
    rng = rng or random
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

    token_sets = {
        record["id"]: _tokens(
            f"{record['concept']} {record['definition']}"
        )
        for record in usable_records
    }
    document_frequency = {}
    for tokens in token_sets.values():
        for token in tokens:
            document_frequency[token] = document_frequency.get(token, 0) + 1
    total_records = len(usable_records)
    inverse_frequency = {
        token: math.log(1 + total_records / (1 + frequency))
        for token, frequency in document_frequency.items()
    }

    target_ids = {record["id"] for record in target_records}
    shuffled_targets = [
        record for record in usable_records
        if record["id"] in target_ids
    ]
    rng.shuffle(shuffled_targets)
    questions = []
    distractor_usage = {}
    max_reuse = max(
        3,
        math.ceil((num_questions * 3) / max(1, total_records - 1)) + 1,
    )

    for target in shuffled_targets:
        target_tokens = token_sets[target["id"]]
        ranked_distractors = []
        for alternative in usable_records:
            if alternative["id"] == target["id"]:
                continue
            similarity = _cosine_similarity(
                target_tokens,
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
            label_overlap = bool(
                _tokens(target["concept"]) & _tokens(alternative["concept"])
            )
            score = similarity + (0.12 if same_unit else 0.0)
            score += 0.08 if label_overlap else 0.0
            if similarity > 0.88:
                score -= (similarity - 0.88) * 2
            ranked_distractors.append(
                (score, alternative["concept"].casefold(), alternative)
            )

        ranked_distractors.sort(key=lambda item: (-item[0], item[1]))
        available = [
            item[2] for item in ranked_distractors
            if distractor_usage.get(item[2]["concept"].casefold(), 0) < max_reuse
        ]
        if len(available) < 3:
            available = [item[2] for item in ranked_distractors]
        distractors = available[:3]
        if len({item["concept"].casefold() for item in distractors}) < 3:
            continue

        options = [target["concept"], *(item["concept"] for item in distractors)]
        rng.shuffle(options)
        definition = target["definition"].casefold()
        question_type = (
            "function"
            if any(pattern.search(definition) for pattern, _ in _ACTION_PATTERNS)
            else "distinction"
        )
        questions.append({
            "source_fact_id": target["id"],
            "question": _question_for(target, len(questions)),
            "question_type": question_type,
            "options": options,
            "answer": target["concept"],
        })
        for distractor in distractors:
            key = distractor["concept"].casefold()
            distractor_usage[key] = distractor_usage.get(key, 0) + 1
        if len(questions) >= num_questions:
            break
    return questions
