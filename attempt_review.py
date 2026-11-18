import html


def escape_question_html(question):
    return html.escape(str(question))


def question_option_labels(question):
    options = question.get("options")
    if not isinstance(options, list):
        return []
    labels = question.get("option_labels")
    if not isinstance(labels, list) or len(labels) != len(options):
        return list("ABCD"[:len(options)])
    return list(labels)


def attempt_option_lines(options, option_labels, selected_answer, correct_answer):
    if not isinstance(options, list):
        return []
    labels = (
        option_labels
        if isinstance(option_labels, list) and len(option_labels) == len(options)
        else list("ABCD"[:len(options)])
    )
    lines = []
    for label, option in zip(labels, options):
        annotations = []
        if option == selected_answer:
            annotations.append("Your answer")
        if option == correct_answer:
            annotations.append("Correct answer")
        suffix = f" ({'; '.join(annotations)})" if annotations else ""
        lines.append(f"{label}. {option}{suffix}")
    return lines


def training_feedback(question, selected_answer):
    correct_answer = question.get("answer")
    explanation = question.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        option_explanations = question.get("option_explanations")
        explanation = (
            option_explanations.get(correct_answer)
            if isinstance(option_explanations, dict)
            else None
        )
    if not isinstance(explanation, str) or not explanation.strip():
        explanation = (
            f"The document's answer key marks {correct_answer} as correct, "
            "but it does not include an explanation."
        )
    return {
        "is_correct": selected_answer == correct_answer,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }
