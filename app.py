import streamlit as st
import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq
from docx import Document
from pypdf import PdfReader
from io import BytesIO

load_dotenv()

# Налаштування сторінки
st.set_page_config(page_title="LegalMind", page_icon="⚖️", layout="centered")

# Отримання ключа (з .env або з Secrets Streamlit)
api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

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

def read_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Видаляємо зайві елементи
        for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
            script_or_style.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Не вдалося зчитати посилання: {e}")
        return None

def create_docx(analysis_text):
    doc = Document()
    doc.add_heading('ЮРИДИЧНИЙ ЗВІТ LEGALMIND', 0)
    doc.add_paragraph(analysis_text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- БІЧНА ПАНЕЛЬ (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Налаштування")
    
    mode = st.selectbox(
        "Оберіть режим аналізу:",
        [
            "Аналіз договору", 
            "Судова практика та Позови", 
            "Корпоративні документи", 
            "Загальна консультація"
        ]
    )
    
    st.info(f"Активний режим: **{mode}**")
    
    if st.button("Очистити все"):
        st.rerun()

# --- ЛОГІКА ПЕРСОНАЛІЗАЦІЇ ШІ ---
prompts = {
    "Аналіз договору": "Ти — провідний юрист. Проаналізуй цей договір на предмет прихованих ризиків, термінів, штрафних санкцій та відповідності ЦКУ. Виділи критичні помилки.",
    "Судова практика та Позови": "Ти — адвокат. Проаналізуй цей документ (позов чи клопотання). Знайди слабкі місця в аргументації, перевір посилання на статті ЦПК/ГПК та запропонуй покращення на основі актуальної практики.",
    "Корпоративні документи": "Ти — спеціаліст з корпоративного права. Перевір цей статут або протокол на відповідність закону про ТОВ, знайди ризики для засновників та помилки в процедурах прийняття рішень.",
    "Загальна консультація": "Ти — універсальний юридичний радник. Проаналізуй текст та надай вичерпну відповідь на питання користувача, базуючись на законодавстві України."
}

# --- ІНТЕРФЕЙС STREAMLIT ---
st.title("⚖️ LegalMind: Ваш AI-Юрист")
st.markdown("---")

# Вибір джерела даних
source = st.radio("Джерело аналізу:", ["Файл", "Посилання"], horizontal=True)

content = ""
input_name = "document"

if source == "Файл":
    uploaded_file = st.file_uploader("Завантажте PDF, DOCX або TXT", type=['pdf', 'docx', 'txt'])
    if uploaded_file:
        content = read_file(uploaded_file)
        input_name = uploaded_file.name
else:
    url_input = st.text_input("Вставте посилання на документ або статтю:")
    if url_input:
        content = read_url(url_input)
        input_name = "url_content"

# --- ПРОЦЕС АНАЛІЗУ ---
if content:
    if st.button("Почати аналіз"):
        with st.spinner('LegalMind вивчає матеріал...'):
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": prompts[mode]},
                        {"role": "user", "content": content}
                    ],
                    model="llama-3.1-8b-instant",
                )
                analysis = chat_completion.choices[0].message.content
                
                st.subheader("📋 Результат аналізу")
                st.markdown(analysis)
                
                # Генерація звіту
                docx_file = create_docx(analysis)
                st.download_button(
                    label="📥 Завантажити звіт у .docx",
                    data=docx_file,
                    file_name=f"LegalMind_{mode}_{input_name}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception as e:
                st.error(f"Помилка при запиті до ШІ: {e}")