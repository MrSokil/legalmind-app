import streamlit as st
import os
import requests
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq
from docx import Document
from pypdf import PdfReader
from io import BytesIO

load_dotenv()

# Налаштування сторінки
st.set_page_config(page_title="LegalMind", page_icon="⚖️", layout="centered")

# Отримання ключа
api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

# --- ІНІЦІАЛІЗАЦІЯ СТАНУ (SESSION STATE) ---
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'full_content' not in st.session_state:
    st.session_state.full_content = ""

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

def analyze_long_text(full_text, mode_prompt):
    # Використовуємо 8000 символів для балансу швидкості та лімітів
    chunk_size = 8000
    chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
    
    summaries = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, chunk in enumerate(chunks):
        status_text.info(f"⚡ Опрацювання частини {idx+1} з {len(chunks)}...")
        progress_bar.progress((idx + 1) / len(chunks))
        
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Ти — помічник юриста. Випиши тезисно головне з цієї частини документа."},
                    {"role": "user", "content": chunk}
                ],
                model="llama-3.1-8b-instant",
            )
            summaries.append(response.choices[0].message.content)
            
            # Пауза для безкоштовного тарифу (Rate Limit)
            if idx < len(chunks) - 1:
                status_text.warning("☕ Пауза 5 сек для стабільності лімітів...")
                time.sleep(5)
                
        except Exception as e:
            st.error(f"Помилка на частині {idx+1}: {e}")
            break
    
    status_text.success("✅ Всі частини прочитано! Формую фінальний звіт...")
    combined_context = "\n".join(summaries)
    
    final_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": mode_prompt},
            {"role": "user", "content": f"Це зміст великого документа. Проаналізуй його повністю:\n\n{combined_context}"}
        ],
        model="llama-3.1-8b-instant",
    )
    return final_response.choices[0].message.content

# --- БІЧНА ПАНЕЛЬ ---
with st.sidebar:
    st.title("⚙️ Налаштування")
    mode = st.selectbox(
        "Оберіть режим аналізу:",
        ["Аналіз договору", "Судова практика та Позови", "Корпоративні документи", "Загальна консультація"]
    )
    st.info(f"Активний режим: **{mode}**")
    if st.button("Очистити все"):
        st.session_state.analysis_result = None
        st.session_state.full_content = ""
        st.rerun()

prompts = {
    "Аналіз договору": "Ти — провідний юрист. Проаналізуй цей договір на предмет прихованих ризиків, термінів, штрафних санкцій та відповідності ЦКУ. Виділи критичні помилки.",
    "Судова практика та Позови": "Ти — адвокат. Проаналізуй цей документ. Знайди слабкі місця в аргументації, перевір посилання на статті ЦПК/ГПК та запропонуй покращення на основі актуальної практики.",
    "Корпоративні документи": "Ти — спеціаліст з корпоративного права. Перевір цей статут або протокол на відповідність закону про ТОВ, знайди ризики та помилки в процедурах.",
    "Загальна консультація": "Ти — універсальний юридичний радник. Проаналізуй текст та надай відповідь на основі законодавства України."
}

# --- ІНТЕРФЕЙС ---
st.title("⚖️ LegalMind: Ваш AI-Юрист")
st.markdown("---")

source = st.radio("Джерело аналізу:", ["Файл", "Посилання"], horizontal=True)
content = ""

if source == "Файл":
    uploaded_file = st.file_uploader("Завантажте документ", type=['pdf', 'docx', 'txt'])
    if uploaded_file:
        content = read_file(uploaded_file)
else:
    url_input = st.text_input("Вставте посилання:")
    if url_input:
        content = read_url(url_input)

# Кнопка запуску
if content:
    if st.button("🚀 Почати повний аналіз"):
        try:
            analysis = analyze_long_text(content, prompts[mode])
            st.session_state.analysis_result = analysis
            st.session_state.full_content = content
        except Exception as e:
            st.error(f"Сталася помилка: {e}")

# --- ВИВІД РЕЗУЛЬТАТІВ ТА ЧАТ ---
if st.session_state.analysis_result:
    st.subheader("📋 Результат аналізу")
    st.markdown(st.session_state.analysis_result)

    # Пошук практики (тільки в цьому режимі)
    if mode == "Судова практика та Позови":
        search_query = st.session_state.analysis_result[:100].replace('\n', ' ')
        search_url = f"https://www.google.com/search?q=site:reyestr.court.gov.ua+{search_query}"
        st.link_button("🔍 Знайти схожі рішення в Реєстрі", search_url)

    # Кнопка завантаження звіту
    docx_file = create_docx(st.session_state.analysis_result)
    st.download_button(
        label="📥 Завантажити звіт у .docx",
        data=docx_file,
        file_name=f"LegalMind_{mode}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    st.markdown("---")
    st.subheader("💬 Чат з документом")
    
    with st.form("chat_form"):
        user_question = st.text_input("Поставте питання до тексту (наприклад: 'Хто відповідач?' або 'Який строк оренди?')")
        submit_chat = st.form_submit_button("Запитати")
        
        if submit_chat and user_question:
            with st.spinner('LegalMind шукає відповідь...'):
                # Беремо частину тексту для контексту чату (щоб не перевищити 413)
                context_for_chat = st.session_state.full_content[:12000]
                chat_res = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Ти — професійний юрист. Відповідай на питання користувача виключно на основі наданого тексту документа."},
                        {"role": "user", "content": f"ДОКУМЕНТ:\n{context_for_chat}\n\nПИТАННЯ: {user_question}"}
                    ],
                    model="llama-3.1-8b-instant",
                )
                st.info(f"💡 **Відповідь:** {chat_res.choices[0].message.content}")