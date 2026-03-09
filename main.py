import os
from dotenv import load_dotenv
from groq import Groq # Змінили імпорт

load_dotenv()

# Ініціалізуємо безкоштовного клієнта
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
            model="llama3-8b-8192",
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