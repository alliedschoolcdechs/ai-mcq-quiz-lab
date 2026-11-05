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
MCQ_ANSWER_ENTRY = re.compile(
    r"(?:\bQ(?:uestion)?\s*)?(\d{1,4})\s*[-:.)]?\s*([A-D1-4])\b",
    flags=re.IGNORECASE
)
NUMBERED_HEADING = re.compile(
    r"^\s*\d+(?:\.\d+)*(?:[.)])?\s+"
    r"[A-Z][A-Za-z0-9&/'()-]*(?:\s+[A-Z][A-Za-z0-9&/'()-]*){0,5}\s*$"
)


def _is_section_heading(stem):
    return bool(NUMBERED_HEADING.fullmatch(stem))


def parse_imported_mcqs(lines):
    parsed_questions = []
    answer_key = {}
    question_text = []
    options = []
    option_labels = []
    marked_answer = None
    current_question_number = None
    answer_key_mode = False

    def finish_question():
        nonlocal question_text, options, option_labels, marked_answer
        nonlocal current_question_number
        stem = re.sub(r"\s+", " ", " ".join(question_text)).strip()
        if (
            stem
            and not _is_section_heading(stem)
            and len(options) == 4
            and len(set(option_labels)) == 4
        ):
            question_number = len(parsed_questions) + 1
            correct_index = marked_answer
            if correct_index is None:
                answer_label = answer_key.get(
                    current_question_number or question_number
                )
                if answer_label is not None:
                    correct_index = answer_label
            answer = options[correct_index] if correct_index in range(4) else None
            parsed_questions.append({
                "id": question_number,
                "question": stem,
                "options": options[:],
                "answer": answer,
                "source_text": "",
                "topic": "Imported question",
                "option_explanations": {},
                "page": None,
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

    def add_answer_entries(text):
        for entry in MCQ_ANSWER_ENTRY.finditer(text):
            question_number = int(entry.group(1))
            answer_token = entry.group(2).upper()
            answer_key[question_number] = (
                ord(answer_token) - ord("A")
                if answer_token in "ABCD"
                else int(answer_token) - 1
            )

    for raw_line in lines:
        line = re.sub(r"\s+", " ", str(raw_line)).strip()
        if not line:
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
            question_text.append(question_match.group(2))
            continue

        if option_match:
            label = (option_match.group(1) or option_match.group(2)).upper()
            label_index = (
                ord(label) - ord("A") if label in "ABCD" else int(label) - 1
            )
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
                    marked_answer = label_index
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
        if question["answer"] is not None:
            question.pop("_source_number", None)
            continue
        answer_index = answer_key.get(question.pop("_source_number"))
        if answer_index in range(4):
            question["answer"] = question["options"][answer_index]
    return parsed_questions
