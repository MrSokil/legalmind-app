import streamlit as st
import os
from dotenv import load_dotenv
from groq import Groq
from docx import Document
from pypdf import PdfReader
from io import BytesIO

load_dotenv()

# Налаштування сторінки для мобільних пристроїв
st.set_page_config(page_title="LegalMind", page_icon="⚖️", layout="centered")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- ФУНКЦІЇ ОБРОБКИ ---
def read_file(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext == '.txt':
        return uploaded_file.read().decode("utf-8")
    elif ext == '.docx':
        doc = Document(uploaded_file)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext == '.pdf':
        reader = PdfReader(uploaded_file)
        return "\n".join([page.extract_text() for page in reader.pages])
    return None

def create_docx(analysis_text):
    doc = Document()
    doc.add_heading('ЮРИДИЧНИЙ ЗВІТ LEGALMIND', 0)
    doc.add_paragraph(analysis_text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- ІНТЕРФЕЙС STREAMLIT ---
st.title("⚖️ LegalMind: Ваш AI-Юрист")
st.markdown("---")

uploaded_file = st.file_uploader("Завантажте документ (PDF, DOCX, TXT)", type=['pdf', 'docx', 'txt'])

if uploaded_file is not None:
    with st.spinner('LegalMind аналізує документ...'):
        content = read_file(uploaded_file)
        
        if content:
            # Запит до Groq
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Ти — старший юрист. Проаналізуй документ: суть, права/обов'язки, ризики та рекомендації українською мовою."},
                    {"role": "user", "content": content}
                ],
                model="llama-3.1-8b-instant",
            )
            analysis = chat_completion.choices[0].message.content
            
            # Відображення результату
            st.subheader("Результат аналізу")
            st.markdown(analysis)
            
            # Генерація та завантаження DOCX
            docx_file = create_docx(analysis)
            st.download_button(
                label="📥 Завантажити звіт у .docx",
                data=docx_file,
                file_name=f"LegalMind_Report_{uploaded_file.name}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            st.error("Помилка читання файлу.")

# --- БОКОВА ПАНЕЛЬ ---
with st.sidebar:
    st.header("Налаштування")
    st.info("LegalMind працює в хмарі. Ваш ПК не навантажується.")
    if st.button("Очистити все"):
        st.rerun()