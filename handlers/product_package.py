# handlers/product_package.py
import asyncio
import logging
from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from django.db.models import Case, When, Value, IntegerField

from shop.models import Product, ProductComponent, Location
from utils.drive_utils import drive

router = Router()
logger = logging.getLogger(__name__)


async def delete_kit_messages(event: types.TelegramObject, state: FSMContext):
    """Видаляє всі повідомлення комплектації та проміжні повідомлення додавання"""
    data = await state.get_data()
    kit_ids = data.get("current_kit_msg_ids", [])
    add_ids = data.get("add_kit_msg_ids", [])

    bot = event.bot
    chat_id = event.from_user.id

    for m_id in kit_ids + add_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=m_id)
        except Exception:
            pass

    await state.update_data(current_kit_msg_ids=[], add_kit_msg_ids=[])


async def get_safe_photo_for_kit(product: Product):
    """Безпечно отримує фото для компонента (з Telegram кешу або Google Drive)"""
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


async def send_kit_list(event: types.TelegramObject, parent_code: str, state: FSMContext):
    """
    Універсальна функція для виведення всього складу комплекту:
    Сортування: 1 - Основні товари, 2 - Тара, 3 - Наліпки.
    Працює однаково як для CallbackQuery, так і для Message.
    """
    await delete_kit_messages(event, state)
    await state.clear()

    target = event.message if isinstance(event, types.CallbackQuery) else event

    components = []
    # Чітке сортування через Django Case/When для гарантованого виведення всіх елементів
    qs = ProductComponent.objects.filter(
        parent_code=parent_code
    ).select_related('component_code').annotate(
        sort_order=Case(
            When(is_boxing=True, then=Value(2)),
            When(is_sticker=True, then=Value(3)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('sort_order', 'id')

    async for comp in qs:
        components.append(comp)

    kit_msg_ids = []

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

        # Формуємо блок інформації про наявність та склади (так само, як у повній картці)
        stock_lines = ["<b>📊 Наявність на складах:</b>"]
        current_stocks = {s.location_id: s async for s in product.stocks.all()}

        # Отримуємо всі склади (Location)
        async for loc in Location.objects.all():
            stock_item = current_stocks.get(loc.id)
            addr = f" (📍 {stock_item.storage_address if stock_item and stock_item.storage_address else '—'})"
            if stock_item and stock_item.balance > 0:
                stock_lines.append(f"• {loc.name}: <b>{float(stock_item.balance)} шт.</b>{addr}")
            else:
                stock_lines.append(f"• {loc.name}: <i>Товар відсутній</i>{addr}")

        stocks_text = "\n".join(stock_lines)

        # Збираємо повний опис картки компонента
        caption = (
            f"<b>{label}</b>\n\n"
            f"🔹 Назва: <b>{product.name_ua}</b>\n"
            f"🆔 Код: <code>{product.code}</code>\n"
            f"🔢 Кількість у комплекті: <b>{float(comp.quantity)} шт.</b>\n\n"
            f"{stocks_text}"
        )

        builder = InlineKeyboardBuilder()
        if not comp.is_boxing and not comp.is_sticker:
            builder.row(InlineKeyboardButton(text="✅ ОБРАТИ", callback_data=f"view_prod_{product.id}"))

        builder.row(
            InlineKeyboardButton(text="❌ Видалити з комплекту", callback_data=f"del_kit_comp:{comp.id}:{parent_code}"))

        photo = await get_safe_photo_for_kit(product)

        try:
            if photo and isinstance(photo, str):
                try:
                    msg = await target.answer_photo(
                        photo=photo, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML"
                    )
                except Exception:
                    # Якщо file_id в Telegram застарів/пошкодився — відправляємо текстом без падіння
                    msg = await target.answer(
                        f"🖼 <i>(Недійсне фото)</i>\n\n{caption}",
                        reply_markup=builder.as_markup(),
                        parse_mode="HTML"
                    )
            elif photo:
                msg = await target.answer_photo(
                    photo=photo, caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML"
                )
            else:
                msg = await target.answer(
                    f"🖼 <i>(Фото відсутнє)</i>\n\n{caption}",
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
            kit_msg_ids.append(msg.message_id)
        except Exception as e:
            logger.error(f"Error sending kit part {product.code}: {e}")

    # Панель швидкого додавання та управління
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

    last_msg = await target.answer(
        "📂 <b>Управління комплектацією:</b>",
        reply_markup=add_builder.as_markup(),
        parse_mode="HTML"
    )
    kit_msg_ids.append(last_msg.message_id)

    await state.update_data(current_kit_msg_ids=kit_msg_ids)


# ==============================================================================
# ХЕНДЛЕРИ КОМПЛЕКТАЦІЇ
# ==============================================================================

@router.callback_query(F.data.startswith("kit_"))
async def show_product_kit(callback: types.CallbackQuery, state: FSMContext):
    parent_code = callback.data.replace("kit_", "")
    await send_kit_list(callback, parent_code, state)
    await callback.answer()


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

    # Оновлюємо список без мутації замороженого callback.data
    await send_kit_list(callback, parent_code, state)


@router.callback_query(F.data == "close_kit")
async def handle_close_kit(callback: types.CallbackQuery, state: FSMContext):
    await delete_kit_messages(callback, state)
    await state.clear()
    await callback.answer("Комплектацію приховано.")