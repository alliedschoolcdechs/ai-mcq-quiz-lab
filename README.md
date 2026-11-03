# AI MCQ Generator & Quiz Lab

This package contains the complete source code for the AI MCQ Generator & Quiz Player application, optimized for school computer labs.

## Files Included:
- `app.py`: The main Streamlit web application with file processing (including OCR for scanned PDFs when Tesseract is installed), selected-page/unit references, fact-based exam-style questions (not fill-in-the-blank) with distinct source-derived statement choices, animated answer cards, scoring/improvement plans, PDF scorecard download, and WhatsApp API parent reporting.
- `run_main.py`: Launcher script required for packaging into a standalone `.exe` using PyInstaller.
- `requirements.txt`: Python package dependencies.

## How to Run Locally:
1. Install Python 3.8+ on the computer.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

For PDF uploads, optionally enter page numbers and ranges in the **PDF pages to use** field (for example, `2, 5-8, 12`). Leave it blank to process the entire PDF. Text extraction and OCR are limited to the selected pages.

## How to Build a Standalone Executable (.exe) for Lab PCs:
1. Open your terminal in this folder and install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build the `.exe`:
   ```bash
   pyinstaller --noconsole --onefile --collect-all streamlit --collect-all fpdf2 --collect-all pypdf --collect-all docx run_main.py --name "AI_Quiz_Lab"
   ```
3. Find your standalone executable in the `dist/AI_Quiz_Lab.exe` folder and copy it to lab computers!
