import os
from dotenv import load_dotenv
from groq import Groq 

load_dotenv()

# Ми ігноруємо відсутність файлу .env і вказуємо ключ прямо тут
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# БЛОК ПЕРЕВІРКИ МОЖНА ТИМЧАСОВО ВИДАЛИТИ АБО ЗАКОМЕНТУВАТИ
# if not api_key:
#     print("ПОМИЛКА...")
#     exit()

def analyze_legal_text(text):
    try:
        chat_completion = client.chat.completions.create(
            # Використовуємо модель Llama-3 (дуже потужна і безкоштовна)
            messages=[
                {
                    "role": "system",
                    "content": "Ти — експерт-юрист. Твоє завдання: коротко проаналізувати наданий текст закону або договору та виділити головні ризики чи суть українською мовою."
                },
                {
                    "role": "user",
                    "content": text,
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Сталася помилка: {e}"

# Читаємо наш файл document.txt
if os.path.exists("document.txt"):
    with open("document.txt", "r", encoding="utf-8") as f:
        content = f.read()
    
    print("ШІ аналізує юридичний документ (через Groq)...")
    analysis = analyze_legal_text(content)
    
    print("\n--- РЕЗУЛЬТАТ АНАЛІЗУ ---")
    print(analysis)
else:
    print("Помилка: Створіть файл document.txt з текстом закону.")

# Функція для збереження звіту
def save_report(analysis_text, original_file):
    report_name = f"report_{original_file}"
    with open(report_name, "w", encoding="utf-8") as f:
        f.write("--- ЮРИДИЧНИЙ ЗВІТ ШІ ---\n")
        f.write(analysis_text)
    return report_name

# Викликаємо збереження після аналізу
report_file = save_report(analysis, "document.txt")
print(f"\n✅ Звіт збережено у файл: {report_file}")