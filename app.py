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
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

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
    # Зменшуємо до 5000 символів, щоб точно влізти в 6000 токенів Groq
    chunk_size = 5000 
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
            
            # ПАУЗА: 7 секунд для стабільності на безкоштовному тарифі
            if idx < len(chunks) - 1:
                time.sleep(7) 
                
        except Exception as e:
            if "rate_limit_exceeded" in str(e).lower():
                status_text.warning("⚠️ Ліміт вичерпано. Пауза 15 секунд...")
                time.sleep(15)
                # Можна додати логіку повтору для цієї ж частини тут
            else:
                st.error(f"Помилка на частині {idx+1}: {e}")
                break
    
    status_text.success("✅ Всі частини прочитано! Формую фінальний висновку...")
    combined_context = "\n".join(summaries)
    
    # Фінальний запит теж може бути великим, тому стискаємо combined_context якщо треба
    final_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": mode_prompt},
            {"role": "user", "content": f"Це зміст документа. Проаналізуй його:\n\n{combined_context[:15000]}"}
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
    if st.button("Очистити все"):
        st.session_state.analysis_result = None
        st.session_state.full_content = ""
        st.session_state.search_query = ""
        st.rerun()

prompts = {
    "Аналіз договору": "Ти — провідний юрист. Виділи: 1) Ризики, 2) Штрафи, 3) Статті ЦКУ. Дай поради.",
    "Судова практика та Позови": """Ти — адвокат. Зроби аналіз за схемою:
    1. ПРАВОВА БАЗА: Обов'язково перелічи конкретні статті (наприклад, ст. 328 ЦК, ст. 20 ГК тощо).
    2. ФАКТИЧНІ ОБСТАВИНИ: Що сталося.
    3. ОБГРУНТУВАННЯ: Чому суд прийняв таке рішення.
    БЕЗ ПОСИЛАНЬ НА ЗАКОНОДАВСТВО АНАЛІЗ ВВАЖАЄТЬСЯ НЕПОВНИМ.""",
    "Корпоративні документи": "Ти — спеціаліст з корпоративного права. Перевір на відповідність Закону про ТОВ.",
    "Загальна консультація": "Ти — юридичний радник. Надай відповідь на основі законодавства України."
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

if content:
    if st.button("🚀 Почати повний аналіз"):
        try:
            analysis = analyze_long_text(content, prompts[mode])
            st.session_state.analysis_result = analysis
            st.session_state.full_content = content
            
            # Генеруємо точний пошуковий запит через ШІ
            if mode == "Судова практика та Позови":
                s_gen = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Сформуй 3-4 ключові слова (без зайвих знаків) для Google пошуку аналогічної судової практики на основі цього висновку: {analysis[:300]}"}],
                    model="llama-3.1-8b-instant",
                )
                st.session_state.search_query = s_gen.choices[0].message.content.strip().replace('"', '')
        except Exception as e:
            st.error(f"Помилка: {e}")

# --- ОНОВЛЕНА ЛОГІКА ВИВОДУ (КНОПКИ В СТОВПЧИК) ---
if st.session_state.analysis_result:
    st.subheader("📋 Результат аналізу")
    st.markdown(st.session_state.analysis_result)

    # Створюємо дві колонки для кнопок
    col1, col2 = st.columns(2)
    
    with col1:
        docx_file = create_docx(st.session_state.analysis_result)
        st.download_button(
            label="📥 Завантажити .docx",
            data=docx_file,
            file_name=f"LegalMind_{mode}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )
    
    with col2:
        if mode == "Судова практика та Позови" and st.session_state.search_query:
            # Очищуємо запит від зайвих слів для URL
            clean_q = st.session_state.search_query.split('\n')[0].replace('"', '').strip()
            search_url = f"https://www.google.com/search?q=site:reyestr.court.gov.ua+{clean_q.replace(' ', '+')}"
            
            # Тільки назва дії на кнопці, без тексту від ШІ
            st.link_button(
                "🔍 Знайти схожі рішення", 
                search_url, 
                use_container_width=True
            )
            
    st.markdown("---")
    st.subheader("💬 Питання до документа")
    with st.form("chat_form"):
        user_q = st.text_input("Що саме уточнити в тексті?")
        if st.form_submit_button("Запитати") and user_q:
            with st.spinner('LegalMind шукає відповідь...'):
                # Контекст для чату (перші 12000 символів для уникнення 413)
                chat_context = st.session_state.full_content[:12000]
                chat_res = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Ти — професійний юрист. Відповідай коротко і по суті на основі наданого тексту."},
                        {"role": "user", "content": f"ТЕКСТ:\n{chat_context}\n\nПИТАННЯ: {user_q}"}
                    ],
                    model="llama-3.1-8b-instant",
                )
                st.info(f"💡 **Відповідь:** {chat_res.choices[0].message.content}")