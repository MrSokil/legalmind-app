import os
from dotenv import load_dotenv
from groq import Groq 
from docx import Document  # Для Word
from pypdf import PdfReader # Для PDF

load_dotenv()

# Використовуємо ключ з .env
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def read_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    elif ext == '.docx':
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    
    elif ext == '.pdf':
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() for page in reader.pages])
    
    return None

def analyze_legal_text(text):
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": """Ти — старший юрист. Проаналізуй документ за наступним алгоритмом:
                    1. Суть документа (коротко).
                    2. Права та обов'язки сторін: чи немає перекосу на користь однієї сторони?
                    3. Критичні ризики: штрафні санкції, неоднозначні формулювання.
                    4. Рекомендації: що саме потрібно змінити або додати для захисту інтересів клієнта.
                    Відповідь надавай чітко, структуровано, українською мовою."""
                },
                {"role": "user", "content": text}
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Сталася помилка: {e}"

def save_report(analysis_text, original_file):
    report_name = f"report_{os.path.splitext(original_file)[0]}.txt"
    with open(report_name, "w", encoding="utf-8") as f:
        f.write("--- ЮРИДИЧНИЙ ЗВІТ ШІ ---\n")
        f.write(analysis_text)
    return report_name

# ГОЛОВНИЙ ЗАПУСК
file_to_process = "document.txt" # Сюди можна вписати .pdf або .docx файл

if os.path.exists(file_to_process):
    content = read_file(file_to_process)
    if content:
        print(f"Аналізую {file_to_process}...")
        analysis = analyze_legal_text(content)
        report_file = save_report(analysis, file_to_process)
        print(f"--- РЕЗУЛЬТАТ ---\n{analysis}")
        print(f"\n✅ Звіт збережено: {report_file}")
    else:
        print("Формат файлу не підтримується.")
else:
    print(f"Файл {file_to_process} не знайдено.")