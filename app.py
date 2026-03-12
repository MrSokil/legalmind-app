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

# --- ІНІЦІАЛІЗАЦІЯ СТАНУ ---
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'full_content' not in st.session_state:
    st.session_state.full_content = ""
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

# --- ФУНКЦІЇ ОБРОБКИ ФАЙЛІВ ---
def read_file(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext == '.txt': return uploaded_file.read().decode("utf-8")
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
        for s in soup(["script", "style", "header", "footer", "nav"]): s.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Помилка посилання: {e}")
        return None

def create_docx(analysis_text):
    doc = Document()
    doc.add_heading('ЮРИДИЧНИЙ ЗВІТ LEGALMIND', 0)
    doc.add_paragraph(analysis_text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- ЛОГІКА АВТОМАТИЗАЦІЇ ---

def auto_determine_mode(text_preview):
    """ШІ сам визначає тип документа без вибору користувачем"""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Ти — юридичний аналітик. Визнач тип документа. Відповідай ТІЛЬКИ ОДНИМ СЛОВОМ: 'Суд', 'Договір', 'Корпоратив' або 'Загальне'."},
                {"role": "user", "content": text_preview[:3000]}
            ],
            model="llama-3.1-8b-instant",
        )
        detected = response.choices[0].message.content.strip().replace('.', '')
        mapping = {
            "Суд": "Судова практика та Позови",
            "Договір": "Аналіз договору",
            "Корпоратив": "Корпоративні документи"
        }
        return mapping.get(detected, "Загальна консультація")
    except:
        return "Загальна консультація"

def analyze_long_text(full_text, mode_prompt):
    """Швидкий аналіз великих текстів"""
    chunk_size = 7500 
    chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
    
    summaries = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, chunk in enumerate(chunks):
        status_text.info(f"⚡ Аналіз частини {idx+1} з {len(chunks)}...")
        progress_bar.progress((idx + 1) / len(chunks))
        
        try:
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Ти — помічник юриста. Випиши головне, статті та факти."},
                    {"role": "user", "content": chunk}
                ],
                model="llama-3.1-8b-instant",
            )
            summaries.append(response.choices[0].message.content)
            if idx < len(chunks) - 1:
                time.sleep(2.2) # Оптимальна пауза для швидкості
        except Exception as e:
            if "rate_limit_exceeded" in str(e).lower():
                status_text.warning("⚠️ Ліміт. Пауза 10 сек...")
                time.sleep(10)
            else:
                st.error(f"Помилка: {e}")
                break
    
    combined_context = "\n".join(summaries)
    final_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": mode_prompt},
            {"role": "user", "content": f"Сформуй звіт на основі цих даних:\n\n{combined_context[:18000]}"}
        ],
        model="llama-3.1-8b-instant",
    )
    status_text.empty()
    progress_bar.empty()
    return final_response.choices[0].message.content

# --- ПРОМПТИ ---
prompts = {
    "Аналіз договору": "### ⚖️ ЮРИДИЧНА БАЗА\n- (статті ЦКУ/ГКУ)\n### 🚩 РИЗИКИ\n- (тезисно)\n### 📝 ПОРАДИ\n- (що змінити)",
    "Судова практика та Позови": "### ⚖️ ЮРИДИЧНА БАЗА (СТАТТІ)\n- Випиши кожну статтю окремим пунктом з назвою\n### 📌 ОСНОВНІ ТЕЗИ\n- (головні аргументи суду)\n### 📑 СУТЬ СПРАВИ\n- (коротко)",
    "Корпоративні документи": "Проаналізуй документ на відповідність Закону про ТОВ.",
    "Загальна консультація": "Надай юридичну відповідь зі статтями законів у вигляді списку."
}

# --- ІНТЕРФЕЙС ---
st.title("⚖️ LegalMind: Ваш AI-Юрист")
st.markdown("---")

# ЧИСТА БІЧНА ПАНЕЛЬ
with st.sidebar:
    st.title("⚙️ Налаштування")
    if st.button("🧹 Очистити все"):
        for key in st.session_state.keys(): del st.session_state[key]
        st.rerun()

source = st.radio("Джерело:", ["Файл", "Посилання"], horizontal=True)
content = ""

if source == "Файл":
    uploaded_file = st.file_uploader("Завантажте документ", type=['pdf', 'docx', 'txt'])
    if uploaded_file: content = read_file(uploaded_file)
else:
    url_input = st.text_input("Вставте посилання:")
    if url_input: content = read_url(url_input)

if content:
    # ТІЛЬКИ ОДНА КНОПКА БЕЗ ВИБОРУ РЕЖИМІВ
    if st.button("🚀 ПОЧАТИ РОЗУМНИЙ АНАЛІЗ", use_container_width=True):
        try:
            with st.spinner('🔍 AI розпізнає документ та проводить аналіз...'):
                mode = auto_determine_mode(content)
                st.toast(f"📂 Виявлено тип: {mode}")
                
                analysis = analyze_long_text(content, prompts[mode])
                st.session_state.analysis_result = analysis
                st.session_state.full_content = content
                
                if "Суд" in mode:
                    s_gen = client.chat.completions.create(
                        messages=[{"role": "user", "content": f"3-4 ключові слова для Google (без лапок): {analysis[:300]}"}],
                        model="llama-3.1-8b-instant",
                    )
                    st.session_state.search_query = s_gen.choices[0].message.content.strip().replace('"', '')
                else:
                    st.session_state.search_query = ""
        except Exception as e:
            st.error(f"Помилка: {e}")

# --- ВИВІД РЕЗУЛЬТАТІВ ---
if st.session_state.analysis_result:
    st.subheader("📋 Результат аналізу")
    st.markdown(st.session_state.analysis_result)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Завантажити .docx", data=create_docx(st.session_state.analysis_result), file_name="LegalReport.docx", use_container_width=True)
    with col2:
        if st.session_state.search_query:
            clean_q = st.session_state.search_query.split('\n')[0].replace(' ', '+')
            st.link_button("🔍 Знайти схожі рішення", f"https://www.google.com/search?q=site:reyestr.court.gov.ua+{clean_q}", use_container_width=True)

    st.markdown("---")
    st.subheader("💬 Питання до документа")
    with st.form("chat_form"):
        user_q = st.text_input("Що уточнити?")
        if st.form_submit_button("Запитати") and user_q:
            res = client.chat.completions.create(
                messages=[{"role": "system", "content": "Ти юрист. Відповідай по тексту."}, {"role": "user", "content": f"ТЕКСТ:\n{st.session_state.full_content[:12000]}\n\nПИТАННЯ: {user_q}"}],
                model="llama-3.1-8b-instant",
            )
            st.info(f"💡 {res.choices[0].message.content}")