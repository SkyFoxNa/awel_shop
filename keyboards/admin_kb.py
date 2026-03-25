from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from utils.states import AdminUserAction

# 1. Головне меню Панелі Керування
def get_admin_panel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    # Ряд 1: Текстові кнопки для Reply-меню
    builder.row(
        KeyboardButton(text="👥 Користувачі"),
        KeyboardButton(text="📢 Акції")  # Нова кнопка
    )
    builder.row(KeyboardButton(text="🏠")) # Повернення до головного меню
    return builder.as_markup(resize_keyboard=True)

# 2. Список користувачів (пагінація)
def get_user_list_kb(users, page: int, is_search=False):
    builder = InlineKeyboardBuilder()
    for u in users:
        label = f"{u.user_surname or ''} {u.user_name} | {u.phone or '---'}"
        builder.button(text=label, callback_data=AdminUserAction(action="view", user_db_id=u.id))
    builder.adjust(1)

    if not is_search:
        builder.row(InlineKeyboardButton(text="🔍 Пошук за даними", callback_data="start_user_search"))
    else:
        builder.row(InlineKeyboardButton(text="🔄 Скинути пошук", callback_data="refresh_user_list"))
    return builder.as_markup()

# 3. Клавіатура для Картки Клієнта
def get_user_card_kb(user):
    builder = InlineKeyboardBuilder()
    lock_icon = "🔒" if user.is_locked else "🔓"
    active_icon = "✅" if user.is_active else "🚫"

    builder.row(
        InlineKeyboardButton(text="🎭 Ролі", callback_data=AdminUserAction(action="edit_roles", user_db_id=user.id).pack()),
        InlineKeyboardButton(text=f"{active_icon} Статус", callback_data=AdminUserAction(action="toggle_active", user_db_id=user.id).pack())
    )
    builder.row(
        InlineKeyboardButton(text=f"{lock_icon} Замок 1С", callback_data=AdminUserAction(action="toggle_lock", user_db_id=user.id).pack()),
        InlineKeyboardButton(text="📝 Нотатка", callback_data=AdminUserAction(action="edit_note", user_db_id=user.id).pack())
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminUserAction(action="list", user_db_id=0).pack()))
    return builder.as_markup()