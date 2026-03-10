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

# --- БІЧНА ПАНЕЛЬ (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Налаштування")
    
    # Додаємо перемикач режимів
    mode = st.selectbox(
        "Оберіть режим аналізу:",
        [
            "Аналіз договору", 
            "Судова практика та Позови", 
            "Корпоративні документи", 
            "Загальна консультація"
        ]
    )
    
    st.info(f"Зараз активний режим: **{mode}**")
    
    if st.button("Очистити все"):
        st.rerun()

# --- ЛОГІКА ПЕРСОНАЛІЗАЦІЇ ШІ ---
prompts = {
    "Аналіз договору": "Ти — провідний юрист. Проаналізуй цей договір на предмет прихованих ризиків, термінів, штрафних санкцій та відповідності ЦКУ. Виділи критичні помилки.",
    "Судова практика та Позови": "Ти — адвокат. Проаналізуй цей документ (позов чи клопотання). Знайди слабкі місця в аргументації, перевір посилання на статті ЦПК/ГПК та запропонуй покращення на основі актуальної практики.",
    "Корпоративні документи": "Ти — спеціаліст з корпоративного права. Перевір цей статут або протокол на відповідність закону про ТОВ, знайди ризики для засновників та помилки в процедурах прийняття рішень.",
    "Загальна консультація": "Ти — універсальний юридичний радник. Проаналізуй текст та надай вичерпну відповідь на питання користувача, базуючись на законодавстві України."
}

# Коли викликаєте client.chat.completions.create, використовуйте prompt відповідно до вибору:
# system_prompt = prompts[mode]