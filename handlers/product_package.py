# handlers/product_package.py
import asyncio
import logging
from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from shop.models import Product, ProductComponent
from utils.drive_utils import drive
from services.states import KitComponentAdd

router = Router()
logger = logging.getLogger(__name__)


# ==============================================================================
# СЕРВІСНІ ФУНКЦІЇ
# ==============================================================================

async def delete_kit_messages(callback: types.CallbackQuery, state: FSMContext):
    """Видаляє всі повідомлення комплектації, збережені в стані"""
    data = await state.get_data()
    kit_ids = data.get("current_kit_msg_ids", [])

    for m_id in kit_ids:
        try:
            await callback.bot.delete_message(chat_id=callback.from_user.id, message_id=m_id)
        except Exception:
            pass

    await state.update_data(current_kit_msg_ids=[])


async def get_safe_photo_for_kit(product: Product):
    """Отримує фото для компонента (TG file_id або Google Drive)"""
    photo_record = await product.photos.afirst()
    if not photo_record:
        return None

    if photo_record.tg_file_id:
        return photo_record.tg_file_id

    if photo_record.photo_name:
        try:
            clean_name = photo_record.photo_name.split('.')[0]
            file_data = await asyncio.to_thread(drive.download_file_by_name, product.code, clean_name)
            if file_data:
                return BufferedInputFile(file_data.read(), filename=f"{clean_name}.png")
        except Exception as e:
            logger.error(f"Drive error for kit item {product.code}: {e}")

    return None


# ==============================================================================
# ОСНОВНИЙ ОБРОБНИК КОМПЛЕКТАЦІЇ (ВИВЕДЕННЯ, ВИДАЛЕННЯ, КНОПКИ ДОДАВАННЯ)
# ==============================================================================

@router.callback_query(F.data.startswith("kit_"))
async def show_product_kit(callback: types.CallbackQuery, state: FSMContext):
    """Виводить склад комплекту з кнопками видалення та панеллю додавання"""
    parent_code = callback.data.replace("kit_", "")

    components = []
    qs = ProductComponent.objects.filter(
        parent_code=parent_code
    ).select_related('component_code').order_by('is_boxing', 'is_sticker')

    async for comp in qs:
        components.append(comp)

    kit_msg_ids = []

    # Виводимо кожен компонент окремим повідомленням з кнопкою видалення
    for comp in components:
        product = comp.component_code
        if not product:
            continue

        if comp.is_boxing:
            label = "📦 ТАРА"
        elif comp.is_sticker:
            label = "🏷 НАЛІПКА"
        else:
            label = "⚙️ ТОВАР КОМПЛЕКТУ"

        caption = (
            f"<b>{label}</b>\n\n"
            f"🔹 Назва: <b>{product.name_ua}</b>\n"
            f"📝 Опис: {product.info or '—'}\n"
            f"🔢 Кількість: <b>{float(comp.quantity)} шт.</b>\n"
            f"🆔 Код: <code>{product.code}</code>"
        )

        builder = InlineKeyboardBuilder()
        if not comp.is_boxing and not comp.is_sticker:
            builder.row(InlineKeyboardButton(text="✅ ОБРАТИ", callback_data=f"view_prod_{product.id}"))

        # Кнопка видалення конкретного зв'язку за ID записи ProductComponent
        builder.row(
            InlineKeyboardButton(text="❌ Видалити з комплекту", callback_data=f"del_kit_comp:{comp.id}:{parent_code}"))

        photo = await get_safe_photo_for_kit(product)

        try:
            if photo:
                msg = await callback.message.answer_photo(
                    photo=photo, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML"
                )
            else:
                msg = await callback.message.answer(
                    f"🖼 <i>(Фото відсутнє)</i>\n\n{caption}",
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
            kit_msg_ids.append(msg.message_id)
        except Exception as e:
            logger.error(f"Error sending kit part {product.code}: {e}")

    # У кінці виводимо панель керування додаванням нових елементів
    add_builder = InlineKeyboardBuilder()
    add_builder.row(
        InlineKeyboardButton(text="➕ Додати товар", callback_data=f"add_kit_item:{parent_code}:product"),
        InlineKeyboardButton(text="➕ Додати тару", callback_data=f"add_kit_item:{parent_code}:boxing"),
    )
    add_builder.row(
        InlineKeyboardButton(text="➕ Додати наліпку", callback_data=f"add_kit_item:{parent_code}:sticker"),
    )
    add_builder.row(
        InlineKeyboardButton(text="❌ Закрити комплектацію", callback_data="close_kit")
    )

    last_msg = await callback.message.answer(
        "📂 <b>Управління комплектацією:</b>\nОберіть дію нижче:",
        reply_markup=add_builder.as_markup(),
        parse_mode="HTML"
    )
    kit_msg_ids.append(last_msg.message_id)

    await state.update_data(current_kit_msg_ids=kit_msg_ids)
    await callback.answer()


# ==============================================================================
# ВИДАЛЕННЯ КОМПОНЕНТА З КОМПЛЕКТУ
# ==============================================================================

@router.callback_query(F.data.startswith("del_kit_comp:"))
async def delete_kit_component(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    comp_id = int(parts[1])
    parent_code = parts[2]

    deleted_count, _ = await ProductComponent.objects.filter(id=comp_id).adelete()

    if deleted_count > 0:
        await callback.answer("✅ Компонент видалено!", show_alert=True)
    else:
        await callback.answer("❌ Компонент не знайдено.", show_alert=True)

    await delete_kit_messages(callback, state)

    # Перезавантажуємо список комплекту
    callback.data = f"kit_{parent_code}"
    await show_product_kit(callback, state)


# ==============================================================================
# ДОДАВАННЯ КОМПОНЕНТА ЧЕРЕЗ КАТЕГОРІЇ
# ==============================================================================

@router.callback_query(F.data.startswith("add_kit_item:"))
async def start_add_kit_item(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    parent_code = parts[1]
    item_type = parts[2]  # 'product', 'boxing', або 'sticker'

    await state.update_data(parent_code=parent_code, kit_item_type=item_type)
    await state.set_state(KitComponentAdd.choosing_category)

    # Отримуємо унікальні категорії товарів
    categories = []
    async for cat in Product.objects.exclude(category__isnull=True).values_list('category', flat=True).distinct():
        if cat and cat not in categories:
            categories.append(cat)

    if not categories:
        return await callback.answer("Категорії товарів не знайдено.", show_alert=True)

    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(InlineKeyboardButton(text=str(cat), callback_data=f"kit_cat_sel:{cat}"))

    builder.row(InlineKeyboardButton(text="◀️ Назад до комплекту", callback_data=f"kit_{parent_code}"))

    await callback.message.edit_text(
        "📂 Оберіть категорію для пошуку:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(KitComponentAdd.choosing_category, F.data.startswith("kit_cat_sel:"))
async def select_kit_category(callback: types.CallbackQuery, state: FSMContext):
    category_name = callback.data.replace("kit_cat_sel:", "")
    await state.set_state(KitComponentAdd.choosing_product)

    products = []
    async for p in Product.objects.filter(category=category_name)[:25]:
        products.append(p)

    builder = InlineKeyboardBuilder()
    for p in products:
        builder.row(InlineKeyboardButton(
            text=f"[{p.code}] {p.name_ua or 'Без назви'}",
            callback_data=f"kit_prod_add:{p.code}"
        ))

    data = await state.get_data()
    parent_code = data.get("parent_code")
    builder.row(InlineKeyboardButton(text="◀️ До категорій",
                                     callback_data=f"add_kit_item:{parent_code}:{data.get('kit_item_type', 'product')}"))

    await callback.message.edit_text(
        f"📦 Товари в категорії <b>{category_name}</b>:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(KitComponentAdd.choosing_product, F.data.startswith("kit_prod_add:"))
async def confirm_add_kit_product(callback: types.CallbackQuery, state: FSMContext):
    component_code = callback.data.replace("kit_prod_add:", "")
    data = await state.get_data()
    parent_code = data.get("parent_code")
    item_type = data.get("kit_item_type", "product")

    is_boxing = (item_type == "boxing")
    is_sticker = (item_type == "sticker")

    # Створюємо зв'язок у базі даних
    await ProductComponent.objects.acreate(
        parent_code_id=parent_code,
        component_code_id=component_code,
        quantity=1.0,
        is_boxing=is_boxing,
        is_sticker=is_sticker
    )

    await state.clear()
    await callback.answer("✅ Успішно додано до комплекту!", show_alert=True)

    # Повертаємося до перегляду оновленої комплектації
    callback.data = f"kit_{parent_code}"
    await show_product_kit(callback, state)


# ==============================================================================
# ЗАКРИТТЯ ТА ПОВЕРНЕННЯ
# ==============================================================================

@router.callback_query(F.data == "close_kit")
async def handle_close_kit(callback: types.CallbackQuery, state: FSMContext):
    """Видаляє повідомлення комплектації"""
    await delete_kit_messages(callback, state)
    await callback.answer("Комплектацію приховано.")