import re


SUBJECT_VERBS = (
    "is", "are", "was", "were", "refers to", "means", "denotes",
    "describes", "consists of", "includes", "contains", "comprises",
    "uses", "allows", "enables", "produces", "converts", "calculates",
    "measures", "represents", "represent", "requires", "has", "have",
    "provides", "stores", "occurs", "takes", "follows", "forms",
    "results in", "determines", "controls", "performs", "supports",
    "creates", "transfers", "transmits", "divides", "classifies",
    "indicates", "translates", "translate", "locates", "locate",
    "examines", "examine", "organizes", "organize", "identifies",
    "identify", "repeats", "repeat", "groups", "group", "evaluates",
    "evaluate", "executes", "execute", "defines", "define", "manages",
    "manage", "follow", "connects", "connect", "store", "builds",
    "build", "assembles", "assemble", "transforms", "transform",
    "classify", "use", "processes", "process", "communicates",
    "communicate", "accepts", "accept", "sends", "send", "receives",
    "receive", "displays", "display", "prints", "print", "reads", "read",
    "writes", "write", "operates", "operate",
)

INVALID_CONCEPT_STARTS = {
    "all", "any", "ask", "both", "check", "do", "does", "each",
    "enlisting", "explain", "few", "he", "here", "how", "if",
    "important", "it", "many", "most", "my", "our", "remember",
    "several", "she", "some", "students", "that", "these", "they",
    "this", "those", "there", "we", "what", "when", "where", "which",
    "who", "why", "you", "your",
}

NON_DEFINITION_STARTS = (
    "ask students", "check whether", "explain why", "remember:", "do not ",
    "don't ", "what is ", "what are ", "which of ", "why is ", "why are ",
)


def is_readable_source_text(text):
    if not isinstance(text, str) or not text.strip():
        return False
    return not re.search(r"[\[\]<>�]|(?<=[A-Za-z])=(?=[A-Za-z])", text)


def extract_exam_facts(source_lines):
    facts = []
    for source_line in source_lines:
        if source_line.get("is_heading", False):
            continue

        text = re.sub(r"\s+", " ", source_line["text"]).strip()
        text = re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+|[•*-]\s*)", "", text)
        if (
            not is_readable_source_text(text)
            or re.search(r"\.{3,}|_{3,}|…{2,}", text)
            or len(re.findall(r"\b\d+(?:\.\d+)+\s+[A-Z]", text)) > 1
            or text.count("+") > 1
        ):
            continue

        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        for sentence in sentences:
            sentence = sentence.strip(" \t\r\n•*-")
            lowered = sentence.casefold()
            if (
                not is_readable_source_text(sentence)
                or "?" in sentence
                or any(lowered.startswith(prefix) for prefix in NON_DEFINITION_STARTS)
                or re.search(
                    r"\b(?:examples?|for example|for instance)\b|"
                    r"\be\.g\.(?:\s|$)|"
                    r"\b(?:fig(?:ure)?\.?\s*\d+|fig\.|table\s+\d+|"
                    r"diagram|illustration)\b|"
                    r"\bsee\s+(?:fig(?:ure)?|table)|"
                    r"\bshown\s+in\s+(?:fig(?:ure)?|table)\b",
                    sentence,
                    flags=re.IGNORECASE
                )
                or len(re.findall(r"\b(?:and|or)\b", sentence, flags=re.IGNORECASE)) > 2
            ):
                continue
            words = re.findall(r"[A-Za-z][A-Za-z'-]*", sentence)
            if (
                len(words) < 9
                or len(words) > 55
                or len(sentence) < 55
                or not sentence[0].isalpha()
                or sum(character.isalpha() for character in sentence) / len(sentence) < 0.65
            ):
                continue

            lowered = sentence.casefold()
            if not any(
                re.search(rf"\b{re.escape(verb)}\b", lowered)
                for verb in SUBJECT_VERBS
            ):
                continue

            fact = dict(source_line)
            fact["text"] = sentence
            fact["topic"] = extract_fact_topic(sentence)
            if (
                not fact["topic"]
                or re.match(
                    r"^(?:examples?|figures?|fig\.?|tables?|diagrams?|"
                    r"illustrations?|the following|some examples|types of)\b",
                    fact["topic"],
                    flags=re.IGNORECASE
                )
                or len(re.findall(r",|\band\b|\bor\b", fact["topic"], flags=re.IGNORECASE)) > 1
                or not is_valid_concept_label(fact["topic"])
                or not definition_fragment(fact)
            ):
                continue
            fact["normalized"] = re.sub(r"\W+", " ", sentence).strip().casefold()
            facts.append(fact)

    return facts


def extract_fact_topic(sentence):
    subject_pattern = "|".join(
        sorted((re.escape(verb) for verb in SUBJECT_VERBS), key=len, reverse=True)
    )
    match = re.search(rf"\b(?:{subject_pattern})\b", sentence, flags=re.IGNORECASE)
    if match is None:
        return None

    subject = sentence[:match.start()].strip(" ,:;.-")
    subject = re.sub(r"^(?:in|for|on|the|a|an)\s+", "", subject, flags=re.IGNORECASE)
    subject = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", subject)
    subject = re.sub(
        r"\b(?:temporarily|repeatedly|usually|generally|often|primarily|"
        r"mainly|simply|typically|uniquely|automatically|efficiently|"
        r"quickly|directly|individually|sequentially|successfully|"
        r"continuously)\b",
        "",
        subject,
        flags=re.IGNORECASE
    ).strip()
    subject_words = subject.split()
    if not subject_words or len(subject_words) > 5:
        return None
    return subject[:1].upper() + subject[1:]


def is_valid_concept_label(topic):
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", topic)
    if not words or len(words) > 5:
        return False
    if not is_readable_source_text(topic):
        return False
    if sum(len(word) > 1 and word.isupper() for word in words) > 1:
        return False
    if words[0].casefold() in INVALID_CONCEPT_STARTS:
        return False
    if words[-1].casefold() in {
        "a", "an", "are", "as", "at", "be", "can", "for", "from", "in",
        "is", "of", "on", "or", "should", "the", "to", "was", "were", "will"
    }:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,4}", topic))


def definition_fragment(fact):
    sentence = fact["text"].strip()
    if not is_readable_source_text(sentence):
        return None
    topic = fact["topic"]
    subject_match = re.match(
        rf"^\s*(?:(?:a|an|the)\s+)?{re.escape(topic)}\b",
        sentence,
        flags=re.IGNORECASE
    )
    if subject_match is None:
        return None

    predicate = sentence[subject_match.end():].strip(" \t,;:-")
    relation = re.match(
        r"^(?:(?:is|are|was|were)\s+defined\s+as\s+|"
        r"(?:is|are|was|were)\s+|"
        r"(?:means|refers\s+to|denotes)\s+)",
        predicate,
        flags=re.IGNORECASE
    )
    if relation is not None:
        definition = predicate[relation.end():].strip(" \t,;:-")
    else:
        action_verbs = {
            verb for verb in SUBJECT_VERBS
            if verb not in {
                "is", "are", "was", "were", "means", "refers to",
                "denotes", "consists of", "results in"
            }
        }
        action_pattern = "|".join(
            sorted((re.escape(verb) for verb in action_verbs), key=len, reverse=True)
        )
        action = re.match(
            rf"^(?:{action_pattern})\b",
            predicate,
            flags=re.IGNORECASE
        )
        if action is None:
            return None
        definition = predicate.strip(" \t,;:-")
    definition = re.split(
        r"\s*,?\s*(?:such as|for example|for instance)\b",
        definition,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0].strip(" \t,;:-")
    if re.match(r"^(?:the\s+)?name\s+of\b", definition, flags=re.IGNORECASE):
        return None
    if len(re.findall(r"[A-Za-z][A-Za-z'-]*", definition)) < 5:
        return None
    return definition.rstrip(".!?")
