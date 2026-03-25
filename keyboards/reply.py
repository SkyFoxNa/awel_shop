from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db.models import User

# Константи для кнопок
BTN_HOME = "🏠"
BTN_PROMO = "🔥 Акції"
BTN_NEWS = "📰 Новини"
BTN_CARD = "🪪 КАРТКА"
BTN_CATALOG = "🛒 Каталог"
BTN_ORDERS = "📦 Замовлення"
BTN_PROFILE = "👤 Профіль"
BTN_DISCOUNTS = "💰 Знижки"
BTN_ADMIN = "🛠 Панель керування"
BTN_HELP = "❓ Допомога"
BTN_ABOUT = "ℹ️ Про нас"


def get_main_kb(user: User) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    # Отримуємо назви ролей безпечно
    # Примітка: переконайтеся, що об'єкт user завантажений з options(selectinload(User.roles))
    user_role_names = [r.role.name for r in user.roles] if user.roles else []

    # 1. Верхній ряд: Головна, Акції та Новини
    builder.row(
        KeyboardButton(text=BTN_HOME),
        KeyboardButton(text=BTN_PROMO),
        KeyboardButton(text=BTN_NEWS)
    )

    # 2. Основний блок Клієнта
    builder.row(KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_ORDERS))
    builder.row(KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_DISCOUNTS))

    # 3. Сервісний блок
    builder.row(KeyboardButton(text=BTN_HELP), KeyboardButton(text=BTN_ABOUT))
    builder.row(KeyboardButton(text=BTN_CARD))

    # 4. Блок Адміністрації
    if any(role in user_role_names for role in ["admin", "manager", "seller", "owner"]):
        builder.row(KeyboardButton(text=BTN_ADMIN))

    # Налаштовуємо сітку
    builder.adjust(3, 2, 2, 2, 2)

    return builder.as_markup(resize_keyboard=True)