from aiogram.fsm.state import State, StatesGroup


# Стан для пошуку
class SearchProduct(StatesGroup):
    find_product_query = State()


# Стан для пошуку номенклатури
class SearchNomenclature(StatesGroup):
    find_nomenclature_query = State()


class EditProduct(StatesGroup):
    menu = State()  # ми в меню редагування конкретного товару
    waiting_storage = State()  # очікуємо ввід комірки
    waiting_balance = State()  # очікуємо ввід залишку
    waiting_photo_folder = State()  # ⬅ новий стан для фото


class EditeQuipment(StatesGroup):
    menu = State()
    edit_equipment = State()
    wait_component_code = State()
    wait_component_quantity = State()
    set_package_id = State()
    wait_component_sticker = State()


class PackageAdd(StatesGroup):
    choose_type = State()
    name = State()
    balance = State()
    info = State()
    price = State()


class PackageEdit(StatesGroup):
    choose_field = State()
    enter_value = State()


class PackageAnalogues(StatesGroup):
    viewing = State()  # перегляд аналогів конкретного пакування
    adding = State()  # вибір пакування для додавання як аналога


class PackagingTypeAdd(StatesGroup):
    name = State()  # введення назви типу пакування


class CustomerAdd(StatesGroup):
    choose_type = State()
    name = State()
    phone = State()
    shipping_info = State()
    discount = State()
    note = State()
    packaging_type = State()


class InvoiceStates(StatesGroup):
    choosing_supplier = State()  # Вибір постачальника (supplier)
    choosing_date = State()  # Введення дати
    choosing_receiver = State()  # Вибір отримувача (receiver)
    confirming = State()  # Завершення (створення накладної)


class StatisticsStates(StatesGroup):
    choosing_order_type = State()
    choosing_customer = State()
    choosing_date_range_type = State()
    choosing_start_date = State()
    choosing_end_date = State()
    choosing_invoice = State()
    choosing_next_page = State()


class OrderStates(StatesGroup):
    waiting_for_action = State()  # користувач обрав замовлення, чекаємо дію

# Додавання товару у ручному режимі
class AddProductState(StatesGroup):
    code = State() # Код товару
    name = State() # назва товару


class KitComponentAdd(StatesGroup):
    choosing_category = State()  # Вибір категорії
    choosing_product = State()   # Вибір конкретного товару з категорії