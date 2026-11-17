import re


MCQ_QUESTION_START = re.compile(
    r"^\s*(?:(?:question|q)\s*)?(\d{1,4})\s*[.):\-]\s*(\S.*)$",
    flags=re.IGNORECASE
)
MCQ_OPTION_LINE = re.compile(
    r"^\s*(?:\(([A-D1-4])\)|([A-D1-4])\s*[).:])\s*(.*?)\s*$",
    flags=re.IGNORECASE
)
MCQ_ANSWER_HEADER = re.compile(
    r"^\s*(?:answer\s*key|answers?|correct\s+answers?)\s*[:\-]?\s*(.*)$",
    flags=re.IGNORECASE
)
MCQ_INLINE_ANSWER = re.compile(
    r"^\s*(?:(?:correct\s+)?(?:answer|option)|ans(?:wer)?)\s*"
    r"(?::|is|-)\s*\(?([A-D1-4])\)?(?:\s+(?:is\s+)?correct)?[.!]?\s*$",
    flags=re.IGNORECASE
)
MCQ_ANSWER_ENTRY = re.compile(
    r"(?:\bQ(?:uestion)?\s*)?(\d{1,4})\s*[-:.)]?\s*([A-D1-4])\b",
    flags=re.IGNORECASE
)
NUMBERED_HEADING = re.compile(
    r"^\s*\d+(?:\.\d+)*(?:[.)])?\s+"
    r"[A-Z][A-Za-z0-9&/'()-]*(?:\s+[A-Z][A-Za-z0-9&/'()-]*){0,5}\s*$"
)
TABLE_OPTION_HEADER = re.compile(
    r"^(?:(?:option|choice)\s*)?([a-d1-4])(?:\s*(?:option|choice|text))?$",
    flags=re.IGNORECASE
)
TABLE_QUESTION_HEADERS = {
    "q",
    "mcq",
    "mcq question",
    "question",
    "question stem",
    "question text",
    "stem",
}
TABLE_ANSWER_HEADERS = {
    "ans",
    "answer",
    "answer key",
    "correct",
    "correct answer",
    "correct choice",
    "correct option",
}
QUESTION_LIKE_OPTION = re.compile(
    r"^\s*(?:what|why|how|which|who|when|where)\b|[?？]\s*$",
    flags=re.IGNORECASE
)
INSTRUCTION_STEM = re.compile(
    r"^\s*(?:write|answer|respond to|complete|solve)\b.*"
    r"\b(?:following|questions?)\b",
    flags=re.IGNORECASE
)


def mcq_lines_from_table(headers, rows):
    normalized_headers = [
        re.sub(r"[^a-z0-9]+", " ", str(header).casefold()).strip()
        for header in headers
    ]
    question_column = next(
        (
            index
            for index, header in enumerate(normalized_headers)
            if header in TABLE_QUESTION_HEADERS
        ),
        None
    )
    option_columns = {}
    for index, header in enumerate(normalized_headers):
        match = TABLE_OPTION_HEADER.fullmatch(header)
        if match:
            label = match.group(1).upper()
            label = chr(ord("A") + int(label) - 1) if label in "1234" else label
            option_columns[label] = index
    if (
        question_column is None
        or set(option_columns) != set("ABCD")
    ):
        return []

    answer_column = next(
        (
            index
            for index, header in enumerate(normalized_headers)
            if header in TABLE_ANSWER_HEADERS
        ),
        None
    )

    def cell_text(value):
        if value is None:
            return ""
        text = re.sub(r"\s+", " ", str(value)).strip()
        return "" if text.casefold() in {"", "nan", "none", "<na>"} else text

    def answer_label(answer, options):
        token = re.fullmatch(
            r"(?:(?:answer|option|choice)\s*[:=]?\s*)?"
            r"\(?([a-d1-4])\)?[.)]?",
            answer,
            flags=re.IGNORECASE
        )
        if token:
            label = token.group(1).upper()
            return chr(ord("A") + int(label) - 1) if label in "1234" else label
        normalized_answer = answer.casefold()
        for label, option in options.items():
            if normalized_answer == option.casefold():
                return label
        return None

    lines = []
    question_number = 0
    for row in rows:
        if question_column >= len(row):
            continue
        question = cell_text(row[question_column])
        options = {
            label: cell_text(row[column])
            for label, column in option_columns.items()
            if column < len(row)
        }
        if not question or len(options) != 4 or any(not value for value in options.values()):
            continue

        question_number += 1
        lines.append(f"{question_number}. {question}")
        lines.extend(f"{label}. {options[label]}" for label in "ABCD")

        if answer_column is not None and answer_column < len(row):
            correct_label = answer_label(cell_text(row[answer_column]), options)
            if correct_label:
                lines.append(f"Correct Answer: {correct_label}")

    return lines


def _is_section_heading(stem):
    return bool(NUMBERED_HEADING.fullmatch(stem))


def parse_mcq_source(lines):
    parsed_questions = []
    answer_key = {}
    question_text = []
    options = []
    option_labels = []
    marked_answer = None
    current_question_number = None
    current_page = None
    question_page = None
    answer_key_mode = False

    def resolve_answer_index(answer_label, current_labels):
        if answer_label is None:
            return None
        if answer_label in current_labels:
            return current_labels.index(answer_label)
        if answer_label in "ABCD":
            answer_index = ord(answer_label) - ord("A")
        elif answer_label in "1234":
            answer_index = int(answer_label) - 1
        else:
            return None
        return answer_index if answer_index < len(current_labels) else None

    def finish_question():
        nonlocal question_text, options, option_labels, marked_answer
        nonlocal current_question_number, question_page
        stem = re.sub(r"\s+", " ", " ".join(question_text)).strip()
        if (
            stem
            and not _is_section_heading(stem)
            and len(options) == 4
            and len(set(option_labels)) == 4
        ):
            question_number = len(parsed_questions) + 1
            answer_label = marked_answer or answer_key.get(
                current_question_number or question_number
            )
            answer_index = resolve_answer_index(answer_label, option_labels)
            parsed_questions.append({
                "id": question_number,
                "question": stem,
                "options": options[:],
                "option_labels": option_labels[:],
                "answer": options[answer_index] if answer_index is not None else None,
                "answer_index": answer_index,
                "source_text": "",
                "topic": "Document question",
                "option_explanations": {},
                "page": question_page,
                "unit": None,
                "unit_group": None,
                "source_location": None,
                "_source_number": current_question_number or question_number
            })
        question_text = []
        options = []
        option_labels = []
        marked_answer = None
        current_question_number = None
        question_page = None

    def add_answer_entries(text):
        for entry in MCQ_ANSWER_ENTRY.finditer(text):
            question_number = int(entry.group(1))
            answer_key[question_number] = entry.group(2).upper()

    for raw_line in lines:
        if isinstance(raw_line, dict):
            line = re.sub(r"\s+", " ", str(raw_line.get("text", ""))).strip()
            current_page = raw_line.get("page")
        else:
            line = re.sub(r"\s+", " ", str(raw_line)).strip()
            current_page = None
        if not line:
            continue

        inline_answer = MCQ_INLINE_ANSWER.match(line)
        if inline_answer and question_text and len(options) == 4:
            marked_answer = inline_answer.group(1).upper()
            continue

        answer_header = MCQ_ANSWER_HEADER.match(line)
        if answer_header:
            finish_question()
            answer_key_mode = True
            line = answer_header.group(1).strip()
            if not line:
                continue

        answer_entries = list(MCQ_ANSWER_ENTRY.finditer(line))
        if answer_key_mode and answer_entries:
            add_answer_entries(line)
            continue

        question_match = MCQ_QUESTION_START.match(line)
        option_match = MCQ_OPTION_LINE.match(line)
        numeric_option_is_expected = False
        if option_match:
            numeric_label = (option_match.group(1) or option_match.group(2)).upper()
            if numeric_label in "1234" and question_text:
                numeric_option_is_expected = (
                    (not option_labels and numeric_label == "1")
                    or (
                        option_labels
                        and option_labels[0] in "1234"
                        and int(numeric_label) == len(options) + 1
                    )
                )
        if question_match and not numeric_option_is_expected:
            if options or question_text:
                finish_question()
            current_question_number = int(question_match.group(1))
            question_page = current_page
            question_text.append(question_match.group(2))
            continue

        if option_match:
            label = (option_match.group(1) or option_match.group(2)).upper()
            if options and (len(options) == 4 or label in option_labels):
                finish_question()
            option_text = option_match.group(3).strip()
            has_correct_mark = bool(
                re.search(r"(?:\*|✓|✔|\[correct\]|\(correct\))\s*$", option_text, re.I)
                or re.match(r"^(?:✓|✔|\*|\[correct\]|\(correct\))\s*", option_text, re.I)
            )
            option_text = re.sub(
                r"^(?:✓|✔|\*|\[correct\]|\(correct\))\s*|\s*(?:\*|✓|✔|\[correct\]|\(correct\))$",
                "",
                option_text,
                flags=re.IGNORECASE
            ).strip()
            if option_text:
                if has_correct_mark:
                    marked_answer = label
                options.append(option_text)
                option_labels.append(label)
            continue

        if answer_key_mode:
            if answer_entries:
                add_answer_entries(line)
            continue

        if len(options) == 4:
            finish_question()
        if options:
            options[-1] = f"{options[-1]} {line}".strip()
        else:
            question_text.append(line)

    finish_question()
    for question in parsed_questions:
        source_number = question.pop("_source_number")
        if question["answer_index"] is None:
            answer_index = resolve_answer_index(
                answer_key.get(source_number),
                question["option_labels"],
            )
            question["answer_index"] = answer_index
            if answer_index is not None:
                question["answer"] = question["options"][answer_index]
    return parsed_questions


def select_answered_mcqs(questions, num_questions):
    answered_questions = [
        question
        for question in questions
        if isinstance(question.get("answer"), str)
        and question["answer"] in question.get("options", [])
        and len(question.get("options", [])) == 4
        and not INSTRUCTION_STEM.match(str(question.get("question", "")))
        and not any(
            not isinstance(option, str)
            or QUESTION_LIKE_OPTION.search(option)
            for option in question["options"]
        )
    ]
    return answered_questions[:num_questions]
