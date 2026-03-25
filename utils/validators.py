import re


def validate_ua_phone(phone: str) -> str | None:
    """Очищує номер та перевіряє, чи він український. Повертає формат 380XXXXXXXXX або None."""
    clean_phone = re.sub(r'\D', '', phone)  # Тільки цифри
    if clean_phone.startswith('0'):
        clean_phone = '38' + clean_phone
    elif clean_phone.startswith('80'):
        clean_phone = '3' + clean_phone

    if re.fullmatch(r'380\d{9}', clean_phone):
        return f"+{clean_phone}"
    return None