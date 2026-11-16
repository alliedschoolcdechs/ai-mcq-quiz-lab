import os
import io
import html
import hashlib
import difflib
import re
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
from fpdf import FPDF
import requests
from mcq_source import (
    mcq_lines_from_table,
    parse_mcq_source,
    select_answered_mcqs,
)
from mcq_logic import (
    QUESTION_STYLES,
    generate_question_items,
    generate_short_answer_items,
    resolve_generation_preferences,
)
from library_storage import (
    DuplicateLibraryFileError,
    add_library_file,
)
from local_storage import LocalStorage
from source_facts import definition_fragment, extract_exam_facts

# Document parsing libraries
import pypdf
from docx import Document

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
LIBRARY_DIR = APP_DIR / "library"
LIBRARY_DIR.mkdir(exist_ok=True)
DATABASE_PATH = APP_DIR / "quiz_attempts.sqlite3"
LOCAL_STORAGE = LocalStorage(DATABASE_PATH)
SUPPORTED_FILE_TYPES = {".pdf", ".docx", ".xlsx", ".csv", ".txt"}

# Page Config
st.set_page_config(
    page_title="MCQ Generator & Quiz Lab",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
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
        background-color: #0b1020;
        color: #f0f2f6;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1440px;
        padding-top: 3rem;
        padding-bottom: 0.25rem;
    }
    [data-testid="stMain"] > div {
        padding-top: 3rem;
    }
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    [class*="st-key-top_navigation"] [data-testid="stHorizontalBlock"] {
        align-items: center;
        gap: 0.6rem;
    }
    [class*="st-key-top_navigation"] button {
        min-height: 2.4rem;
    }
    [class*="st-key-upload_panel"] {
        padding: 0.65rem 0.75rem;
        border: 1px solid #2a3850;
        border-radius: 1rem;
        background: #172236;
    }
    [class*="st-key-setup_panel"] {
        padding: 0.65rem 0.75rem;
        border: 1px solid #2a3850;
        border-radius: 1.1rem;
        background: #172236;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.14);
    }
    [class*="st-key-setup_panel"] [data-testid="stForm"] {
        padding: 0;
        border: 0;
        background: transparent;
    }
    [class*="st-key-setup_panel"] [data-testid="stMarkdownContainer"] h3 {
        margin: 0 0 0.35rem 0;
        color: #f5f7ff;
    }
    [class*="st-key-upload_panel"] [data-testid="stMarkdownContainer"] h3 {
        margin: 0 0 0.35rem 0;
        color: #f5f7ff;
    }
    [class*="st-key-setup_panel"] [data-testid="stVerticalBlock"],
    [class*="st-key-upload_panel"] [data-testid="stVerticalBlock"] {
        gap: 0.35rem;
    }
    [class*="st-key-upload_panel"] [data-testid="stFileUploader"] {
        border-radius: 0.9rem;
        background: transparent;
    }
    [class*="st-key-upload_panel"] [data-testid="stFileUploaderDropzone"] {
        border: 1px dashed #44536c;
        border-radius: 0.8rem;
        background: #111a2b;
        min-height: 4.5rem;
        justify-content: center;
    }
    [class*="st-key-upload_panel"] [data-testid="stFileUploaderDropzoneInstructions"] {
        padding: 0.55rem;
    }
    [class*="st-key-generate_panel"] button {
        min-height: 3rem;
        border: 0;
        color: #fff;
        background: linear-gradient(105deg, #6558f5, #9b2bec);
        box-shadow: 0 8px 20px rgba(123, 61, 235, 0.27);
        font-weight: 750;
    }
    [class*="st-key-generate_panel"] button:hover {
        border: 0;
        background: linear-gradient(105deg, #766cff, #aa3cff);
        color: #fff;
        transform: translateY(-1px);
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
    [class*="st-key-answer_grid_"] {
        display: block;
    }
    [class*="st-key-answer_grid_"] [data-testid="stHorizontalBlock"] {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.7rem;
    }
    [class*="st-key-answer_grid_"] [data-testid="stColumn"] {
        width: auto !important;
        min-width: 0 !important;
        flex: initial !important;
    }
    [class*="st-key-answer_grid_"] [class*="st-key-answer_card_"] {
        animation: fadeIn 0.4s ease-out both;
    }
    [class*="st-key-answer_card_"] button {
        width: 100%;
        min-height: 2.45rem;
        padding: 0.45rem 0.8rem;
        text-align: left;
        white-space: normal;
        border: 1px solid #344256;
        border-radius: 9px;
        font-size: 0.92rem;
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
    [class*="st-key-quiz_panel"] {
        max-width: 760px;
        width: 100%;
        margin: 0 auto;
    }
    [class*="st-key-results_panel"] {
        max-width: 880px;
        width: 100%;
        margin: 0 auto;
    }
    [class*="st-key-quiz_panel"] .fade-in-card {
        padding: 1.15rem 1.4rem;
    }
    [class*="st-key-quiz_panel"] .fade-in-card h3 {
        margin: 0 0 0.45rem 0;
        font-size: 1.05rem;
    }
    [class*="st-key-quiz_panel"] .fade-in-card p {
        margin: 0.35rem 0;
        font-size: 1rem !important;
    }
    [class*="st-key-quiz_panel"] [data-testid="stProgress"] {
        margin-bottom: 0.65rem;
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
    .quiz-progress-label {
        margin-bottom: 0.4rem;
        color: #cbd5e1;
        font-size: 0.9rem;
        font-weight: 600;
    }
    .quiz-progress-track {
        width: 100%;
        height: 0.65rem;
        margin-bottom: 0.9rem;
        overflow: hidden;
        border-radius: 999px;
        background: #253349;
    }
    .quiz-progress-fill {
        height: 100%;
        border-radius: inherit;
        background: #3b82f6;
        transition: width 250ms ease;
    }
    @media (max-width: 760px) {
        [data-testid="stMain"] > div {
            padding: 3rem 0.75rem 2rem 0.75rem;
        }
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.55rem !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        [class*="st-key-setup_panel"],
        [class*="st-key-upload_panel"] {
            padding: 0.65rem;
        }
        [class*="st-key-upload_panel"] [data-testid="stFileUploaderDropzone"] {
            min-height: 5rem;
        }
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
if "quiz_mode" not in st.session_state:
    st.session_state.quiz_mode = "Examination"
if "question_source" not in st.session_state:
    st.session_state.question_source = "generated"
if "short_answer_questions" not in st.session_state:
    st.session_state.short_answer_questions = []
if "page_view" not in st.session_state:
    st.session_state.page_view = "home"
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "attempt_saved" not in st.session_state:
    st.session_state.attempt_saved = False
if "document_cache" not in st.session_state:
    st.session_state.document_cache = LOCAL_STORAGE.load_document_cache()
# ==========================================
# DOCUMENT TEXT EXTRACTOR
# ==========================================
def parse_page_selection(selection, page_count=None):
    if not selection.strip():
        return None

    selected_pages = set()
    for part in selection.split(","):
        part = part.strip()
        match = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", part)
        if not match:
            raise ValueError(
                f"Invalid page range '{part}'. Use page numbers or ranges, "
                "for example 2, 5-8, 12."
            )

        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1:
            raise ValueError("Page numbers must be 1 or greater.")
        if page_count is not None and end > page_count:
            raise ValueError(f"Page numbers must be between 1 and {page_count}.")
        if start > end:
            raise ValueError(f"Page range '{part}' must start before it ends.")
        selected_pages.update(range(start, end + 1))

    return tuple(sorted(selected_pages))


def get_ocr_tools():
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
    return pdfium, pytesseract


@st.cache_data(show_spinner=False, ttl=86400, max_entries=512)
def extract_pdf_ocr_page(file_digest, page_number, _file_bytes, scale=1.5):
    if not file_digest:
        raise ValueError("A document fingerprint is required to cache OCR results.")
    pdfium, pytesseract = get_ocr_tools()
    pdfium_document = pdfium.PdfDocument(_file_bytes)
    try:
        image = pdfium_document[page_number - 1].render(scale=scale).to_pil()
        return pytesseract.image_to_string(image, lang="eng")
    finally:
        pdfium_document.close()


def read_document_text(
    file_bytes,
    file_name,
    selected_pages=None,
    progress_callback=None,
    progress_start=5,
    progress_end=55
):
    source_lines = []
    file_extension = file_name.split(".")[-1].lower()
    current_unit = None
    current_unit_group = None

    def add_text_lines(text, page=None, unit=None, heading_style=False, merge_wrapped=False):
        nonlocal current_unit, current_unit_group
        pending_lines = []

        def append_source_line(line, is_heading=False):
            source_lines.append({
                "text": line,
                "page": page,
                "unit": unit or current_unit,
                "unit_group": current_unit_group,
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
            indexed_heading = re.match(
                r"^(\d+(?:\.\d+){0,3}\s+[A-Z][A-Za-z0-9 ,&()'/-]{2,75}?)"
                r"(?:\s+\.{2,}\s*\d+)?$",
                line
            )
            if heading_style or explicit_unit or indexed_heading:
                flush_pending()
                heading_text = indexed_heading.group(1) if indexed_heading else line
                current_unit = heading_text
                unit_group_match = re.match(
                    r"^(?:unit|chapter)\s+[\w.-]+(?:\s*[:\-–]\s*.*)?$",
                    heading_text,
                    flags=re.IGNORECASE
                )
                if unit_group_match:
                    current_unit_group = heading_text
                append_source_line(heading_text, is_heading=True)
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
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            file_digest = None
            page_count = len(reader.pages)
            if selected_pages is not None and any(
                page_number > page_count for page_number in selected_pages
            ):
                raise ValueError(f"Page numbers must be between 1 and {page_count}.")
            pages_to_read = (
                selected_pages
                if selected_pages is not None
                else range(1, page_count + 1)
            )
            total_to_read = len(pages_to_read)
            progress_page_limit = (
                pages_to_read[-1] if selected_pages is not None else page_count
            )
            for page_index, page_number in enumerate(pages_to_read):
                page = reader.pages[page_number - 1]
                t = page.extract_text()
                if len(re.findall(r"\w+", t or "")) < 8:
                    if file_digest is None:
                        file_digest = hashlib.sha256(file_bytes).hexdigest()
                    t = extract_pdf_ocr_page(
                        file_digest,
                        page_number,
                        file_bytes,
                        scale=2
                    )
                if t:
                    add_text_lines(t, page=page_number, merge_wrapped=True)
                if progress_callback:
                    progress = progress_start + int(
                        (progress_end - progress_start)
                        * (page_index + 1)
                        / max(1, total_to_read)
                    )
                    progress_callback(
                        progress,
                        f"Reading page {page_number} of {progress_page_limit}"
                    )
        elif file_extension in ["docx", "doc"]:
            if selected_pages is not None:
                raise ValueError("Page ranges can only be used with PDF files.")
            if progress_callback:
                progress_callback(
                    progress_start + 3,
                    "Extracting paragraphs and section headings"
                )
            doc = Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                if para.text.strip():
                    style_name = getattr(getattr(para, "style", None), "name", "")
                    is_heading = style_name.lower().startswith("heading")
                    add_text_lines(para.text, heading_style=is_heading)
        elif file_extension == "csv":
            if selected_pages is not None:
                raise ValueError("Page ranges can only be used with PDF files.")
            if progress_callback:
                progress_callback(progress_start + 3, "Reading CSV rows")
            df = pd.read_csv(io.BytesIO(file_bytes))
            add_text_lines(df.to_string(index=False))
        elif file_extension in ["xlsx", "xls"]:
            if selected_pages is not None:
                raise ValueError("Page ranges can only be used with PDF files.")
            if progress_callback:
                progress_callback(progress_start + 3, "Reading workbook sheets")
            sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
            for sheet_name, df in sheets.items():
                add_text_lines(df.to_string(index=False), unit=f"Sheet: {sheet_name}")
        elif file_extension == "txt":
            if selected_pages is not None:
                raise ValueError("Page ranges can only be used with PDF files.")
            if progress_callback:
                progress_callback(progress_start + 3, "Reading text document")
            add_text_lines(file_bytes.decode("utf-8-sig", errors="replace"))
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error reading file: {e}") from e
    return source_lines


def extract_uploaded_text(
    file_bytes,
    file_name,
    selected_pages=None,
    _progress_callback=None,
    progress_start=5
):
    return read_document_text(
        file_bytes,
        file_name,
        selected_pages,
        _progress_callback,
        progress_start
    )


def extract_library_text(
    file_name,
    modified_ns,
    file_size,
    selected_pages=None,
    _progress_callback=None,
    progress_start=5
):
    library_path = LIBRARY_DIR / Path(file_name).name
    current_stat = library_path.stat()
    if current_stat.st_mtime_ns != modified_ns or current_stat.st_size != file_size:
        raise RuntimeError("The selected library book changed. Select it again and retry.")
    return read_document_text(
        library_path.read_bytes(),
        library_path.name,
        selected_pages,
        _progress_callback,
        progress_start
    )


def document_cache_key(file_name, modified_ns, file_size):
    identity = f"{Path(file_name).name}|{modified_ns}|{file_size}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def source_lines_from_cached_facts(cached_facts):
    if not isinstance(cached_facts, list):
        return []
    return [
        {
            "text": fact["text"],
            "page": fact.get("page"),
            "unit": fact.get("unit"),
            "unit_group": fact.get("unit_group"),
            "is_heading": False,
        }
        for fact in cached_facts
        if isinstance(fact, dict) and isinstance(fact.get("text"), str)
    ]


def compact_document_facts(source_lines):
    facts = extract_exam_facts(source_lines)
    compact = []
    for fact in facts[:500]:
        compact.append({
            "text": fact["text"],
            "topic": fact["topic"],
            "page": fact.get("page"),
            "unit": fact.get("unit"),
            "unit_group": fact.get("unit_group"),
        })
    return compact


def save_document_fact_cache(file_name, modified_ns, file_size, source_lines):
    cache_key = document_cache_key(file_name, modified_ns, file_size)
    cached_facts = compact_document_facts(source_lines)
    if not cached_facts:
        return
    document_cache = dict(st.session_state.document_cache or {})
    cache_entry = {
        "fileName": Path(file_name).name,
        "modifiedNs": modified_ns,
        "fileSize": file_size,
        "facts": cached_facts,
    }
    LOCAL_STORAGE.save_document_cache_entry(cache_key, cache_entry)
    document_cache[cache_key] = cache_entry
    if len(document_cache) > 10:
        document_cache = dict(list(document_cache.items())[-10:])
    st.session_state.document_cache = document_cache


def extract_mcq_lines(
    file_bytes,
    file_name,
    selected_pages=None,
    progress_callback=None
):
    extension = Path(file_name).suffix.lower()
    if extension == ".pdf":
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        pages_to_read = (
            selected_pages
            if selected_pages is not None
            else tuple(range(1, page_count + 1))
        )
        if any(page < 1 or page > page_count for page in pages_to_read):
            raise ValueError(f"Page numbers must be between 1 and {page_count}.")
        lines = []
        file_digest = hashlib.sha256(file_bytes).hexdigest()
        for page_index, page_number in enumerate(pages_to_read):
            page = reader.pages[page_number - 1]
            try:
                page_text = page.extract_text(extraction_mode="layout") or ""
            except TypeError:
                page_text = page.extract_text() or ""
            if len(re.findall(r"\w+", page_text)) < 8:
                page_text = extract_pdf_ocr_page(
                    file_digest,
                    page_number,
                    file_bytes,
                    scale=2
                )
            lines.extend(
                {"text": line, "page": page_number}
                for line in page_text.splitlines()
            )
            if progress_callback:
                progress = 5 + int(50 * (page_index + 1) / max(1, len(pages_to_read)))
                progress_page_limit = (
                    pages_to_read[-1] if selected_pages is not None else page_count
                )
                progress_callback(
                    progress,
                    f"Reading MCQs on PDF page {page_number} of {progress_page_limit}."
                )
        return lines

    if selected_pages is not None:
        raise ValueError("Page ranges can only be used with PDF files.")

    if extension in {".docx", ".doc"}:
        document = Document(io.BytesIO(file_bytes))
        lines = [
            {"text": paragraph.text, "page": None}
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]
        for table in document.tables:
            table_rows = [
                [cell.text for cell in row.cells]
                for row in table.rows
            ]
            table_mcqs = (
                mcq_lines_from_table(table_rows[0], table_rows[1:])
                if table_rows
                else []
            )
            if table_mcqs:
                lines.extend(
                    {"text": line, "page": None}
                    for line in table_mcqs
                )
                continue
            for row in table.rows:
                for cell in row.cells:
                    lines.extend(
                        {"text": line, "page": None}
                        for line in cell.text.splitlines()
                    )
        if progress_callback:
            progress_callback(55, "Read question text from the Word document.")
        return lines

    if extension == ".txt":
        if progress_callback:
            progress_callback(55, "Read question text from the text document.")
        return [
            {"text": line, "page": None}
            for line in file_bytes.decode("utf-8-sig", errors="replace").splitlines()
        ]

    if extension in {".csv", ".xlsx"}:
        if extension == ".csv":
            table = pd.read_csv(io.BytesIO(file_bytes))
            table_mcqs = mcq_lines_from_table(
                table.columns,
                table.itertuples(index=False, name=None),
            )
            if table_mcqs:
                if progress_callback:
                    progress_callback(55, "Read question-bank rows from the CSV file.")
                return [{"text": line, "page": None} for line in table_mcqs]
        else:
            sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
            lines = []
            found_table_mcqs = False
            for sheet_name, table in sheets.items():
                table_mcqs = mcq_lines_from_table(
                    table.columns,
                    table.itertuples(index=False, name=None),
                )
                if table_mcqs:
                    found_table_mcqs = True
                    lines.extend(
                        {"text": line, "page": None}
                        for line in table_mcqs
                    )
                else:
                    lines.append({"text": f"Sheet: {sheet_name}", "page": None})
                    lines.extend(
                        {"text": line, "page": None}
                        for line in table.to_string(index=False).splitlines()
                    )
            if found_table_mcqs:
                if progress_callback:
                    progress_callback(55, "Read question-bank rows from the workbook.")
                return lines

        return read_document_text(
            file_bytes,
            file_name,
            progress_callback=progress_callback,
            progress_start=5
        )

    raise ValueError("MCQ source detection supports PDF, DOCX, XLSX, CSV, and TXT files.")


def start_quiz(
    questions,
    student_name,
    student_class,
    file_name,
    question_source,
    short_answer_questions,
):
    st.session_state.questions = questions
    st.session_state.student_name = student_name.strip()
    st.session_state.student_class = student_class.strip()
    st.session_state.file_name = file_name
    st.session_state.current_index = 0
    st.session_state.user_answers = {}
    st.session_state.quiz_mode = "Examination"
    st.session_state.question_source = question_source
    st.session_state.generation_notice = None
    st.session_state.short_answer_questions = short_answer_questions
    st.session_state.quiz_attempt_id = uuid.uuid4().hex
    st.session_state.quiz_started_at = datetime.now(timezone.utc).isoformat()
    st.session_state.attempt_saved = False
    st.session_state.app_state = "quiz"


def search_terms(query):
    excluded = TOPIC_STOP_WORDS | {
        "as", "at", "by", "for", "in", "of", "on", "to"
    }
    return {
        word.casefold()
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", query)
        if (len(word) >= 2 or word.isdigit())
        and word.casefold() not in excluded
    }


def search_terms_match(query_terms, content_terms):
    for query_term in query_terms:
        if query_term in content_terms:
            continue
        if len(query_term) < 5 or not any(
            len(content_term) >= 5
            and difflib.SequenceMatcher(
                None,
                query_term,
                content_term
            ).ratio() >= 0.84
            for content_term in content_terms
        ):
            return False
    return bool(query_terms)


def locate_pdf_pages(file_bytes, query, _progress_callback=None):
    terms = search_terms(query)
    if not terms:
        raise ValueError(
            "The topic or unit does not include searchable subject terms. "
            "Enter a topic or unit, or provide PDF page ranges."
        )

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    page_count = len(reader.pages)
    matched_pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        page_words = search_terms(page_text)
        if search_terms_match(terms, page_words):
            matched_pages.append(page_number)
        if _progress_callback:
            progress = 5 + int(25 * page_number / max(1, page_count))
            _progress_callback(
                progress,
                f"Searching selectable text on page {page_number} of {page_count}"
            )
    return tuple(matched_pages), page_count


def locate_library_pdf_pages(
    file_name,
    modified_ns,
    file_size,
    query,
    _progress_callback=None
):
    library_path = LIBRARY_DIR / Path(file_name).name
    current_stat = library_path.stat()
    if current_stat.st_mtime_ns != modified_ns or current_stat.st_size != file_size:
        raise RuntimeError("The selected library book changed. Select it again and retry.")
    return locate_pdf_pages(
        library_path.read_bytes(),
        query,
        _progress_callback
    )


# ==========================================
# MCQ GENERATOR
# ==========================================
TOPIC_STOP_WORDS = {
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


def generate_mcqs_from_source(
    candidates,
    fact_pool,
    num_questions,
    report_progress,
    difficulty="Medium",
    question_style="Balanced",
):
    unique_facts = []
    facts_by_topic = {}
    for fact in candidates + fact_pool:
        topic_key = fact["topic"].casefold()
        if topic_key in facts_by_topic:
            continue
        definition = definition_fragment(fact)
        if not definition:
            continue
        record = {
            "id": f"F{len(unique_facts) + 1}",
            "concept": fact["topic"],
            "definition": definition,
            "unit": fact.get("unit"),
            "unit_group": fact.get("unit_group"),
        }
        unique_facts.append((record, fact))
        facts_by_topic[topic_key] = fact

    candidate_fact_objects = {id(fact) for fact in candidates}
    candidate_ids = {
        record["id"]
        for record, fact in unique_facts
        if id(fact) in candidate_fact_objects
    }
    if len(unique_facts) < 4 or not candidate_ids:
        report_progress(
            100,
            "The selected source needs at least four distinct, source-backed concepts "
            "to create credible multiple-choice options.",
        )
        return []

    facts_by_id = {
        record["id"]: fact for record, fact in unique_facts
    }
    records_by_id = {record["id"]: record for record, _ in unique_facts}
    question_records = [records_by_id[fact_id] for fact_id in candidate_ids]
    distractor_records = [
        record for record, _ in unique_facts if record["id"] not in candidate_ids
    ]
    report_progress(80, "Generating questions using built-in source-based logic.")
    generated_questions = generate_question_items(
        question_records,
        num_questions,
        distractor_records=distractor_records,
        difficulty=difficulty,
        question_style=question_style,
    )

    report_progress(94, "Checking question answers and source-derived choices.")
    questions = []
    for item in generated_questions:
        fact = facts_by_id.get(item.get("source_fact_id"))
        options = item.get("options")
        answer = item.get("answer")
        answer_index = item.get("correct_answer_index")
        if (
            fact is None
            or item.get("source_fact_id") not in candidate_ids
            or not isinstance(options, list)
            or len(options) != 4
            or any(not isinstance(option, str) for option in options)
            or len({option.casefold() for option in options}) != 4
            or not isinstance(answer_index, int)
            or isinstance(answer_index, bool)
            or not 0 <= answer_index < len(options)
            or not isinstance(answer, str)
            or answer.casefold() != fact["topic"].casefold()
            or options[answer_index].casefold() != fact["topic"].casefold()
            or any(option.casefold() not in facts_by_topic for option in options)
            or not isinstance(item.get("question"), str)
            or not item["question"].strip()
            or not isinstance(item.get("explanation"), str)
            or not item["explanation"].strip()
        ):
            continue

        canonical_options = [facts_by_topic[option.casefold()]["topic"] for option in options]
        questions.append({
            "id": len(questions) + 1,
            "question": item["question"],
            "options": canonical_options,
            "answer": fact["topic"],
            "source_text": fact["text"],
            "topic": fact["topic"],
            "option_explanations": {
                option: facts_by_topic[option.casefold()]["text"]
                for option in canonical_options
            },
            "explanation": item["explanation"],
            "concept_tested": fact["topic"],
            "correct_answer_index": canonical_options.index(fact["topic"]),
            "page": fact.get("page"),
            "unit": fact.get("unit"),
            "unit_group": fact.get("unit_group"),
        })
        if len(questions) == num_questions:
            break

    report_progress(100, f"Created {len(questions)} source-grounded questions.")
    if not questions:
        report_progress(
            100,
            "The available source facts could not produce valid four-choice questions. "
            "Try a broader topic or page selection, or choose another source.",
        )
    return questions


def generate_mcqs(
    text,
    num_questions=5,
    topic_filter=None,
    progress_callback=None,
    difficulty="Medium",
    question_style="Balanced",
):
    def report_progress(value, message):
        if progress_callback:
            progress_callback(value, message)

    report_progress(60, "Finding conceptual facts in the selected material")
    if isinstance(text, str):
        source_lines = [
            {"text": line, "page": None, "unit": None}
            for line in text.splitlines()
        ]
    else:
        source_lines = text
    facts = extract_exam_facts(source_lines)
    report_progress(68, f"Identified {len(facts)} clean conceptual facts")
    if not facts:
        report_progress(100, "No clear source-backed concepts were found in the selected material")
        return []

    def query_words(sentence):
        return {
            word.casefold()
            for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", sentence)
            if (len(word) >= 2 or word.isdigit())
            and word.casefold() not in TOPIC_STOP_WORDS
        }

    fact_pool = facts
    topic_terms = query_words(topic_filter or "")
    if topic_terms:
        candidates = [
            fact for fact in fact_pool
            if search_terms_match(
                topic_terms,
                query_words(
                    f"{fact.get('unit_group') or ''} {fact.get('unit') or ''} "
                    f"{fact['topic']} {fact['text']}"
                )
            )
        ]
        if not candidates:
            report_progress(100, "No source facts matched the requested topic or unit")
            return []
    else:
        candidates = fact_pool[:]

    report_progress(
        74,
        f"Matched {len(candidates)} facts to the requested topic/unit"
        if topic_terms
        else f"Preparing {len(candidates)} facts from the selected material"
    )
    return generate_mcqs_from_source(
        candidates,
        fact_pool,
        num_questions,
        report_progress,
        difficulty=difficulty,
        question_style=question_style,
    )

def format_source_location(question):
    if question.get("source_location"):
        return str(question["source_location"])
    parts = []
    if question.get("page") is not None:
        parts.append(f"Page {question['page']}")
    if question.get("unit_group"):
        parts.append(str(question["unit_group"]))
    if question.get("unit"):
        unit = str(question["unit"])
        if unit != question.get("unit_group"):
            parts.append(unit)
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
        f"MCQ Quiz System"
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


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def build_attempt_record():
    score = st.session_state.score_data
    started_at = st.session_state.quiz_started_at
    completed_at = utc_timestamp()
    start_time = datetime.fromisoformat(started_at)
    elapsed = max(
        0,
        int((datetime.fromisoformat(completed_at) - start_time).total_seconds())
    )
    answer_records = []
    for question_index, question in enumerate(st.session_state.questions):
        selected_answer = st.session_state.user_answers.get(question_index)
        correct_answer = question.get("answer")
        answer_records.append({
            "questionNumber": question_index + 1,
            "question": question["question"],
            "selectedAnswer": selected_answer,
            "correctAnswer": correct_answer,
            "isCorrect": (
                selected_answer == correct_answer
                if correct_answer is not None
                else None
            ),
            "topic": question.get("topic", ""),
            "sourceLocation": format_source_location(question),
        })

    return {
        "attemptId": st.session_state.quiz_attempt_id,
        "studentName": st.session_state.student_name,
        "studentClass": st.session_state.student_class,
        "fileName": st.session_state.file_name,
        "quizMode": st.session_state.quiz_mode,
        "questionSource": st.session_state.question_source,
        "graded": score.get("graded", True),
        "scorePct": score.get("score_pct"),
        "correctCount": score.get("correct_count"),
        "total": score["total"],
        "startedAt": started_at,
        "completedAt": completed_at,
        "durationSeconds": elapsed,
        "answers": answer_records,
    }


def save_completed_attempt():
    if st.session_state.attempt_saved:
        return
    attempt = build_attempt_record()
    LOCAL_STORAGE.save_attempt(attempt)
    st.session_state.attempt_saved = True


def format_attempt_time(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (AttributeError, ValueError):
        return str(value)


def render_attempt_history(attempts):
    if not attempts:
        st.info("No quiz activity has been recorded yet.")
        return

    attempts = sorted(
        attempts,
        key=lambda item: item.get("completedAt", ""),
        reverse=True,
    )
    rows = []
    for attempt in attempts:
        row = {
            "Date and time": format_attempt_time(attempt.get("completedAt")),
            "Quiz": attempt.get("fileName", ""),
            "Mode": attempt.get("quizMode", ""),
            "Result": (
                f"{attempt['scorePct']}%"
                if attempt.get("graded") and attempt.get("scorePct") is not None
                else "Ungraded"
            ),
            "Correct": (
                f"{attempt.get('correctCount', 0)}/{attempt.get('total', 0)}"
                if attempt.get("graded")
                else "—"
            ),
            "Duration (seconds)": attempt.get("durationSeconds", 0),
            "Student": attempt.get("studentName", ""),
            "Class": attempt.get("studentClass", ""),
        }
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    for attempt in attempts[:100]:
        title = (
            f"{format_attempt_time(attempt.get('completedAt'))} · "
            f"{attempt.get('studentName', 'Student')} · "
            f"{attempt.get('studentClass', '')} · "
            f"{attempt.get('fileName', 'Quiz')}"
        )
        with st.expander(title):
            st.caption(
                f"{attempt.get('quizMode', '')} · {attempt.get('questionSource', '')}"
            )
            st.write(
                "Result: "
                + (
                    f"{attempt.get('scorePct')}% "
                    f"({attempt.get('correctCount', 0)}/{attempt.get('total', 0)})"
                    if attempt.get("graded")
                    else f"Ungraded ({attempt.get('total', 0)} questions)"
                )
            )
            for answer in attempt.get("answers", []):
                st.markdown(
                    f"**{answer.get('questionNumber', '')}. "
                    f"{answer.get('question', '')}**"
                )
                st.write(f"Student answer: {answer.get('selectedAnswer') or '—'}")
                if answer.get("correctAnswer") is not None:
                    st.write(f"Answer key: {answer['correctAnswer']}")
                st.caption(
                    f"Topic: {answer.get('topic') or '—'} · "
                    f"Source: {answer.get('sourceLocation') or '—'}"
                )


# ==========================================
# STREAMLIT UI ROUTING
# ==========================================
with st.container(key="top_navigation"):
    home_column, admin_column, _ = st.columns([1, 1.2, 6], gap="small")
    if home_column.button("Home", use_container_width=True):
        st.session_state.page_view = "home"
        st.rerun()
    if st.session_state.admin_authenticated:
        if admin_column.button("Admin dashboard", use_container_width=True):
            st.session_state.page_view = "admin"
            st.rerun()
    elif admin_column.button("Staff sign-in", use_container_width=True):
        st.session_state.page_view = "admin_login"
        st.rerun()

if st.session_state.page_view == "admin_login":
    try:
        admin_setup_required = not LOCAL_STORAGE.has_admin_password()
    except sqlite3.Error as error:
        st.title("Admin access")
        st.error(f"Could not read the local admin configuration: {error}")
        st.stop()

    st.title("Set up admin" if admin_setup_required else "Admin sign-in")
    if admin_setup_required:
        st.caption(
            "Create the first admin password on this computer before sharing "
            "the app on a school network."
        )
    with st.form("admin_access", clear_on_submit=True):
        entered_password = st.text_input(
            "Create admin password" if admin_setup_required else "Admin password",
            type="password",
        )
        confirm_password = None
        if admin_setup_required:
            confirm_password = st.text_input(
                "Confirm admin password",
                type="password",
            )
        submitted = st.form_submit_button(
            "Create admin password" if admin_setup_required else "Unlock dashboard"
        )

    if submitted:
        if admin_setup_required:
            if len(entered_password) < 12:
                st.error("Choose a password with at least 12 characters.")
            elif entered_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    configured = LOCAL_STORAGE.configure_admin_password(
                        entered_password
                    )
                except sqlite3.Error as error:
                    st.error(f"Could not save the admin configuration: {error}")
                else:
                    if configured:
                        st.session_state.admin_authenticated = True
                        st.session_state.page_view = "admin"
                        st.rerun()
                    else:
                        st.error(
                            "An admin password was configured in another session. "
                            "Sign in with that password."
                        )
        else:
            try:
                authenticated = LOCAL_STORAGE.verify_admin_password(
                    entered_password
                )
            except sqlite3.Error as error:
                st.error(f"Could not verify the admin password: {error}")
            else:
                if authenticated:
                    st.session_state.admin_authenticated = True
                    st.session_state.page_view = "admin"
                    st.rerun()
                else:
                    st.error("Incorrect admin password.")
    st.stop()

if (
    st.session_state.page_view == "admin"
    and not st.session_state.admin_authenticated
):
    st.session_state.page_view = "admin_login"
    st.rerun()

if st.session_state.page_view == "admin":
    st.title("Admin dashboard")
    st.caption(
        "Saved records are stored in the local SQLite database. "
        "Times are shown in this computer's local timezone."
    )
    try:
        admin_attempts = LOCAL_STORAGE.list_attempts()
    except sqlite3.Error as error:
        st.error(f"Could not load local quiz records: {error}")
        st.stop()

    graded_attempts = [
        attempt for attempt in admin_attempts
        if attempt.get("graded") and attempt.get("scorePct") is not None
    ]
    average_score = (
        sum(attempt["scorePct"] for attempt in graded_attempts)
        / len(graded_attempts)
        if graded_attempts
        else 0
    )
    metric_columns = st.columns(3)
    metric_columns[0].metric(
        "Students",
        len({attempt.get("studentName", "") for attempt in admin_attempts}),
    )
    metric_columns[1].metric("Quiz attempts", len(admin_attempts))
    metric_columns[2].metric(
        "Average graded score",
        f"{average_score:.1f}%" if graded_attempts else "—",
    )
    student_filter = st.text_input("Filter by student name")
    class_filter = st.text_input("Filter by class")
    filtered_attempts = LOCAL_STORAGE.list_attempts(
        student_filter,
        class_filter,
    )
    render_attempt_history(filtered_attempts)
    if st.button("Lock admin dashboard"):
        st.session_state.admin_authenticated = False
        st.session_state.page_view = "home"
        st.rerun()
    st.stop()

if st.session_state.app_state == "upload":
    file_column, parameter_column, action_column = st.columns(
        [1.0, 1.35, 0.65],
        gap="small"
    )
    preview_error = None
    selected_file_bytes = None
    selected_file_name = None
    selected_file_path = None
    library_stat = None
    library_files = sorted(
        (
            path.name for path in LIBRARY_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_FILE_TYPES
        ),
        key=str.casefold
    )

    with file_column:
        with st.container(key="upload_panel"):
            st.markdown("### 📚 Select book")
            file_source = st.radio(
                "Choose source",
                ["Upload a file", "Library"],
                horizontal=False
            )
            if file_source == "Library":
                if library_files:
                    selected_path = st.selectbox(
                        "Choose a book from your library",
                        library_files,
                    )
                    selected_path = LIBRARY_DIR / selected_path
                    try:
                        library_stat = selected_path.stat()
                        selected_file_path = selected_path
                        selected_file_name = selected_path.name
                    except OSError as e:
                        preview_error = f"Could not read the selected library file: {e}"
                else:
                    st.info("Your library is empty. Upload a book and add it to the library.")
            else:
                st.caption("PDF, DOCX, XLSX, CSV, or TXT. Scanned PDFs are supported with OCR.")
                uploaded_file = st.file_uploader(
                    "Browse files",
                    type=["pdf", "docx", "xlsx", "csv", "txt"],
                    label_visibility="collapsed"
                )
                if uploaded_file:
                    selected_file_bytes = uploaded_file.getvalue()
                    selected_file_name = uploaded_file.name
                    if st.button("Add this file to library", key="add_uploaded_to_library"):
                        try:
                            destination = add_library_file(
                                LIBRARY_DIR,
                                uploaded_file.name,
                                selected_file_bytes,
                                SUPPORTED_FILE_TYPES,
                            )
                        except DuplicateLibraryFileError as e:
                            st.warning(str(e))
                        except (OSError, ValueError) as e:
                            st.error(f"Could not save this file to the library: {e}")
                        else:
                            st.success(f"Added {destination.name} to the library.")
                            st.rerun()
            if preview_error:
                st.error(preview_error)
            elif selected_file_name:
                st.caption(selected_file_name)

    with parameter_column:
        with st.container(key="setup_panel"):
            st.markdown("### ⚙ Quiz Setup")
            student_name = st.text_input(
                "Student Name:",
                placeholder="e.g. Irfan ul Haq"
            )
            student_class = st.text_input(
                "Class:",
                placeholder="e.g. Grade 9A"
            )
            num_q = st.slider(
                "Number of Questions",
                min_value=3,
                max_value=15,
                value=5
            )
            difficulty = st.selectbox(
                "Difficulty",
                ["Easy", "Medium", "Hard"],
                index=1,
                help=(
                    "Controls how closely related the source-derived "
                    "incorrect choices are to the correct concept."
                ),
            )
            generation_template = st.selectbox(
                "Question style",
                QUESTION_STYLES,
                help=(
                    "FBISE-style uses source-grounded, application-framed wording. "
                    "It is not a verified match to a specific official model paper."
                ),
            )
            custom_prompt = st.text_area(
                "Optional custom instructions",
                height=68,
                placeholder=(
                    "Example: Make the questions challenging and conceptual."
                ),
                help=(
                    "Local rules recognize difficulty words (easy, medium, hard) "
                    "and styles (recall, conceptual, application/FBISE). Other "
                    "instructions are not interpreted; use Topic or unit for focus."
                ),
            )
            generation_preferences = resolve_generation_preferences(
                generation_template,
                custom_prompt,
                difficulty,
            )
            if custom_prompt.strip() and generation_preferences["conflict"]:
                st.warning(
                    "The custom instructions contain conflicting styles or "
                    "difficulty levels; the selected controls will be used."
                )
            elif custom_prompt.strip() and not generation_preferences["recognized"]:
                st.caption(
                    "No supported control was found in the custom instructions; "
                    "the selected style and difficulty will be used."
                )
            topic_unit = st.text_input(
                "Topic or unit (optional)",
                placeholder="e.g. RAM or Unit 2",
                help=(
                    "Optional. Leave blank to use the whole selected document; "
                    "enter a topic to narrow question targets."
                )
            )
            st.info(
                "The app generates an MCQ quiz and a separate short-answer study sheet. "
                "It automatically detects answer-keyed MCQs in the selected document. "
                "Templates affect generated questions; detected MCQs keep their source wording."
            )

            page_ranges = st.text_input(
                "PDF pages (optional)",
                placeholder="e.g. 5-10, 14",
                help=(
                    "Optional. Blank means the entire PDF; selecting pages limits extraction "
                    "and OCR."
                )
            )
            st.caption(
                "For a scanned PDF with no page selection, OCR may need to process every page."
            )

    with action_column:
        with st.container(key="generate_panel"):
            st.markdown("### Generate")
            submitted = st.button(
                "✧ Generate MCQs",
                key="generate_quiz_action",
                use_container_width=True,
                type="primary"
            )
            progress_slot = st.empty()
            status_slot = st.empty()

    if submitted:
        if not selected_file_name:
            status_slot.error("Choose a library book or upload a document first.")
        elif not student_name.strip():
            status_slot.error("Please enter the student's name.")
        elif not student_class.strip():
            status_slot.error("Please enter the student's class.")
        elif preview_error:
            status_slot.error(f"Could not prepare the selected book: {preview_error}")
        else:
            progress_slot.progress(0, text="Starting...")
            status_slot.info("Preparing the selected document.")
            generation_status_message = [""]
            questions = []
            source_lines = []
            short_answer_questions = []
            question_source = "generated"
            mcq_fallback_notice = None

            def update_generation_progress(value, message):
                generation_status_message[0] = message
                progress_slot.progress(value, text=f"{value}%")
                status_slot.info(message)

            try:
                extraction_progress_start = 5
                selected_pages = None
                if page_ranges.strip():
                    if Path(selected_file_name).suffix.lower() != ".pdf":
                        raise ValueError("Page ranges can only be used with PDF files.")
                    update_generation_progress(2, "Validating the requested PDF page ranges.")
                    selected_pages = parse_page_selection(page_ranges)

                if selected_file_path and library_stat:
                    current_stat = selected_file_path.stat()
                    if (
                        current_stat.st_mtime_ns != library_stat.st_mtime_ns
                        or current_stat.st_size != library_stat.st_size
                    ):
                        raise RuntimeError(
                            "The selected library file changed. Select it again and retry."
                        )
                    document_bytes = selected_file_path.read_bytes()
                else:
                    document_bytes = selected_file_bytes

                update_generation_progress(
                    5,
                    "Checking the document for multiple-choice questions and an answer key."
                )
                document_mcqs = parse_mcq_source(extract_mcq_lines(
                    document_bytes,
                    selected_file_name,
                    selected_pages,
                    progress_callback=update_generation_progress
                ))
                questions = select_answered_mcqs(document_mcqs, num_q)
                if questions:
                    for question in questions:
                        question["source_location"] = None
                        question["source_text"] = question["question"]
                    short_answer_questions = [
                        {
                            "question": question["question"],
                            "answer": question["answer"],
                            "topic": question["topic"],
                            "page": question.get("page"),
                        }
                        for question in questions
                    ]
                    question_source = "document_mcqs"
                    update_generation_progress(
                        100,
                        f"Selected {len(questions)} answer-keyed MCQs from the document."
                    )
                else:
                    if document_mcqs:
                        mcq_fallback_notice = (
                            "MCQ-style questions were detected, but no usable correct "
                            "answers were found. Generating questions from the source "
                            "content instead."
                        )
                    search_query = topic_unit.strip()
                    is_pdf = Path(selected_file_name).suffix.lower() == ".pdf"
                    if (
                        is_pdf
                        and selected_pages is None
                        and search_query
                        and search_terms(search_query)
                    ):
                        extraction_progress_start = 30
                        update_generation_progress(
                            5,
                            "Searching selectable PDF text for matching pages."
                        )
                        if selected_file_path and library_stat:
                            matched_pages, page_count = locate_library_pdf_pages(
                                selected_file_name,
                                library_stat.st_mtime_ns,
                                library_stat.st_size,
                                search_query,
                                _progress_callback=update_generation_progress
                            )
                        else:
                            matched_pages, page_count = locate_pdf_pages(
                                selected_file_bytes,
                                search_query,
                                _progress_callback=update_generation_progress
                            )
                        if not matched_pages:
                            update_generation_progress(
                                30,
                                "No matching selectable text found; reading the full PDF. "
                                "OCR may process every scanned page."
                            )
                        else:
                            selected_pages = tuple(sorted({
                                neighbor
                                for page_number in matched_pages
                                for neighbor in range(
                                    max(1, page_number - 2),
                                    min(page_count, page_number + 2) + 1
                                )
                            }))
                            update_generation_progress(
                                30,
                                f"Found {len(matched_pages)} matching pages; adding nearby context for answer choices."
                            )

                    cached_entry = None
                    if selected_file_path and library_stat and selected_pages is None:
                        cache_key = document_cache_key(
                            selected_file_name,
                            library_stat.st_mtime_ns,
                            library_stat.st_size,
                        )
                        candidate_cache = st.session_state.document_cache.get(cache_key)
                        if (
                            isinstance(candidate_cache, dict)
                            and candidate_cache.get("modifiedNs")
                            == library_stat.st_mtime_ns
                            and candidate_cache.get("fileSize")
                            == library_stat.st_size
                        ):
                            cached_entry = candidate_cache

                    if cached_entry:
                        source_lines = source_lines_from_cached_facts(
                            cached_entry.get("facts")
                        )
                        update_generation_progress(
                            55,
                            f"Loaded {len(source_lines)} cached source facts for "
                            f"{selected_file_name}."
                        )
                    else:
                        update_generation_progress(
                            extraction_progress_start,
                            (
                                "Reading the full selected document."
                                if selected_pages is None
                                else "Extracting only the selected pages/sections."
                            )
                        )
                        if selected_file_path and library_stat:
                            source_lines = extract_library_text(
                                selected_file_name,
                                library_stat.st_mtime_ns,
                                library_stat.st_size,
                                selected_pages,
                                _progress_callback=update_generation_progress,
                                progress_start=extraction_progress_start
                            )
                        else:
                            source_lines = extract_uploaded_text(
                                selected_file_bytes,
                                selected_file_name,
                                selected_pages,
                                _progress_callback=update_generation_progress,
                                progress_start=extraction_progress_start
                            )
                        if selected_file_path and library_stat and selected_pages is None:
                            try:
                                save_document_fact_cache(
                                    selected_file_name,
                                    library_stat.st_mtime_ns,
                                    library_stat.st_size,
                                    source_lines,
                                )
                                update_generation_progress(
                                    58,
                                    "Saved extracted topics and units for faster future quizzes."
                                )
                            except sqlite3.Error as error:
                                status_slot.warning(
                                    f"Questions will still be generated, but the document "
                                    f"cache could not be saved locally: {error}"
                                )

                    update_generation_progress(
                        60,
                        "Building questions from the selected source content."
                    )
                    questions = generate_mcqs(
                        source_lines,
                        num_questions=num_q,
                        topic_filter=topic_unit.strip(),
                        progress_callback=update_generation_progress,
                        difficulty=generation_preferences["difficulty"],
                        question_style=generation_preferences["question_style"],
                    )
                    short_answer_facts = extract_exam_facts(source_lines)
                    topic_terms = search_terms(topic_unit.strip())
                    if topic_terms:
                        short_answer_facts = [
                            fact for fact in short_answer_facts
                            if search_terms_match(
                                topic_terms,
                                search_terms(f"{fact['topic']} {fact['text']}")
                            )
                        ]
                    short_answer_questions = generate_short_answer_items(
                        short_answer_facts,
                        num_q,
                    )
            except ValueError as e:
                status_slot.error(str(e))
            except Exception as e:
                status_slot.error(f"Question generation failed: {e}")
            else:
                if not questions:
                    if mcq_fallback_notice and not source_lines:
                        status_slot.error(
                            f"{mcq_fallback_notice} No selectable source text could be "
                            "extracted. If this is a scanned PDF, verify that OCR is "
                            "installed."
                        )
                    elif mcq_fallback_notice:
                        status_slot.error(
                            f"{mcq_fallback_notice} "
                            + (
                                generation_status_message[0]
                                or "No suitable source-backed questions could be built."
                            )
                        )
                    elif question_source == "generated" and not source_lines:
                        status_slot.error(
                            "No selectable text could be extracted from this file. "
                            "If it is a scanned PDF, verify that OCR is installed and retry."
                        )
                    else:
                        status_slot.error(
                            generation_status_message[0]
                            or "No suitable source-backed questions could be built from this selection."
                        )
                else:
                    start_quiz(
                        questions,
                        student_name,
                        student_class,
                        selected_file_name,
                        question_source,
                        short_answer_questions,
                    )
                    if question_source == "document_mcqs" and len(questions) < num_q:
                        st.session_state.generation_notice = (
                            f"Found only {len(questions)} answer-keyed MCQs; "
                            "the quiz will use those."
                        )
                    elif mcq_fallback_notice:
                        st.session_state.generation_notice = mcq_fallback_notice
                        if len(questions) < num_q:
                            st.session_state.generation_notice += (
                                f" Created {len(questions)} of {num_q} requested questions."
                            )
                    elif question_source == "generated" and len(questions) < num_q:
                        st.session_state.generation_notice = (
                            f"Created {len(questions)} questions instead of {num_q}: "
                            "some source concepts did not pass the grounding and distinct-choice "
                            "checks. Try another source or reduce the requested question count."
                        )
                    st.rerun()

elif st.session_state.app_state == "quiz":
    questions = st.session_state.questions
    idx = st.session_state.current_index
    q = questions[idx]

    with st.container(key="quiz_panel"):
        if st.session_state.generation_notice:
            st.info(st.session_state.generation_notice)

        progress_percent = int(100 * (idx + 1) / len(questions))
        st.markdown(
            f"""
            <div class="quiz-progress-label">Question {idx + 1} of {len(questions)}</div>
            <div class="quiz-progress-track" role="progressbar"
                 aria-valuenow="{progress_percent}" aria-valuemin="0" aria-valuemax="100">
                <div class="quiz-progress-fill" style="width: {progress_percent}%"></div>
            </div>
            """,
            unsafe_allow_html=True
        )

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
        with st.container(key=f"answer_grid_{idx}"):
            option_columns = st.columns(2, gap="small")
            option_labels = q.get("option_labels")
            if not isinstance(option_labels, list) or len(option_labels) != len(q["options"]):
                option_labels = list("ABCD"[:len(q["options"])])
            for option_index, option in enumerate(q["options"]):
                is_selected = selected_option == option
                card_state = "selected_" if is_selected else ""
                with option_columns[option_index % 2]:
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
                            selected_fact = quest.get("option_explanations", {}).get(ans)
                            document_mcq = (
                                st.session_state.question_source == "document_mcqs"
                            )
                            wrong_list.append({
                                "question": quest["question"],
                                "topic": quest["topic"],
                                "user_answer": ans,
                                "correct_answer": quest["answer"],
                                "source_location": format_source_location(quest),
                                "source_text": quest.get("source_text", ""),
                                "selected_option_fact": selected_fact or "",
                                "correct_reason": (
                                    f"The selected document marks {quest['answer']} as correct."
                                    if document_mcq
                                    else (
                                        f"{quest['answer']} is correct because the source states: "
                                        f"{quest['source_text']}"
                                    )
                                ),
                                "incorrect_reason": (
                                    f"The document identifies {quest['answer']} as correct, "
                                    f"not {ans}."
                                    if document_mcq
                                    else (
                                        f"The source describes {ans} this way: \"{selected_fact}\" "
                                        f"That fact is about {ans}; this question asks about "
                                        f"{quest['topic']}. The relevant source fact is: {quest['source_text']}"
                                    )
                                    if selected_fact
                                    else (
                                        f"{ans} does not match the source fact for {quest['topic']}. "
                                        f"The relevant fact is: {quest['source_text']}"
                                    )
                                )
                            })

                    score_pct = int((correct_count / len(questions)) * 100)

                    if score_pct == 100:
                        plan = "Excellent work—you answered every question correctly."
                    elif wrong_list:
                        missed_topics = ", ".join(dict.fromkeys(
                            item["topic"] for item in wrong_list
                        ))
                        plan = (
                            f"Review these concepts from the selected material: {missed_topics}. "
                            "The notes below explain the source fact and why each chosen option "
                            "does not fit."
                        )
                    else:
                        plan = "Review the selected source material and try another practice quiz."

                    st.session_state.score_data = {
                        "graded": True,
                        "score_pct": score_pct,
                        "correct_count": correct_count,
                        "total": len(questions),
                        "wrong_answers": wrong_list,
                        "improvement_plan": plan,
                    }
                    st.session_state.app_state = "results"
                    st.rerun()

elif st.session_state.app_state == "results":
    data = st.session_state.score_data
    if not st.session_state.attempt_saved:
        try:
            save_completed_attempt()
            st.success("Your quiz activity was saved on this computer.")
        except sqlite3.Error as error:
            st.error(
                "This result has not been saved to the local database yet. "
                f"Check the database file and retry: {error}"
            )
            if st.button("Retry saving quiz activity"):
                st.rerun()

    with st.container(key="results_panel"):
        if data.get("graded", True):
            st.title("📊 Quiz Results & Improvement Plan")
            st.metric(
                label="Final Score Percentage",
                value=f"{data['score_pct']}%",
                delta=f"{data['correct_count']}/{data['total']} Correct"
            )
        else:
            st.title("📘 Quiz Complete")

        st.markdown("### 💡 Improvement Summary & Plan")
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
        elif data.get("graded", True):
            st.success("Zero incorrect answers! Perfect score!")

        short_answer_questions = st.session_state.short_answer_questions
        if short_answer_questions:
            st.markdown("### Short-Answer Study Sheet")
            st.caption(
                "Review these source-based questions and answers after completing the MCQ quiz."
            )
            for question_index, item in enumerate(short_answer_questions, start=1):
                st.markdown(
                    f"**Q{question_index}.** {html.escape(item['question'])}<br>"
                    f"**Answer:** {html.escape(item['answer'])}",
                    unsafe_allow_html=True,
                )
                if item.get("page") is not None:
                    st.caption(f"Source: Page {item['page']}")

            study_sheet = "\n\n".join(
                f"Q{question_index}. {item['question']}\nAnswer: {item['answer']}"
                for question_index, item in enumerate(short_answer_questions, start=1)
            )
            st.download_button(
                label="Download Short-Answer Study Sheet",
                data=study_sheet,
                file_name=f"{Path(st.session_state.file_name).stem}_short_answers.txt",
                mime="text/plain",
                key="download_short_answer_sheet",
            )

        st.markdown("---")

        if data.get("graded", True):
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
                parent_phone = st.text_input(
                    "Parent's WhatsApp Number:",
                    placeholder="e.g. 15551234567"
                )
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
