# AI MCQ Generator & Quiz Lab

This package contains the complete source code for the AI MCQ Generator & Quiz Player application, optimized for school computer labs.

## Files Included:
- `app.py`: The main Streamlit web application with a compact, responsive navy-and-purple interface, a reusable local book library, file processing (including OCR for scanned PDFs when Tesseract is installed), optional topic/page filters, built-in source-based MCQ generation, answer/source validation, animated answer cards, source-specific explanations, PDF scorecards, and WhatsApp API parent reporting.
- `mcq_logic.py` and `source_facts.py`: Deterministic question generation, source fact extraction, related distractor ranking, and validation support.
- `cloud_backend.py`, `firestore.rules`, and `google_login_component/`: Google sign-in, Firebase profile and quiz-history storage, the admin group, and Firestore access controls.
- `packages.txt`: Linux OCR engine dependency for Streamlit Community Cloud.
- `firebase_config.example.json`: Template for the public Firebase web-app configuration. Copy it to `firebase_config.json` beside the app or EXE and enter your project values.
- `run_main.py`: Launcher script required for packaging into a standalone `.exe` using PyInstaller.
- `requirements.txt`: Python package dependencies.

## How to Run Locally:
1. Complete [Google sign-in and shared Firebase setup](#google-sign-in-shared-activity-and-admin-dashboard) once for the school.
2. Install Python 3.8+ on each computer.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   streamlit run app.py --server.address localhost --server.port 8501
   ```

The app generates grounded questions locally from extracted source facts using
built-in logic. Generated items contain a concept-driven stem, four choices, a
zero-based correct-answer index, and a pedagogical explanation. Each item is
validated against its extracted source fact before it is added to a quiz.

### OmniRoute AI question generation

The app can use a local OmniRoute OpenAI-compatible gateway to improve question
wording, distractor selection, and incorrect-answer explanations. Configure
OmniRoute before launching the app:

```powershell
$env:OMNIROUTE_ENDPOINT = "http://localhost:20128/v1"
$env:OMNIROUTE_API_KEY = "your-local-or-gateway-key"
# Optional when the gateway exposes more than one model:
$env:OMNIROUTE_MODEL = "your-model-id"
py -m streamlit run app.py --server.address localhost --server.port 8501
```

The app sends the selected source facts and the user's question instructions to
OmniRoute. It requires a valid JSON response and still rejects questions whose
answers or choices cannot be matched to the source material. Generated quiz
creation reports an explicit error if OmniRoute is unavailable. Free providers
can have changing quotas, latency, or quality; do not send confidential
student information or copyrighted material to a third-party provider unless
your school has approved that provider.

The same values can be entered after sign-in in the **OmniRoute AI settings**
section in the app sidebar. The endpoint key is kept only in the current
Streamlit session. The key in **Dashboard -> Endpoints** authenticates calls to
OmniRoute; provider keys configured inside OmniRoute are separate.

Library documents use two cache layers. Parsed library text is cached locally
for 24 hours using the file name, size, and modification time. After a full
library read, the extracted topics, units, page references, and source
statements are also stored in the signed-in user's Firebase profile. An
unchanged library file can therefore reuse its cached facts on another quiz or
app restart. Changing the file size or modification time invalidates that
profile cache automatically. Page-limited reads still extract only the
requested PDF pages.

Without a valid `firebase_config.json`, the app stays on the setup/sign-in screen and does not expose the quiz.

If Streamlit displays “Your app is having trouble loading the `app.google_firebase_login` component,” restart the app and refresh the browser. The login component must send its ready signal before Streamlit can render it; use the updated source/EXE rather than an older running copy. This frontend-loading error is separate from Firebase credentials and Firestore rules.

## Google Sign-in, Shared Activity, and Admin Dashboard

The app accepts verified Google accounts. Users must sign in before accessing quizzes. A student's profile and quiz history are linked to the Firebase Authentication user ID; students can view their own attempt history, while admins can view all profiles and attempts. Each saved attempt includes its date/time, quiz mode, source file, duration, score (when graded), and question-level answers. Times are stored in UTC and displayed in the viewing computer's local timezone.

Data is stored in the school's Firebase project, not in an individual's Gmail inbox or Google Drive. The project owner controls the database and its retention. Quiz question text, selected answers, and answer keys are included in saved activity so authorized admins can review attempts.

The app uses an **in-app admin group** stored in Firestore. The first admin must be bootstrapped once in Firebase Console; admins can then add or remove other users who have already signed in. No Google Group email or domain allowlist is required; any verified Google account can register.

Scores are recorded from the local app after a quiz is completed. This shared dashboard is an activity and progress tracker, not a proctored or tamper-proof examination system.

### One-time Firebase setup

1. Create a Firebase project owned by the school and add a **Web app** to it.
2. In **Authentication → Sign-in method**, enable **Google** and choose the project's support email. In **Authentication → Settings → Authorized domains**, ensure `localhost` and `127.0.0.1` are present for local/EXE use. After deploying to Streamlit Community Cloud, add the app's exact `*.streamlit.app` hostname too.
3. Create a **Cloud Firestore** database.
4. Publish the access rules from [`firestore.rules`](./firestore.rules) in **Firestore → Rules**. Do this before allowing users to sign in. The rules let users access their own profile and attempts, and let active admin-group members read and manage the shared dashboard.
5. Copy [`firebase_config.example.json`](./firebase_config.example.json) to `firebase_config.json` in the same folder as `app.py` (or beside `AI_Quiz_Lab.exe`). Fill in `apiKey`, `projectId`, `appId`, and `authDomain` from the Firebase web-app configuration. This client configuration is not a service-account credential; **never put a Firebase service-account/private key in the app or EXE**.
6. Launch the app and sign in once with the intended first-admin Google account.
7. In **Firebase Console → Authentication → Users**, copy that account's **UID**. In **Firestore → Data**, create a document in collection `adminMembers` with the document ID set to that UID and these fields:
   - `uid` — string, the same UID
   - `email` — string, the admin's Google email
   - `active` — boolean, `true`
   - `addedBy` — string, `bootstrap`
   - `addedAt` — string, an ISO-8601 UTC timestamp
8. Select **Refresh access** in the app. **Admin dashboard** will appear in the sidebar. Students must sign in once before an admin can add them to the in-app admin group.

### Shared PCs and EXE distribution

Build the EXE using the packaging command below, then place the same school-owned `firebase_config.json` beside each copy of the EXE. The config contains public client settings only; Firestore rules enforce access. Every PC needs internet access to authenticate and save/load activity. Users on separate PCs see shared records because they use the same Firebase project. The local book library remains local to each computer.

If you expose the Streamlit server to other devices over a network instead of having each person run the EXE locally, use an HTTPS deployment and configure the corresponding Firebase authorized domain; do not expose an unauthenticated or plain-HTTP server to the internet.

The EXE runs a local Streamlit server on the computer where it is launched; it is not itself a mobile app or a hosted website. For phone access, deploy the app on a secured, HTTPS school server.

### Mobile web app on Streamlit Community Cloud

The mobile web version runs on Streamlit's host; students open its HTTPS `streamlit.app` URL in their phone browser. It uses the same built-in source-based question logic and does not require a model download or external AI service.

To deploy:

1. Put the app source and `requirements.txt` in a GitHub repository that you can deploy from Streamlit Community Cloud. Do not upload `firebase_config.json`, credentials, student data, or PDF/library files to a public repository.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py` as the entry point. Python 3.12 is the Community Cloud default and is the recommended deployment version for this app.
3. In the app's **Settings → Secrets**, add the Firebase web-app configuration in TOML form:
   ```toml
   [firebase]
   apiKey = "YOUR_FIREBASE_WEB_API_KEY"
   authDomain = "YOUR_FIREBASE_PROJECT_ID.firebaseapp.com"
   projectId = "YOUR_FIREBASE_PROJECT_ID"
   appId = "YOUR_FIREBASE_WEB_APP_ID"
   ```
   These settings are the Firebase web client configuration, not a service-account key. Never add a Firebase service-account/private key.
4. Add the deployed `your-app-name.streamlit.app` hostname to Firebase Authentication's **Authorized domains**, then sign in and test a quiz from a phone.

Community Cloud installs the Linux OCR engine using [`packages.txt`](./packages.txt). Uploaded documents are processed by the Streamlit host. Question generation does not send source text to an AI API; documents still leave the user's phone and are processed by the hosting provider. Community Cloud hosting is in the United States.

## Question Generation:
- Built-in questions use fact statements found in the selected material, turn those statements into direct concept/function questions, and select distractors from related terms in the same source. The app checks the answer against its source fact, requires four distinct source-derived options, and filters repeated stems/options before showing a quiz.
- Fact extraction rejects obvious OCR debris and non-concept subjects such as pronouns or existential openers (for example, "There are ..."), so those words cannot become answer choices. This conservative filter may skip ambiguous source statements rather than turn them into questions.
- The built-in engine does not invent hidden context or rely on external language models. It prefers grounded questions over unsupported claims; sources without enough clear concepts may yield fewer questions. Review generated questions before using them as a formal assessment.

## Import Existing MCQs:
- Choose **Import existing MCQs** to copy existing questions and their options from a PDF, DOCX, XLSX, CSV, or TXT file. The importer keeps question text, option text, and option order; it does not send these questions through the AI generator.
- For reliable detection, put each question and each of its four answer choices on separate lines, with choices labeled `A-D` or `1-4`. Numbered section headings followed by four labeled lines are not treated as questions. Scanned PDFs can be OCR-read; enter page ranges to limit OCR to selected pages.
- Choose **Practice** or **Examination**. Practice shows answer feedback when the document includes an answer key; if it does not, the quiz remains ungraded. Examination mode requires answers marked in the document or entered manually before the exam starts.
- Embedded correct answers are detected from an `Answer Key` section (for example `1-A, 2-C`) or a correct marker such as `*` after an option.

## Study Library:
- Place books in the `library/` folder beside `app.py` to make them available in the app.
- Or choose **Upload a file** and use **Add this file to library** to save an uploaded PDF, DOCX, XLSX, CSV, or TXT for later quizzes.
- Choose **Library** in the study-material panel to reuse a saved book without uploading it again. Files remain on this computer in the project folder.
- The app does not modify library files when reading them. Keep backups of important books.

Files are not scanned for topics when they are selected or uploaded. Topic/unit, PDF page ranges, and question-focus instructions are all optional. If no topic or pages are selected, the app uses the full document. A topic narrows question targets, page ranges limit PDF extraction, and question-focus instructions prioritize related source facts.

For PDFs with a topic or instructions and no page range, the app searches selectable text and reads matching pages plus nearby context. If there are no matching text-layer pages (for example, in a scanned PDF), it reads the full PDF and OCRs pages without selectable text. With no topic or range, the full PDF is read, and OCR may process every scanned page. Enter page ranges (for example `5-10, 14`) to limit extraction/OCR for a large scanned book. OCR results are cached for 24 hours. If a topic is supplied, generated questions must match it; distractors are drawn from the extracted content. Page ranges apply only to PDFs.

For DOCX, XLSX, and CSV files, the full selected document is analyzed to find topic-matching question concepts; other clean concepts from that same document remain available as distractors. Parent unit/chapter headings are retained so entering a broad unit name can match facts under its subsections. Only selected PDF pages are used when page ranges are supplied. OCR results for individual PDF pages are cached for up to 24 hours. Document extraction and page searching run outside Streamlit's data-cache wrappers so progress updates remain compatible with Streamlit's layout lifecycle. During extraction and question generation, the progress indicator reports percentage and the current step.

## How to Build a Standalone Executable (.exe) for Lab PCs:
1. Open your terminal in this folder and install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build the `.exe` (the login component must be included):
   ```bash
   pyinstaller --noconfirm --noconsole --onefile --add-data "app.py;." --add-data "cloud_backend.py;." --add-data "mcq_import.py;." --add-data "mcq_logic.py;." --add-data "source_facts.py;." --add-data "google_login_component;google_login_component" --collect-all streamlit --collect-all fpdf --collect-all pypdf --collect-all docx run_main.py --name "AI_Quiz_Lab"
   ```
3. Copy `dist/AI_Quiz_Lab.exe` and the configured `firebase_config.json` to each lab PC. Keep the Firebase project and Firestore rules under school administration.
