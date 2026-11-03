import os
import io
import html
import random
import re
import shutil
import pandas as pd
import streamlit as st
from fpdf import FPDF
import requests

# Document parsing libraries
import pypdf
from docx import Document

# Page Config
st.set_page_config(
    page_title="AI MCQ Generator & Quiz Lab",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for a dark theme and animated quiz questions
st.markdown("""
<style>
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(-8px); }
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"] {
        background-color: #0e1117;
        color: #f0f2f6;
    }
    [data-testid="stSidebar"] {
        background-color: #161b22;
    }
    .fade-in-card {
        animation: fadeIn 0.45s ease-out both;
        background-color: #1b2533;
        color: #f0f2f6;
        border: 1px solid #344256;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    [class*="st-key-answer_card_"] {
        animation: fadeIn 0.4s ease-out both;
    }
    [class*="st-key-answer_card_"] button {
        width: 100%;
        min-height: 3.5rem;
        text-align: left;
        white-space: normal;
        border: 1px solid #344256;
        border-radius: 12px;
        background-color: #1b2533;
        color: #f0f2f6;
        transition: transform 160ms ease, border-color 160ms ease, background-color 160ms ease;
    }
    [class*="st-key-answer_card_"] button:hover {
        transform: scale(1.015);
        border-color: #60a5fa;
        background-color: #243449;
        color: #ffffff;
    }
    [class*="st-key-answer_card_selected_"] button,
    [class*="st-key-answer_card_selected_"] button:hover {
        background-color: #14532d !important;
        border: 2px solid #4ade80 !important;
        color: #f0fdf4 !important;
        font-weight: 700 !important;
    }
    .stApp:has([class*="st-key-next_question_button_"] button:active) [class*="st-key-answer_card_"] {
        animation: fadeOut 0.25s ease-in both;
    }
    .fade-in-card h3,
    .fade-in-card p,
    [data-testid="stWidgetLabel"] p {
        color: #f0f2f6 !important;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
    [data-testid="stProgress"] > div > div {
        background-color: #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# INITIALIZE SESSION STATE
# ==========================================
if "app_state" not in st.session_state:
    st.session_state.app_state = "upload"
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "score_data" not in st.session_state:
    st.session_state.score_data = {}
if "generation_notice" not in st.session_state:
    st.session_state.generation_notice = None

# ==========================================
# DOCUMENT TEXT EXTRACTOR
# ==========================================
def parse_page_selection(selection, page_count):
    if not selection.strip():
        return list(range(1, page_count + 1))

    selected_pages = set()
    for part in selection.split(","):
        part = part.strip()
        if not part:
            raise ValueError("Enter pages as numbers or ranges, for example 2, 5-8, 12.")

        match = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", part)
        if not match:
            raise ValueError(
                f"Invalid page selection '{part}'. Use page numbers or ranges, "
                "for example 2, 5-8, 12."
            )

        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end > page_count:
            raise ValueError(f"Page numbers must be between 1 and {page_count}.")
        if start > end:
            raise ValueError(f"Page range '{part}' must start before it ends.")
        selected_pages.update(range(start, end + 1))

    return sorted(selected_pages)


def extract_text_from_file(uploaded_file, selected_pages=None):
    source_lines = []
    file_extension = uploaded_file.name.split(".")[-1].lower()
    current_unit = None

    def add_text_lines(text, page=None, unit=None, heading_style=False, merge_wrapped=False):
        nonlocal current_unit
        pending_lines = []

        def append_source_line(line, is_heading=False):
            source_lines.append({
                "text": line,
                "page": page,
                "unit": unit or current_unit,
                "is_heading": is_heading
            })

        def flush_pending():
            if pending_lines:
                append_source_line(" ".join(pending_lines))
                pending_lines.clear()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                flush_pending()
                continue
            explicit_unit = re.match(
                r"^(unit|chapter|section|module|lesson)\s+(?:[\w.-]+)(?:\s*[:\-–]\s*.*)?$",
                line,
                flags=re.IGNORECASE
            )
            if heading_style or explicit_unit:
                flush_pending()
                current_unit = line
                append_source_line(line, is_heading=True)
                continue
            if merge_wrapped:
                pending_lines.append(line)
                if re.search(r"[.!?][\"')\]]?$", line):
                    flush_pending()
            else:
                append_source_line(line)
        flush_pending()
    
    try:
        if file_extension == "pdf":
            pdf_bytes = uploaded_file.getvalue()
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages_to_read = (
                range(1, len(reader.pages) + 1)
                if selected_pages is None
                else selected_pages
            )
            pdfium_document = None
            for page_number in pages_to_read:
                page = reader.pages[page_number - 1]
                t = page.extract_text()
                if len(re.findall(r"\w+", t or "")) < 8:
                    try:
                        import pypdfium2 as pdfium
                        import pytesseract
                    except ModuleNotFoundError as e:
                        raise RuntimeError(
                            "This PDF needs OCR, but OCR packages are missing. "
                            "Install the project dependencies with: "
                            "pip install -r requirements.txt"
                        ) from e

                    tesseract_path = shutil.which("tesseract")
                    if not tesseract_path:
                        default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                        if os.path.isfile(default_tesseract):
                            tesseract_path = default_tesseract
                        else:
                            raise RuntimeError(
                                "This PDF needs OCR, but the Tesseract OCR engine was not found. "
                                "Install Tesseract OCR and make sure it is on PATH."
                            )
                    pytesseract.pytesseract.tesseract_cmd = tesseract_path
                    if pdfium_document is None:
                        pdfium_document = pdfium.PdfDocument(pdf_bytes)
                    image = pdfium_document[page_number - 1].render(scale=2).to_pil()
                    t = pytesseract.image_to_string(image, lang="eng")
                if t:
                    add_text_lines(t, page=page_number, merge_wrapped=True)
            if pdfium_document is not None:
                pdfium_document.close()
        elif file_extension in ["docx", "doc"]:
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                if para.text.strip():
                    style_name = getattr(getattr(para, "style", None), "name", "")
                    is_heading = style_name.lower().startswith("heading")
                    add_text_lines(para.text, heading_style=is_heading)
        elif file_extension == "csv":
            df = pd.read_csv(uploaded_file)
            add_text_lines(df.to_string(index=False))
        elif file_extension in ["xlsx", "xls"]:
            sheets = pd.read_excel(uploaded_file, sheet_name=None)
            for sheet_name, df in sheets.items():
                add_text_lines(df.to_string(index=False), unit=f"Sheet: {sheet_name}")
    except Exception as e:
        st.error(f"Error reading file: {e}")
    return source_lines

# ==========================================
# MCQ GENERATOR
# ==========================================
QUESTION_STOP_WORDS = {
    "about", "after", "again", "against", "also", "among", "and", "any",
    "are", "because", "been", "before", "being", "between", "both", "but",
    "can", "could", "does", "each", "either", "every", "from", "further",
    "had", "has", "have", "her", "here", "hers", "him", "his", "into",
    "itself", "just", "more", "most", "must", "not", "only", "other", "our",
    "out", "over", "same", "should", "some", "such", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "under", "until", "very", "was", "were", "what", "when",
    "where", "which", "while", "who", "will", "with", "would", "you", "your",
    "able", "across", "within", "without", "using", "used", "use", "make",
    "made", "many", "much", "like", "known", "often", "typically",
    "generally", "various", "during", "therefore", "thus", "important",
    "different", "specific", "from", "following", "example", "examples"
}

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
    "manage", "follows", "follow", "connects", "connect", "stores",
    "store", "builds", "build", "assembles", "assemble", "transforms",
    "transform", "classifies", "classify", "uses", "use"
)


def extract_exam_facts(source_lines):
    facts = []
    for source_line in source_lines:
        if source_line.get("is_heading", False):
            continue

        text = re.sub(r"\s+", " ", source_line["text"]).strip()
        text = re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+|[•*-]\s*)", "", text)
        if (
            not text
            or re.search(r"\.{3,}|_{3,}|…{2,}", text)
            or len(re.findall(r"\b\d+(?:\.\d+)+\s+[A-Z]", text)) > 1
        ):
            continue

        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        for sentence in sentences:
            sentence = sentence.strip(" \t\r\n•*-")
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
            if not fact["topic"]:
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
    if not subject_words:
        return None
    if len(subject_words) > 6:
        return None
    return subject[:1].upper() + subject[1:]


def exam_question_stem(fact):
    question_patterns = (
        (
            r"\b(?:is used to|is used for|allows|enables|performs|controls|"
            r"provides|produces|converts|calculates|measures|transmits)\b",
            "Which statement best explains the role of {topic}?",
        ),
        (
            r"\b(?:means|refers to|denotes|describes|consists of|includes|"
            r"contains|comprises|is|are)\b(?!\s+used\s+(?:to|for))",
            "Which statement best defines {topic}?",
        ),
    )
    for pattern, stem in question_patterns:
        if re.search(pattern, fact["text"], flags=re.IGNORECASE):
            return stem.format(topic=fact["topic"])
    return f"Which statement correctly describes {fact['topic']}?"


def generate_mcqs(text, num_questions=5):
    if isinstance(text, str):
        source_lines = [
            {"text": line, "page": None, "unit": None}
            for line in text.splitlines()
        ]
    else:
        source_lines = text
    facts = extract_exam_facts(source_lines)
    if len(facts) < 4:
        return []

    def content_words(sentence):
        return {
            word.casefold()
            for word in re.findall(r"[A-Za-z][A-Za-z'-]*", sentence)
            if len(word) >= 4 and word.casefold() not in QUESTION_STOP_WORDS
        }

    candidates = facts[:]
    random.shuffle(candidates)
    used_options = set()
    questions = []

    for fact in candidates:
        correct_option = fact["text"]
        if fact["normalized"] in used_options:
            continue

        target_words = content_words(correct_option)
        distractor_candidates = [
            candidate for candidate in facts
            if candidate["normalized"] not in used_options
            and candidate["normalized"] != fact["normalized"]
            and candidate["topic"].casefold() != fact["topic"].casefold()
            and fact["topic"].casefold() not in candidate["text"].casefold()
        ]
        distractor_candidates.sort(
            key=lambda candidate: (
                -len(target_words & content_words(candidate["text"])),
                candidate.get("unit") != fact.get("unit"),
                candidate.get("page") != fact.get("page"),
            )
        )

        distractors = []
        seen_distractors = set()
        for candidate in distractor_candidates:
            if candidate["normalized"] in seen_distractors:
                continue
            distractors.append(candidate)
            seen_distractors.add(candidate["normalized"])
            if len(distractors) == 3:
                break
        if len(distractors) < 3:
            continue

        options = [correct_option] + [item["text"] for item in distractors]
        random.shuffle(options)
        questions.append({
            "id": len(questions) + 1,
            "question": exam_question_stem(fact),
            "options": options,
            "answer": correct_option,
            "source_text": correct_option,
            "topic": fact["topic"],
            "page": fact.get("page"),
            "unit": fact.get("unit")
        })
        used_options.update(
            re.sub(r"\W+", " ", option).strip().casefold()
            for option in options
        )
        if len(questions) == num_questions:
            break

    return questions


def format_source_location(question):
    parts = []
    if question.get("page") is not None:
        parts.append(f"Page {question['page']}")
    if question.get("unit"):
        parts.append(str(question["unit"]))
    return " · ".join(parts) if parts else "Source location unavailable"


# ==========================================
# PDF SCORECARD EXPORT FUNCTION
# ==========================================
def add_pdf_paragraph(pdf, text, line_height=6):
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        w=pdf.epw,
        h=line_height,
        text=pdf_safe_text(text),
        wrapmode="CHAR"
    )


def pdf_safe_text(text):
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "--",
        "\u2026": "...",
        "\u00a0": " ",
        "\u2022": "*",
        "\u00b7": "-",
    }
    normalized = str(text).translate(str.maketrans(replacements))
    return normalized.encode("latin-1", errors="replace").decode("latin-1")


def create_pdf_scorecard(student_name, subject, score_pct, wrong_answers, improvement_plan):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, pdf_safe_text("Student Quiz Performance Report"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Student Name:", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, pdf_safe_text(student_name), new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Source File:", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, pdf_safe_text(subject), new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Final Score:", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"{score_pct}%", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    if wrong_answers:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Incorrect Responses Review:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for idx, item in enumerate(wrong_answers, start=1):
            add_pdf_paragraph(pdf, f"Q: {item['question']}")
            add_pdf_paragraph(pdf, f"Source: {item['source_location']}")
            add_pdf_paragraph(pdf, f"Your Answer: {item['user_answer']}")
            add_pdf_paragraph(pdf, f"Correct Answer: {item['correct_answer']}")
            add_pdf_paragraph(pdf, f"Why this is correct: {item['correct_reason']}")
            add_pdf_paragraph(pdf, f"Why your answer is incorrect: {item['incorrect_reason']}")
            pdf.ln(2)
            
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Personalized Improvement Plan:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    add_pdf_paragraph(pdf, improvement_plan)
    
    return pdf.output()

# ==========================================
# WHATSAPP API INTEGRATION FUNCTION
# ==========================================
def send_whatsapp_report(parent_phone, student_name, score_pct, improvement_summary):
    PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_ID", "YOUR_META_PHONE_NUMBER_ID")
    ACCESS_TOKEN = os.getenv("WHATSAPP_TOKEN", "YOUR_META_ACCESS_TOKEN")
    
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    message_body = (
        f"📊 *Quiz Result Update for {student_name}*\n\n"
        f"• *Score:* {score_pct}%\n\n"
        f"💡 *Improvement Areas:*\n{improvement_summary}\n\n"
        f"Lab AI Quiz System"
    )
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": parent_phone,
        "type": "text",
        "text": {"body": message_body}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return True, "Success"
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)


# ==========================================
# STREAMLIT UI ROUTING
# ==========================================
if st.session_state.app_state == "upload":
    st.title("🎓 AI MCQ Generator & Quiz Player")
    st.markdown("Upload your study materials (**PDF, Word, Excel, CSV**) and let the AI generate an interactive quiz session.")

    uploaded_file = st.file_uploader(
        "Upload Document",
        type=["pdf", "docx", "xlsx", "csv"]
    )
    selected_pages = None
    page_count = None
    if uploaded_file and uploaded_file.name.lower().endswith(".pdf"):
        try:
            page_count = len(pypdf.PdfReader(io.BytesIO(uploaded_file.getvalue())).pages)
            page_selection = st.text_input(
                "PDF pages to use (optional)",
                placeholder=f"All {page_count} pages",
                help=(
                    "Leave blank to use the whole PDF. Enter page numbers or ranges, "
                    "such as 2, 5-8, 12."
                )
            )
        except Exception as e:
            st.error(f"Could not read the PDF page count: {e}")
            page_selection = ""
    
    with st.form("quiz_setup_form"):
        student_name = st.text_input("Student Name:", placeholder="e.g. Alex Johnson")
        num_q = st.slider("Number of Questions", min_value=3, max_value=15, value=5)
        
        submitted = st.form_submit_button("Generate Quiz & Start", use_container_width=True)
        
        if submitted:
            if not uploaded_file:
                st.warning("Please upload a document first.")
            elif not student_name.strip():
                st.warning("Please enter the student's name.")
            elif uploaded_file.name.lower().endswith(".pdf") and page_count is None:
                st.error("The PDF page count is unavailable. Please upload a readable PDF.")
            else:
                try:
                    if uploaded_file.name.lower().endswith(".pdf"):
                        selected_pages = parse_page_selection(page_selection, page_count)
                except ValueError as e:
                    st.error(str(e))
                    st.stop()

                page_scope = (
                    f"pages {', '.join(map(str, selected_pages))}"
                    if selected_pages is not None
                    else "the uploaded document"
                )
                with st.spinner(f"Reading {page_scope} and generating quiz questions..."):
                    raw_text = extract_text_from_file(uploaded_file, selected_pages)
                    questions = generate_mcqs(raw_text, num_questions=num_q)
                    if not questions:
                        if not raw_text:
                            st.error(
                                "No selectable text could be extracted from this file. "
                                "If this is a scanned PDF, OCR will be attempted for the selected pages."
                            )
                        else:
                            st.error(
                                "The selected pages did not contain enough clean factual statements "
                                "to build exam-style questions with four distinct choices. Select "
                                "more content pages or upload a text-readable version of the book."
                            )
                    else:
                        st.session_state.questions = questions
                        st.session_state.student_name = student_name
                        st.session_state.file_name = uploaded_file.name
                        st.session_state.current_index = 0
                        st.session_state.user_answers = {}
                        st.session_state.generation_notice = (
                            f"Created {len(questions)} questions instead of {num_q}: "
                            "there were not enough clean, distinct facts in the selected material "
                            "to build more questions with non-repeating choices."
                            if len(questions) < num_q
                            else None
                        )
                        st.session_state.app_state = "quiz"
                        st.rerun()

elif st.session_state.app_state == "quiz":
    questions = st.session_state.questions
    idx = st.session_state.current_index
    q = questions[idx]

    if st.session_state.generation_notice:
        st.info(st.session_state.generation_notice)
    
    st.progress((idx + 1) / len(questions), text=f"Question {idx + 1} of {len(questions)}")
    
    st.markdown(f"""
    <div class="fade-in-card">
        <h3>Question {idx + 1}</h3>
        <p style="font-size: 1.1rem; font-weight: 500;">{html.escape(q['question'])}</p>
        <p style="font-size: 0.9rem; color: #b7c4d6;">Source: {html.escape(format_source_location(q))}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("**Choose your answer:**")
    selected_option = st.session_state.user_answers.get(idx)
    option_labels = "ABCD"
    for option_index, option in enumerate(q["options"]):
        is_selected = selected_option == option
        card_state = "selected_" if is_selected else ""
        with st.container(key=f"answer_card_{card_state}{idx}_{option_index}"):
            label = (
                f"✓ Selected — {option_labels[option_index]}. {option}"
                if is_selected
                else f"{option_labels[option_index]}. {option}"
            )
            if st.button(
                label,
                key=f"answer_{idx}_{option_index}",
                use_container_width=True,
                type="primary" if is_selected else "secondary"
            ):
                st.session_state.user_answers[idx] = option
                st.rerun()
    
    col1, col2 = st.columns([1, 1])
    with col2:
        if st.button(
            "Next Question ➡️" if idx < len(questions) - 1 else "Finish Quiz 🎉",
            key=f"next_question_button_{idx}",
            use_container_width=True
        ):
            selected_option = st.session_state.user_answers.get(idx)
            if selected_option is None:
                st.warning("Please select an answer before continuing.")
                st.stop()
            if idx < len(questions) - 1:
                st.session_state.current_index += 1
                st.rerun()
            else:
                correct_count = 0
                wrong_list = []
                for q_i, quest in enumerate(questions):
                    ans = st.session_state.user_answers.get(q_i)
                    if ans == quest["answer"]:
                        correct_count += 1
                    else:
                        wrong_list.append({
                            "question": quest["question"],
                            "user_answer": ans,
                            "correct_answer": quest["answer"],
                            "source_location": format_source_location(quest),
                            "correct_reason": (
                                f"The source material states: {quest['source_text']}. "
                                f"This statement directly describes {quest['topic']}."
                            ),
                            "incorrect_reason": (
                                f"Your selected statement, {ans}, does not describe "
                                f"{quest['topic']} according to the source material."
                            )
                        })
                
                score_pct = int((correct_count / len(questions)) * 100)
                
                if score_pct == 100:
                    plan = "Fantastic job! You mastered all concepts in this document."
                elif score_pct >= 70:
                    plan = "Good grasp of the material. Review the missed questions above and practice 3-5 related problems."
                else:
                    plan = "Needs focused revision. Re-read the source document sections covering incorrect answers."
                
                st.session_state.score_data = {
                    "score_pct": score_pct,
                    "correct_count": correct_count,
                    "total": len(questions),
                    "wrong_answers": wrong_list,
                    "improvement_plan": plan
                }
                st.session_state.app_state = "results"
                st.rerun()

elif st.session_state.app_state == "results":
    data = st.session_state.score_data
    st.title("📊 Quiz Results & AI Improvement Plan")
    
    st.metric(label="Final Score Percentage", value=f"{data['score_pct']}%", delta=f"{data['correct_count']}/{data['total']} Correct")
    
    st.markdown("### 💡 AI Improvement Summary & Plan")
    st.info(data["improvement_plan"])
    
    if data["wrong_answers"]:
        st.markdown("### 🔍 Incorrect Responses Review")
        for item in data["wrong_answers"]:
            st.markdown(f"#### {item['question']}")
            st.caption(f"Source: {item['source_location']}")
            st.error(f"Your answer: {item['user_answer']}")
            st.success(f"Correct answer: {item['correct_answer']}")
            st.write(f"Why this is correct: {item['correct_reason']}")
            st.write(f"Why your answer is incorrect: {item['incorrect_reason']}")
    else:
        st.success("Zero incorrect answers! Perfect score!")
        
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        pdf_bytes = create_pdf_scorecard(
            st.session_state.student_name,
            st.session_state.file_name,
            data["score_pct"],
            data["wrong_answers"],
            data["improvement_plan"]
        )
        st.download_button(
            label="📄 Download PDF Scorecard",
            data=bytes(pdf_bytes),
            file_name=f"{st.session_state.student_name}_Scorecard.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
    with col2:
        parent_phone = st.text_input("Parent's WhatsApp Number:", placeholder="e.g. 15551234567")
        if st.button("📱 Send Report via WhatsApp", use_container_width=True):
            if not parent_phone:
                st.warning("Enter a valid phone number.")
            else:
                success, msg = send_whatsapp_report(
                    parent_phone,
                    st.session_state.student_name,
                    data["score_pct"],
                    data["improvement_plan"]
                )
                if success:
                    st.success("Report successfully sent to parent!")
                else:
                    st.error(f"Failed to send: {msg}")
                    
    if st.button("🔄 Take Another Quiz", use_container_width=True):
        st.session_state.app_state = "upload"
        st.rerun()
