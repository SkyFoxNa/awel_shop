import asyncio
import logging
from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Product, ProductComponent, User
from utils.drive_utils import drive

# Припускаємо, що ці функції доступні для імпорту
# Якщо виникає помилка імпорту, переконайтеся, що вони в __init__.py ваших папок
from utils.product_helper import get_product_display_data

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
    """Отримує фото для компонента (TG id або Google Drive)"""
    if not product.photos:
        return None

    photo_record = product.photos[0]
    if photo_record.tg_file_id:
        return photo_record.tg_file_id

    try:
        clean_name = photo_record.photo_name.split('.')[0]
        file_data = await asyncio.to_thread(drive.download_file_by_name, product.code, clean_name)
        if file_data:
            return BufferedInputFile(file_data.read(), filename=f"{clean_name}.png")
    except Exception as e:
        logger.error(f"Drive error for kit item {product.code}: {e}")

    return None


# ==============================================================================
# ОСНОВНИЙ ОБРОБНИК КОМПЛЕКТАЦІЇ
# ==============================================================================

@router.callback_query(F.data.startswith("kit_"))
async def show_product_kit(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    """
    Виводить склад комплекту окремими повідомленнями:
    1. Товари (деталі)
    2. Тара
    3. Наліпки
    """
    parent_code = callback.data.replace("kit_", "")

    # Отримуємо компоненти, сортуємо їх логічно (спочатку деталі, потім тара, потім наліпки)
    stmt = (
        select(ProductComponent)
        .where(ProductComponent.parent_code == parent_code)
        .order_by(ProductComponent.is_boxing.asc(), ProductComponent.is_sticker.asc())
    )
    components = (await session.execute(stmt)).scalars().all()

    if not components:
        return await callback.answer("Комплектація не знайдена.", show_alert=True)

    kit_msg_ids = []

    # Проходимо по компонентах
    for comp in components:
        # Завантажуємо дані продукту-компонента
        stmt_prod = (
            select(Product)
            .where(Product.code == comp.component_code)
            .options(selectinload(Product.photos))
        )
        product = (await session.execute(stmt_prod)).scalar()

        if not product:
            continue

        # Визначаємо заголовок та іконку залежно від типу
        if comp.is_boxing:
            label, icon = "📦 ТАРА", "📦"
        elif comp.is_sticker:
            label, icon = "🏷 НАЛІПКА", "🏷"
        else:
            label, icon = "⚙️ ТОВАР КОМПЛЕКТУ", "⚙️"

        caption = (
            f"<b>{label}</b>\n\n"
            f"🔹 Назва: <b>{product.name_ua}</b>\n"
            f"📝 Опис: {product.info or '—'}\n"
            f"🔢 Кількість: <b>{float(comp.quantity)} шт.</b>\n"
            f"🆔 Код: <code>{product.code}</code>"
        )

        # Кнопка "ОБРАТИ" (view_prod_ID) для переходу до повної картки як окремого товару
        builder = InlineKeyboardBuilder()
        if not comp.is_boxing and not comp.is_sticker:
            builder.row(InlineKeyboardButton(text="✅ ОБРАТИ", callback_data=f"view_prod_{product.id}"))

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

    # Кнопка закриття рулону
    back_builder = InlineKeyboardBuilder()
    back_builder.row(InlineKeyboardButton(text="❌ Закрити комплектацію", callback_data="close_kit"))

    last_msg = await callback.message.answer("Кінець списку комплектації.", reply_markup=back_builder.as_markup())
    kit_msg_ids.append(last_msg.message_id)

    # Зберігаємо ID для видалення
    await state.update_data(current_kit_msg_ids=kit_msg_ids)
    await callback.answer()


# ==============================================================================
# ЗАКРИТТЯ ТА ПОВЕРНЕННЯ
# ==============================================================================

@router.callback_query(F.data == "close_kit")
async def handle_close_kit(callback: types.CallbackQuery, state: FSMContext):
    """Просто видаляє 'рулон' повідомлень комплектації"""
    await delete_kit_messages(callback, state)
    await callback.answer("Комплектацію приховано.")