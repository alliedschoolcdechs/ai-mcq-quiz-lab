# MCQ Generator & Quiz Lab

A local Streamlit app for generating and taking source-based quizzes. Quiz
generation and record storage run on the computer hosting the app; Firebase,
Google sign-in, a hosted database, GitHub, and internet access are not required
for normal local use.

## Run locally

1. Install Python 3.8+ and the project dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. Launch the app:
   ```powershell
   python run_main.py
   ```
3. Open `http://127.0.0.1:8501` in a browser on the same computer.
4. Select **Staff sign-in** and create the first admin account with a username
   and a password of at least 12 characters. Passwords are stored as salted
   hashes in SQLite. Admins can add other named admin accounts from the
   dashboard. Existing installations with the former shared password can sign
   in as `admin` using that password.

The launcher binds to `127.0.0.1` by default, so the app is not exposed to the
local network. The server checks the password before displaying admin records;
hiding the dashboard button is not the access check. Configure the admin
password before exposing the app to a school network.

## Local records, library, and backups

Students enter their name and class before starting a quiz. Those details are
not verified; a student can enter someone else's name or class. Completed
attempts are saved to `quiz_attempts.sqlite3` beside the app or executable.
Records include the entered name and class, quiz/source details, score,
start/completion timestamps, duration, and question-level answers.

Books added to the study library are kept in the `library/` folder beside the
app or executable. Back up both `quiz_attempts.sqlite3` and the `library/`
folder regularly to a separate drive or other safe location. Close the app
before copying the SQLite database. Local-only storage avoids cloud quotas but
does not protect against disk failure or a lost computer.

Existing records that were in Firebase are not automatically imported into
SQLite. They remain in the Firebase project until separately exported or
deleted.

Each independently run copy of the app has its own database and library.
For multiple PCs to share records, run one copy on a school computer and make
it available only on the trusted school network. The host must stay on. For
example, set `STREAMLIT_SERVER_ADDRESS=0.0.0.0` before launch and configure
the host firewall/router to restrict access to the trusted school network.
Do not expose the app directly to the public internet. Admin accounts protect
the dashboard; they do not verify student identities or replace network
restrictions. If each PC runs its own copy, records remain separate.

## Quiz generation and source documents

The app generates grounded questions locally from extracted source facts using
built-in logic; no external AI service receives the documents. It maps extracted
concepts using their topic/unit and text similarity, then generates and validates
source-grounded questions. Conceptual and FBISE-style templates frame source
facts as computer tasks when the text supports that wording. Question wording,
target concepts, and answer-option order vary between quizzes. Distractors are
ranked by topic/unit and text similarity, near-duplicate definitions are
excluded, and distractor concepts are not reused within a quiz while enough
related choices remain. If the source does not provide three related
distractors, that question is omitted instead of using unrelated choices, so a
quiz may contain fewer questions than requested. Each generated item is
validated against its extracted source fact and includes a source-backed
explanation.

Choose a question style template (Balanced, Direct recall, Conceptual, or
FBISE-style) before generation. The FBISE-style option uses source-grounded,
application-framed wording; it is not a verified match to a specific official
FBISE model paper. Optional custom instructions are interpreted locally for
recognized style and difficulty keywords only. Other instructions are not
applied, and no external AI service is used.

- Choose **Generate MCQs** for any document. The app detects answer-keyed MCQs
  when the source includes four labeled options and a marked correct answer.
  When more questions are detected than requested, the app randomly selects
  from the answer-keyed bank; the answer key is used to grade student
  selections. If there are no usable answer-keyed MCQs, new questions are
  generated from the document's source facts.
- For automatic detection, put each question and each of its four answer
  choices on separate lines, with choices labeled `A-D` or `1-4`. Correct
  answers can be shown in an `Answer Key` section (for example `1-A, 2-C`),
  written after each question (for example `Correct Answer: C`), or marked on
  the correct option. CSV, XLSX, and DOCX tables with columns for the question,
  options A-D (or 1-4), and correct answer are also supported. The app does not
  guess when an answer is missing.
- Scanned PDFs can be OCR-read when Tesseract OCR is installed. Enter page
  ranges to limit OCR for large documents. Page ranges apply only to PDFs.
- The app also creates a short-answer study sheet from detected MCQs or lesson
  facts. The sheet appears after the quiz and can be downloaded as a text file.

Place books in `library/` beside `app.py`, or upload a PDF, DOCX, XLSX, CSV, or
TXT and select **Add this file to library**. Identical files are rejected;
same-name files with different contents are saved under a numbered name. The
app does not modify library files when reading them.

Topic/unit and PDF page ranges are optional. If no topic or pages are selected,
the app uses the full document. A topic narrows question targets; page ranges
limit PDF extraction. For PDFs with a topic and no page range, the app searches
selectable text and reads matching pages plus nearby context. If there are no
matching text-layer pages (for example, in a scanned PDF), it reads the full
PDF and OCRs pages without selectable text. OCR results are cached locally for
24 hours. Extracted facts from full library reads are also cached in SQLite and
reused while the library file's size and modification time remain unchanged.

For DOCX, XLSX, and CSV files, the full selected document is analyzed to find
topic-matching question concepts; other clean concepts from that same document
remain available as distractors. Parent unit/chapter headings are retained so
entering a broad unit name can match facts under its subsections.

## Optional WhatsApp reports

Sending a score report through WhatsApp requires an internet connection and a
configured WhatsApp API integration. It is optional; quiz generation,
attempt saving, the local admin dashboard, and library use work without it.

## Build a standalone Windows executable

1. Install PyInstaller:
   ```powershell
   pip install pyinstaller
   ```
2. Build the executable:
   ```powershell
   pyinstaller --noconfirm --noconsole --onefile --add-data "app.py;." --add-data "mcq_source.py;." --add-data "mcq_logic.py;." --add-data "library_storage.py;." --add-data "local_storage.py;." --add-data "source_facts.py;." --collect-all streamlit --collect-all fpdf --collect-all pypdf --collect-all docx run_main.py --name "AI_Quiz_Lab"
   ```
3. Launch `dist/AI_Quiz_Lab.exe` and create the first admin account through
   **Staff sign-in**. The executable creates its local database and `library/`
   folder beside itself.
