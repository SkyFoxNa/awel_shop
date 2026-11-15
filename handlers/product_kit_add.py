# handlers/product_kit_add.py
import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from django.db.models import Q

from shop.models import Product, ProductComponent, Location
from services.states import KitAddProcess
from .product_package import delete_kit_messages, send_kit_list

router = Router()
logger = logging.getLogger(__name__)


# ==============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ ОЧИЩЕННЯ ПОВІДОМЛЕНЬ ПРОЦЕСУ ДОДАВАННЯ
# ==============================================================================

async def track_add_msg(state: FSMContext, *msg_ids: int):
    """Додає ID повідомлень до списку для подальшого видалення"""
    data = await state.get_data()
    tracked = data.get("add_kit_msg_ids", [])
    tracked.extend(msg_ids)
    await state.update_data(add_kit_msg_ids=tracked)


async def clear_add_kit_messages(event: types.TelegramObject, state: FSMContext):
    """Видаляє всі накопичені проміжні повідомлення процесу додавання"""
    data = await state.get_data()
    msg_ids = data.get("add_kit_msg_ids", [])
    chat_id = event.from_user.id

    for m_id in msg_ids:
        try:
            await event.bot.delete_message(chat_id=chat_id, message_id=m_id)
        except Exception:
            pass

    await state.update_data(add_kit_msg_ids=[])


# ==============================================================================
# 1. СТАРТ ДОДАВАННЯ -> ЗАПИТ ПОШУКУ
# ==============================================================================

@router.callback_query(F.data.startswith("add_kit_item:"))
async def start_add_kit_item(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    parent_code = parts[1]
    item_type = parts[2]  # 'product', 'boxing', або 'sticker'

    await delete_kit_messages(callback, state)
    await clear_add_kit_messages(callback, state)

    await state.update_data(
        parent_code=parent_code,
        item_type=item_type
    )
    await state.set_state(KitAddProcess.searching)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Скасувати", callback_data=f"kit_{parent_code}"))

    type_titles = {
        "product": "товару для комплекту",
        "boxing": "тари (упаковки)",
        "sticker": "наліпки"
    }

    msg = await callback.message.answer(
        f"🔍 <b>Пошук {type_titles.get(item_type, 'компонента')}</b>\n\n"
        f"Введіть назву, код або каталожний номер:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await track_add_msg(state, msg.message_id)
    await callback.answer()


# ==============================================================================
# 2. ОБРОБКА ПОШУКУ -> ВИДАЛЕННЯ ЗАПИТУ, ВИВІД РЕЗУЛЬТАТІВ З ФІЛЬТРАЦІЄЮ
# ==============================================================================

@router.message(KitAddProcess.searching)
async def process_kit_search_input(message: types.Message, state: FSMContext):
    # Одразу запам'ятовуємо ID повідомлення користувача, щоб прибрати його
    await track_add_msg(state, message.message_id)

    query = message.text.strip()
    if len(query) < 2:
        warn_msg = await message.answer("⚠️ Запит занадто короткий. Введіть мінімум 2 символи.")
        await track_add_msg(state, warn_msg.message_id)
        return

    # Очищуємо попередній запит бота, повідомлення користувача та можливі попередження
    await clear_add_kit_messages(message, state)

    data = await state.get_data()
    parent_code = data.get("parent_code")
    item_type = data.get("item_type")  # 'product', 'boxing', або 'sticker'

    # Базовий пошуковий фільтр за текстом (код, назва, каталожний номер) та виключення самого себе
    base_qs = Product.objects.filter(
        Q(code__icontains=query) | Q(name_ua__icontains=query) | Q(catalog_number__icontains=query)
    ).exclude(code=parent_code)

    # Застосовуємо фільтр в залежності від обраного типу компонента
    if item_type == "boxing":
        # Якщо шукаємо тару (можливо, у вас є спеціальне поле чи категорія, наприклад is_boxing=True або фільтрація за назвою/категорією)
        # Якщо тара це звичайний товар з прапорцем або певній категорії, адаптуйте умову нижче:
        qs = base_qs.filter(is_boxing=True) if hasattr(Product, 'is_boxing') else base_qs.filter(
            Q(name_ua__icontains="тара") | Q(name_ua__icontains="ящик") | Q(name_ua__icontains="коробка")
        )
    elif item_type == "sticker":
        # Якщо шукаємо наліпку
        qs = base_qs.filter(is_sticker=True) if hasattr(Product, 'is_sticker') else base_qs.filter(
            Q(name_ua__icontains="наліпка") | Q(name_ua__icontains="етикетка") | Q(name_ua__icontains="стікер")
        )
    else:
        # Звичайний товар комплекту (виключаємо тару та наліпки, якщо вони розділені в таблиці Product)
        qs = base_qs
        if hasattr(Product, 'is_boxing') and hasattr(Product, 'is_sticker'):
            qs = qs.filter(is_boxing=False, is_sticker=False)

    qs = qs.distinct()[:10]
    products = [p async for p in qs]

    if not products:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ Назад до комплекту", callback_data=f"kit_{parent_code}"))
        not_found_msg = await message.answer(
            "❌ За вашим запитом нічого не знайдено з урахуванням фільтру. Спробуйте інший текст або поверніться назад:",
            reply_markup=builder.as_markup()
        )
        await track_add_msg(state, not_found_msg.message_id)
        return

    new_ids = []
    header_msg = await message.answer(
        f"🔎 Знайдено товарів: <b>{len(products)}</b>. Оберіть потрібний:",
        parse_mode="HTML"
    )
    new_ids.append(header_msg.message_id)

    for p in products:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅ Додати обране",
            callback_data=f"addkit_select_prod:{p.code}"
        ))

        caption = (
            f"<b>{p.name_ua or 'Без назви'}</b>\n"
            f"Код: <code>{p.code}</code> | Кат. номер: <code>{p.catalog_number or '—'}</code>"
        )
        item_msg = await message.answer(caption, reply_markup=builder.as_builder().as_markup() if hasattr(builder, 'as_builder') else builder.as_markup(), parse_mode="HTML")
        new_ids.append(item_msg.message_id)

    cancel_builder = InlineKeyboardBuilder()
    cancel_builder.row(InlineKeyboardButton(text="❌ Скасувати пошук", callback_data=f"kit_{parent_code}"))
    footer_msg = await message.answer("⬆️ Оберіть варіант вище або скасуйте:", reply_markup=cancel_builder.as_markup())
    new_ids.append(footer_msg.message_id)

    await track_add_msg(state, *new_ids)


# ==============================================================================
# 3. ВИБІР ТОВАРУ -> ВИДАЛЕННЯ СПИСКУ ПОШУКУ, ЗАПИТ КІЛЬКОСТІ
# ==============================================================================

@router.callback_query(F.data.startswith("addkit_select_prod:"))
async def select_kit_product_action(callback: types.CallbackQuery, state: FSMContext):
    component_code = callback.data.replace("addkit_select_prod:", "")
    data = await state.get_data()
    parent_code = data.get("parent_code")

    exists = await ProductComponent.objects.filter(
        parent_code_id=parent_code,
        component_code_id=component_code
    ).aexists()

    if exists:
        return await callback.answer("⚠️ Цей товар уже додано до комплектації!", show_alert=True)

    # Прибираємо весь список знайдених товарів
    await clear_add_kit_messages(callback, state)

    await state.update_data(selected_component_code=component_code)
    await state.set_state(KitAddProcess.waiting_quantity)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Скасувати", callback_data=f"kit_{parent_code}"))

    qty_prompt = await callback.message.answer(
        "🔢 Введіть необхідну кількість на комплект (наприклад: <code>1</code> або <code>0.5</code>):",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await track_add_msg(state, qty_prompt.message_id)
    await callback.answer()


# ==============================================================================
# 4. ВВЕДЕННЯ КІЛЬКОСТІ -> ВИДАЛЕННЯ ЗАПИТУ ТА ЧИСЛА, ПЕРЕВІРКА ДАНИХ
# ==============================================================================

@router.message(KitAddProcess.waiting_quantity)
async def process_kit_quantity_input(message: types.Message, state: FSMContext):
    # Фіксуємо повідомлення користувача з кількістю
    await track_add_msg(state, message.message_id)

    try:
        quantity = float(message.text.replace(",", "."))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        err_msg = await message.answer("⚠️ Будь ласка, введіть коректне додатне число (наприклад, 1 або 2.5).")
        await track_add_msg(state, err_msg.message_id)
        return

    # Видаляємо запит кількості та повідомлення користувача з числом
    await clear_add_kit_messages(message, state)

    data = await state.get_data()
    parent_code = data.get("parent_code")
    component_code = data.get("selected_component_code")

    try:
        comp_prod = await Product.objects.aget(code=component_code)
        comp_name = comp_prod.name_ua
    except Product.DoesNotExist:
        comp_name = component_code

    await state.update_data(kit_quantity=quantity)
    await state.set_state(KitAddProcess.confirming)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Додати до комплекту", callback_data="addkit_confirm_add"),
        InlineKeyboardButton(text="❌ Скасувати", callback_data=f"kit_{parent_code}")
    )

    confirm_msg = await message.answer(
        f"📦 <b>Перевірка даних:</b>\n\n"
        f"🔹 Компонент: <b>{comp_name}</b> (Код: <code>{component_code}</code>)\n"
        f"🔢 Кількість: <b>{quantity} шт.</b>\n\n"
        f"Додати цей елемент до комплектації?",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await track_add_msg(state, confirm_msg.message_id)


# ==============================================================================
# 5. ФІНАЛЬНЕ ЗБЕРЕЖЕННЯ -> ВИДАЛЕННЯ ПЕРЕВІРКИ, ПОВЕРНЕННЯ ДО КОМПЛЕКТУ
# ==============================================================================

@router.callback_query(KitAddProcess.confirming, F.data == "addkit_confirm_add")
async def finalize_add_kit_component(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parent_code = data.get("parent_code")
    component_code = data.get("selected_component_code")
    quantity = data.get("kit_quantity", 1.0)
    item_type = data.get("item_type", "product")

    is_boxing = (item_type == "boxing")
    is_sticker = (item_type == "sticker")

    await ProductComponent.objects.acreate(
        parent_code_id=parent_code,
        component_code_id=component_code,
        quantity=quantity,
        is_boxing=is_boxing,
        is_sticker=is_sticker
    )

    # Прибираємо повідомлення перевірки даних
    await clear_add_kit_messages(callback, state)

    await callback.answer("✅ Компонент успішно додано до комплекту!", show_alert=True)

    # Повертаємося до відображення оновленого комплекту
    await send_kit_list(callback, parent_code, state)