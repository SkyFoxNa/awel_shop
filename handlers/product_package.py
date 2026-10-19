import asyncio
import logging
from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from shop.models import Product, ProductComponent
from utils.drive_utils import drive
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
# ОСНОВНИЙ ОБРОБНИК КОМПЛЕКТАЦІЇ
# ==============================================================================

@router.callback_query(F.data.startswith("kit_"))
async def show_product_kit(callback: types.CallbackQuery, state: FSMContext):
    """
    Виводить склад комплекту окремими повідомленнями:
    1. Товари (деталі)
    2. Тара
    3. Наліпки
    """
    parent_code = callback.data.replace("kit_", "")

    # Отримуємо компоненти через Django ORM
    components = []
    qs = ProductComponent.objects.filter(
        parent_code=parent_code
    ).order_by('is_boxing', 'is_sticker')

    async for comp in qs:
        components.append(comp)

    if not components:
        return await callback.answer("Комплектація не знайдена.", show_alert=True)

    kit_msg_ids = []

    for comp in components:
        try:
            product = await Product.objects.prefetch_related('photos').aget(code=comp.component_code)
        except Product.DoesNotExist:
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

    back_builder = InlineKeyboardBuilder()
    back_builder.row(InlineKeyboardButton(text="❌ Закрити комплектацію", callback_data="close_kit"))

    last_msg = await callback.message.answer("Кінець списку комплектації.", reply_markup=back_builder.as_markup())
    kit_msg_ids.append(last_msg.message_id)

    await state.update_data(current_kit_msg_ids=kit_msg_ids)
    await callback.answer()


# ==============================================================================
# ЗАКРИТТЯ ТА ПОВЕРНЕННЯ
# ==============================================================================

@router.callback_query(F.data == "close_kit")
async def handle_close_kit(callback: types.CallbackQuery, state: FSMContext):
    """Видаляє повідомлення комплектації"""
    await delete_kit_messages(callback, state)
    await callback.answer("Комплектацію приховано.")