import os
import io
import random
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

# Custom CSS for Smooth Fade Animations & Clean UI
st.markdown("""
<style>
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .fade-in-card {
        animation: fadeIn 0.4s ease-in-out;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
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

# ==========================================
# DOCUMENT TEXT EXTRACTOR (Robust & Scanned PDF Handler)
# ==========================================
def extract_text_from_file(uploaded_file):
    text = ""
    file_extension = uploaded_file.name.split(".")[-1].lower()
    
    try:
        if file_extension == "pdf":
            reader = pypdf.PdfReader(uploaded_file)
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t + "\n"
            if not text.strip():
                st.warning("⚠️ This PDF appears to be a scanned image or contains no selectable text. Falling back to smart default study content to generate the quiz!")
        elif file_extension in ["docx", "doc"]:
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                if para.text.strip(): text += para.text + "\n"
        elif file_extension == "csv":
            df = pd.read_csv(uploaded_file)
            text = df.to_string()
        elif file_extension in ["xlsx", "xls"]:
            df = pd.read_excel(uploaded_file)
            text = df.to_string()
    except Exception as e:
        st.warning(f"⚠️ Could not parse file directly ({e}). Using smart default study content to generate the quiz!")
    return text

# ==========================================
# MCQ GENERATOR
# ==========================================
def generate_mcqs(text, num_questions=5):
    lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 20]
    questions = []
    
    if len(lines) < num_questions:
        lines = [
            "Python is a high-level, interpreted programming language known for its readability.",
            "Variables in Python do not need explicit declaration to reserve memory space.",
            "Lists in Python are mutable data types enclosed in square brackets.",
            "Tuples are immutable sequences in Python enclosed in parentheses.",
            "Dictionaries store key-value pairs and are optimized to retrieve values when the key is known."
        ]
    
    selected_lines = random.sample(lines, min(num_questions, len(lines)))
    
    for i, line in enumerate(selected_lines):
        words = line.split()
        if len(words) > 5:
            target_idx = len(words) // 2
            correct_answer = words[target_idx].strip('.,')
            words[target_idx] = "_____"
            q_text = " ".join(words)
            
            distractors = [correct_answer + "1", "Dynamic", "Static", "Function", "Object"]
            options = [correct_answer] + [d for d in distractors if d != correct_answer][:3]
            random.shuffle(options)
            
            questions.append({
                "id": i + 1,
                "question": f"Complete or identify based on text: {q_text}",
                "options": options,
                "answer": correct_answer
            })
            
    return questions

# ==========================================
# PDF SCORECARD EXPORT FUNCTION
# ==========================================
def create_pdf_scorecard(student_name, subject, score_pct, wrong_answers, improvement_plan):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Student Quiz Performance Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Student Name:", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, student_name, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(40, 8, "Source File:", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, subject, new_x="LMARGIN", new_y="NEXT")
    
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
            pdf.multi_cell(0, 6, f"Q: {item['question']}")
            pdf.multi_cell(0, 6, f"   Your Answer: {item['user_answer']} | Correct: {item['correct_answer']}")
            pdf.ln(2)
            
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Personalized Improvement Plan:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, improvement_plan)
    
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
    
    with st.form("quiz_setup_form"):
        student_name = st.text_input("Student Name:", placeholder="e.g. Alex Johnson")
        uploaded_file = st.file_uploader("Upload Document", type=["pdf", "docx", "xlsx", "csv"])
        num_q = st.slider("Number of Questions", min_value=3, max_value=15, value=5)
        
        submitted = st.form_submit_button("Generate Quiz & Start", use_container_width=True)
        
        if submitted:
            if not uploaded_file:
                st.warning("Please upload a document first.")
            elif not student_name.strip():
                st.warning("Please enter the student's name.")
            else:
                with st.spinner("Extracting text and generating smart MCQs..."):
                    raw_text = extract_text_from_file(uploaded_file)
                    questions = generate_mcqs(raw_text, num_questions=num_q)
                    
                    st.session_state.questions = questions
                    st.session_state.student_name = student_name
                    st.session_state.file_name = uploaded_file.name
                    st.session_state.current_index = 0
                    st.session_state.user_answers = {}
                    st.session_state.app_state = "quiz"
                    st.rerun()

elif st.session_state.app_state == "quiz":
    questions = st.session_state.questions
    idx = st.session_state.current_index
    q = questions[idx]
    
    st.progress((idx + 1) / len(questions), text=f"Question {idx + 1} of {len(questions)}")
    
    st.markdown(f"""
    <div class="fade-in-card">
        <h3>Question {idx + 1}</h3>
        <p style="font-size: 1.1rem; font-weight: 500;">{q['question']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    selected_option = st.radio("Choose your answer:", q["options"], key=f"q_{idx}")
    
    col1, col2 = st.columns([1, 1])
    with col2:
        if st.button("Next Question ➡️" if idx < len(questions) - 1 else "Finish Quiz 🎉", use_container_width=True):
            st.session_state.user_answers[idx] = selected_option
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
                            "correct_answer": quest["answer"]
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
            st.error(f"**Q:** {item['question']}\n\n*Your Answer:* {item['user_answer']} | *Correct Answer:* **{item['correct_answer']}**")
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
