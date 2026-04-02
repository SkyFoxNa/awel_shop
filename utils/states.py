from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.callback_data import CallbackData

class AdminUserSearch(StatesGroup):
    waiting_for_query = State()  # Стан очікування тексту для пошуку

class AdminUserAction(CallbackData, prefix="adm_u"):
    action: str  # "list", "view", "edit_roles", "toggle_role", "search"
    user_db_id: int
    page: int = 0
    role_id: int = 0

class AdminUserEdit(StatesGroup):
    waiting_for_balance = State()
    waiting_for_note = State()
    waiting_for_discount = State()

#     Акції
class AdminPromoAdd(StatesGroup):
    waiting_for_title = State()    # Назва акції
    waiting_for_desc = State()     # Опис
    waiting_for_image = State()    # Фото
    waiting_for_type = State()     # Тип (Дія/Товар)
    waiting_for_role = State()     # Цільова роль
    waiting_for_points = State()   # Кількість бонусів
    waiting_for_link = State()     # Посилання

class CatalogState(StatesGroup):
    waiting_for_search_query = State() # Очікуємо текст для пошуку

# новини
class NewsStates(StatesGroup):
    waiting_for_title = State()      # Заголовок
    waiting_for_content = State()    # Опис
    waiting_for_photo = State()      # Фото
    waiting_for_product = State()    # Код товару (необов'язково)
    confirm_news = State()           # Фінальне прев'ю та збереження

class NewsAdminStates(StatesGroup):
    in_editor = State()         # Основний стан перегляду чернетки
    waiting_for_field = State()  # Очікування введення конкретного поля