import os

def read_legal_document(file_path):
    # Перевіряємо, чи існує файл
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return content
    else:
        return "Файл не знайдено."

# Шлях до нашого документа
file_name = "document.txt"
text = read_legal_document(file_name)

print("--- Звіт асистента ---")
print(f"Текст завантажено. Кількість символів: {len(text)}")
print(f"Перші 50 символів: {text[:50]}...")