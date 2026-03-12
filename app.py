import streamlit as st
import os
import requests
import time
import sqlite3
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

# --- РОБОТА З БАЗОЮ ДАНИХ (ВІЧНА ІСТОРІЯ) ---
def init_db():
    conn = sqlite3.connect('legalmind_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT, result TEXT, content TEXT, query TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_to_history(title, result, content, query):
    conn = sqlite3.connect('legalmind_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (title, result, content, query) VALUES (?, ?, ?, ?)", 
              (title, result, content, query))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect('legalmind_history.db')
    c = conn.cursor()
    c.execute("SELECT title, result, content, query FROM history ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    return rows

def clear_db():
    if os.path.exists('legalmind_history.db'):
        os.remove('legalmind_history.db')
    init_db()

# Ініціалізація БД при запуску
init_db()

# --- ІНІЦІАЛІЗАЦІЯ СТАНУ ---
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'full_content' not in st.session_state:
    st.session_state.full_content = ""
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

# --- ФУНКЦІЇ ОБРОБКИ ТЕКСТУ (БЕЗ ЗМІН) ---
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

def auto_determine_mode(text_preview):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Ти — юридичний аналітик. Визнач тип документа одним словом: 'Суд', 'Договір', 'Корпоратив' або 'Загальне'."},
                {"role": "user", "content": text_preview[:3000]}
            ],
            model="llama-3.1-8b-instant",
        )
        detected = response.choices[0].message.content.strip().replace('.', '')
        mapping = {"Суд": "Судова практика та Позови", "Договір": "Аналіз договору", "Корпоратив": "Корпоративні документи"}
        return mapping.get(detected, "Загальна консультація")
    except: return "Загальна консультація"

def analyze_long_text(full_text, mode_prompt):
    chunk_size = 7500 
    chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
    summaries = []
    p_bar = st.progress(0)
    for idx, chunk in enumerate(chunks):
        p_bar.progress((idx + 1) / len(chunks))
        try:
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": "Ти помічник юриста. Випиши головне."}, {"role": "user", "content": chunk}],
                model="llama-3.1-8b-instant",
            )
            summaries.append(response.choices[0].message.content)
            if idx < len(chunks) - 1: time.sleep(2.2)
        except Exception as e:
            if "rate_limit" in str(e): time.sleep(10)
            else: break
    
    combined = "\n".join(summaries)
    final = client.chat.completions.create(
        messages=[{"role": "system", "content": mode_prompt}, {"role": "user", "content": combined[:18000]}],
        model="llama-3.1-8b-instant",
    )
    p_bar.empty()
    return final.choices[0].message.content

# --- ПРОМПТИ ---
prompts = {
    "Судова практика та Позови": """Ти — провідний адвокат із 20-річним стажем. Твоє завдання: знайти слабкі місця в матеріалах та підсилити позицію клієнта. 
    
    Сформуй звіт за наступною суворою структурою:

    ### 🛡️ СТРАТЕГІЧНИЙ АНАЛІЗ ПОЗИЦІЇ
    - **Сильні сторони**: Які факти грають на користь клієнта?
    - **Критичні ризики**: Де позиція найбільш вразлива?

    ### ⚖️ ПЕРЕВІРКА ПРОЦЕСУАЛЬНОЇ ЧИСТОТИ (КЛЮЧОВЕ)
    - Проаналізуй, чи не було порушено процедуру (наприклад, для ст. 130 КУпАП — чи були свідки, чи сертифікований Драгер, чи дотримано строки).
    - Вкажи конкретні статті (наприклад, ст. 251, 268 КУпАП), які допоможуть визнати докази недопустимими.

    ### 📖 РЕКОМЕНДОВАНА ЮРИДИЧНА БАЗА
    - Склади список статей законів та постанов Пленуму ВС, які ТРЕБА додати до позову.
    - Для кожної статті напиши 1 речення: "Це дозволить нам довести, що..."

    ### 📝 ПЛАН ДІЙ (STEP-BY-STEP)
    - Які конкретно клопотання подати (про виклик свідків, про витребування відео з боді-камер тощо)?
    - Яких документів не вистачає в матеріалах справи прямо зараз?

    **Стиль відповіді:** Професійний, гострий, орієнтований на результат. Уникай загальних фраз типу "ознайомтеся з нормами".""",

    "Аналіз договору": """Ти — юридичний аудитор. Твоя мета — знайти "пастки" в договорі.
    ### 🚩 ЧЕРВОНІ ПРАПОРЦІ (РИЗИКИ)
    - Знайди приховані штрафи, пеню та умови одностороннього розірвання.
    ### ⚖️ ПОСИЛЕННЯ ПОЗИЦІЇ
    - Які статті ЦКУ/ГКУ захистять клієнта у разі форс-мажору (наприклад, ст. 617 ЦКУ)?
    ### ✏️ РЕКОМЕНДОВАНІ ПРАВКИ
    - Напиши готові формулювання пунктів, які варто змінити (Було -> Стало)."""
}

# --- БІЧНА ПАНЕЛЬ (ВИПРАВЛЕНА) ---
with st.sidebar:
    st.title("⚙️ Налаштування")
    if st.button("🧹 Очистити все"):
        clear_db()
        # Повне очищення стану
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    st.subheader("📜 Вічна історія")
    
    # Отримуємо дані з БД (тепер додаємо ID)
    conn = sqlite3.connect('legalmind_history.db')
    c = conn.cursor()
    c.execute("SELECT id, title, result, content, query FROM history ORDER BY id DESC LIMIT 20")
    history_rows = c.fetchall()
    conn.close()

    if not history_rows:
        st.info("Історія порожня")
    else:
        for h_id, h_title, h_res, h_cont, h_qry in history_rows:
            # Використовуємо стабільний ключ на основі ID бази даних
            if st.button(f"📄 {h_title[:25]}...", key=f"btn_{h_id}", use_container_width=True):
                st.session_state.analysis_result = h_res
                st.session_state.full_content = h_cont
                st.session_state.search_query = h_qry
                st.rerun()

# --- ГОЛОВНИЙ ІНТЕРФЕЙС ---
st.title("⚖️ LegalMind: Ваш AI-Юрист")
st.markdown("---")

source = st.radio("Джерело:", ["Файл", "Посилання"], horizontal=True)
content = ""

if source == "Файл":
    uploaded_file = st.file_uploader("Завантажте документ", type=['pdf', 'docx', 'txt'])
    if uploaded_file: content = read_file(uploaded_file)
else:
    url_input = st.text_input("Вставте посилання:")
    if url_input: content = read_url(url_input)

if content:
    if st.button("🚀 ПОЧАТИ АНАЛІЗ", use_container_width=True):
        try:
            with st.spinner('🔍 AI працює...'):
                mode = auto_determine_mode(content)
                st.toast(f"📂 Режим: {mode}")
                analysis = analyze_long_text(content, prompts[mode])
                
                # Пошуковий запит для суду
                s_query = ""
                if "Суд" in mode:
                    sg = client.chat.completions.create(
                        messages=[{"role": "user", "content": f"3 ключові слова: {analysis[:200]}"}],
                        model="llama-3.1-8b-instant",
                    )
                    s_query = sg.choices[0].message.content.strip().replace('"', '')
                
                # ЗБЕРЕЖЕННЯ В БАЗУ
                doc_name = url_input if source == "Посилання" else uploaded_file.name
                save_to_history(doc_name, analysis, content, s_query)
                
                st.session_state.analysis_result = analysis
                st.session_state.full_content = content
                st.session_state.search_query = s_query
        except Exception as e:
            st.error(f"Помилка: {e}")

# --- ЛОГІКА ВІДОБРАЖЕННЯ (ПЕРЕВІРКА) ---
# Переконайтеся, що блок виводу результатів знаходиться ПОЗА блоком "if content"
# Це дозволить показувати дані з історії, навіть якщо зараз не завантажено новий файл

if st.session_state.analysis_result:
    st.markdown("---")
    st.subheader("📋 Результат аналізу")
    st.markdown(st.session_state.analysis_result)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Завантажити .docx", 
            data=create_docx(st.session_state.analysis_result), 
            file_name="LegalReport.docx", 
            use_container_width=True
        )
    with col2:
        if st.session_state.search_query:
            # Очищення запиту для URL
            clean_q = st.session_state.search_query.split('\n')[0].strip().replace(' ', '+')
            st.link_button(
                "🔍 Схожі рішення", 
                f"https://www.google.com/search?q=site:reyestr.court.gov.ua+{clean_q}", 
                use_container_width=True
            )

    # Форма чату також має бути доступна для даних з історії
    st.markdown("---")
    with st.form("chat_history_form"):
        user_q = st.text_input("Питання до цього документа:")
        if st.form_submit_button("Запитати") and user_q:
            with st.spinner('Шукаю відповідь...'):
                r = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Ти юрист професіонал."},
                        {"role": "user", "content": f"Текст: {st.session_state.full_content[:10000]}\nПитання: {user_q}"}
                    ],
                    model="llama-3.1-8b-instant",
                )
                st.info(f"💡 {r.choices[0].message.content}")