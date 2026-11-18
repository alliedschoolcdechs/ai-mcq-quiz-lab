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

Choose **Built-in logic** for offline question generation; it does not send
documents to an AI service. The optional **Ollama AI** mode sends extracted,
validated source facts to the Ollama server configured for this app. Ollama
must be running and have a model installed (for example, run
`ollama pull qwen2.5:7b`). The default endpoint is `http://127.0.0.1:11434`; set
`OLLAMA_BASE_URL` in the server environment or Streamlit secrets to use another
reachable Ollama server.
The app lists installed models for students to choose from. On a hosted
Streamlit deployment, the configured Ollama server must be reachable from the
deployment host; it cannot connect to Ollama running only on a student's PC.
Keep Ollama on a trusted network and do not expose its unauthenticated API to
the public internet.

Both generation modes use readable source facts, reject corrupted fragments
and editorial headings, and require related, document-derived distractors.
Being in the same section alone is not enough. Generated questions are checked
against the source concept map; if three related choices are unavailable, the
question is omitted rather than padded with unrelated options. Built-in
generation uses local concept and question templates. Ollama can write varied,
conceptual and application-focused stems while the app validates the answer
concepts and options against the extracted facts.

Choose a question style template (Balanced, Direct recall, Conceptual, or
FBISE-style) before generation. The FBISE-style option uses source-grounded,
application-framed wording; it is not a verified match to a specific official
FBISE model paper. Built-in logic interprets recognized style and difficulty
keywords in optional custom instructions. Ollama also receives those
instructions, but source support and answer validation remain required.

Choose **Examination** to receive feedback at the end or **Training** to see
whether each answer is correct immediately, with the correct answer and its
available explanation. Training locks the selected answer; a correct choice
glows green, while an incorrect choice briefly shakes and highlights red.
The incorrect choice and feedback card also show a cracked-glass overlay.
Imported MCQs without an explanation in the source answer key are identified as
such rather than given an invented rationale.

- Choose **Generate MCQs** for any document. The app detects answer-keyed MCQs
  when the source includes four labeled options and a marked correct answer.
  When more questions are detected than requested, the app randomly selects
  from the answer-keyed bank; the answer key is used to grade student
  selections. If there are no usable answer-keyed MCQs, new questions are
  generated from the document's source facts. Generic instruction prompts and
  excessively long extracted passages are rejected as malformed question stems.
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
   pyinstaller --noconfirm --noconsole --onefile --add-data "app.py;." --add-data "mcq_source.py;." --add-data "mcq_logic.py;." --add-data "library_storage.py;." --add-data "local_storage.py;." --add-data "source_facts.py;." --add-data "ollama_generation.py;." --collect-all streamlit --collect-all fpdf --collect-all pypdf --collect-all docx run_main.py --name "AI_Quiz_Lab"
   ```
3. Launch `dist/AI_Quiz_Lab.exe` and create the first admin account through
   **Staff sign-in**. The executable creates its local database and `library/`
   folder beside itself.
