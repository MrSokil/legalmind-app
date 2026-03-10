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

# Отримання ключа
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
    # Розбиваємо текст на шматки по 12000 символів (щоб не перевищити ліміти)
    chunk_size = 12000
    chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
    
    summaries = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, chunk in enumerate(chunks):
        status_text.text(f"Опрацювання частини {idx+1} з {len(chunks)}...")
        progress_bar.progress((idx + 1) / len(chunks))
        
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Ти — помічник юриста. Коротко випиши всі ключові факти, норми та деталі з цієї частини документа для подальшого аналізу."},
                {"role": "user", "content": chunk}
            ],
            model="llama-3.1-8b-instant",
        )
        summaries.append(response.choices[0].message.content)
    
    status_text.text("Формування фінального висновку...")
    combined_context = "\n".join(summaries)
    
    final_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": mode_prompt},
            {"role": "user", "content": f"Це зібрана інформація з усього документа. Проаналізуй її повністю:\n\n{combined_context}"}
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
input_name = "document"

if source == "Файл":
    uploaded_file = st.file_uploader("Завантажте документ", type=['pdf', 'docx', 'txt'])
    if uploaded_file:
        content = read_file(uploaded_file)
        input_name = uploaded_file.name
else:
    url_input = st.text_input("Вставте посилання:")
    if url_input:
        content = read_url(url_input)
        input_name = "web_content"

if content:
    if st.button("Почати повний аналіз"):
        try:
            analysis = analyze_long_text(content, prompts[mode])
            
            st.subheader("📋 Результат аналізу")
            st.markdown(analysis)

            # Розумний пошук практики
            if mode == "Судова практика та Позови":
                st.markdown("---")
                st.subheader("⚖️ Пошук аналогічних рішень")
                search_gen = client.chat.completions.create(
                    messages=[{"role": "user", "content": f"Сформуй короткий пошуковий запит (3-5 слів) для реєстру судових рішень на основі цього: {analysis[:500]}"}],
                    model="llama-3.1-8b-instant",
                )
                query = search_gen.choices[0].message.content.strip().replace('"', '')
                search_url = f"https://www.google.com/search?q=site:reyestr.court.gov.ua+{query.replace(' ', '+')}"
                st.link_button(f"🔍 Знайти схожі рішення за запитом: {query}", search_url)

            # Завантаження звіту
            docx_file = create_docx(analysis)
            st.download_button(
                label="📥 Завантажити звіт у .docx",
                data=docx_file,
                file_name=f"LegalMind_{mode}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        except Exception as e:
            st.error(f"Сталася помилка: {e}")