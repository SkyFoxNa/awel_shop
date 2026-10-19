import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from django.db.models import Q

from shop.models import Product, User, Location, ProductPhoto
from handlers.product_package import delete_kit_messages
from utils.product_helper import get_product_display_data
from utils.states import CatalogState
from utils.drive_utils import drive
from keyboards.reply import BTN_CATALOG

router = Router()


# Клас для керування пагінацією
class CatalogPagination(CallbackData, prefix="cat"):
    action: str
    page: int
    query: str


# --- СЕРВІСНІ ФУНКЦІЇ ---

async def clear_previous_results(event, state: FSMContext):
    """Видаляє всі повідомлення пошуку, збережені в стані FSM"""
    data = await state.get_data()
    msg_ids = data.get("search_msg_ids", [])

    for msg_id in msg_ids:
        try:
            await event.bot.delete_message(chat_id=event.from_user.id, message_id=msg_id)
        except Exception:
            pass

    await state.update_data(search_msg_ids=[])


async def safe_send_photo(event, p_code, photo_record, caption, reply_markup):
    """Безпечна відправка одного фото з відновленням з Google Drive"""
    if photo_record is None:
        return await (event.answer if isinstance(event, Message) else event.message.answer)(
            text=f"🖼 <i>(Фото не додано)</i>\n\n{caption}", reply_markup=reply_markup, parse_mode="HTML"
        )

    try:
        return await (event.answer_photo if isinstance(event, Message) else event.message.answer_photo)(
            photo=photo_record.tg_file_id, caption=caption, reply_markup=reply_markup, parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "wrong file identifier" in str(e).lower() or "file_id" in str(e).lower():
            if photo_record.photo_name:
                clean_name = photo_record.photo_name.split('.')[0]
                file_data = await asyncio.to_thread(drive.download_file_by_name, p_code, clean_name)
                if file_data:
                    f = BufferedInputFile(file_data.read(), filename=f"{clean_name}.png")
                    msg = await (event.answer_photo if isinstance(event, Message) else event.message.answer_photo)(
                        photo=f, caption=caption, reply_markup=reply_markup, parse_mode="HTML"
                    )
                    new_id = msg.photo[-1].file_id
                    photo_record.tg_file_id = new_id
                    await photo_record.asave()
                    return msg

    return await (event.answer if isinstance(event, Message) else event.message.answer)(
        text=f"🖼 <i>(Помилка фото)</i>\n\n{caption}", reply_markup=reply_markup, parse_mode="HTML"
    )


async def send_product_display(event, product: Product, user: User, info: dict, is_preview=True):
    new_ids = []
    photos = [ph async for ph in product.photos.all()]
    p_code = product.code

    # 1. Перевірка ролі клієнта
    user_role_names = [role.name.lower() async for role in user.roles.all()] if user and user.roles else []
    is_any_client = any("client" in role for role in user_role_names)

    # 2. Формування тексту
    if is_preview:
        caption = (f"<b>{product.name_ua}</b>\n"
                   f"📝 {product.info or 'Опис відсутній'}\n\n"
                   f"Код: <code>{p_code}</code>\n"
                   f"Кат. номер: <code>{product.catalog_number or '—'}</code>\n"
                   f"Ціна: <b>{info['final_price']} грн</b>")
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✅ ОБРАТИ", callback_data=f"view_prod_{product.id}"))
    else:
        # ПОВНА КАРТКА
        lines = [
            f"📦 <b>{product.name_ua}</b>",
            f"📝 {product.info or 'Опис відсутній'}\n",
            f"Код: <code>{p_code}</code>",
            f"Кат. номер: <code>{product.catalog_number or '—'}</code>",
            f"Ціна: <b>{info['final_price']} грн</b>\n",
            "<b>📊 Наявність на складах:</b>"
        ]

        current_stocks = {s.location_id: s async for s in product.stocks.all()}

        async for loc in Location.objects.all():
            stock_item = current_stocks.get(loc.id)
            addr = f" (📍 {stock_item.storage_address if stock_item and stock_item.storage_address else '—'})"
            if stock_item and stock_item.balance > 0:
                lines.append(f"• {loc.name}: <b>{stock_item.balance} шт.</b>{addr}")
            else:
                lines.append(f"• {loc.name}: <i>Товар відсутній</i>{addr}")

        caption = "\n".join(lines)
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Аналоги", callback_data=f"anlg_{p_code}"),
            InlineKeyboardButton(text="🛠 Комплектація", callback_data=f"kit_{p_code}")
        )
        if is_any_client:
            builder.row(
                InlineKeyboardButton(text="📥 Додати в кошик", callback_data=f"add_cart_{product.id}")
            )

    # Вивід контенту
    if not photos:
        msg = await (event.answer if isinstance(event, Message) else event.message.answer)(
            text=f"🖼 <i>(Фото відсутнє)</i>\n\n{caption}", reply_markup=builder.as_markup(), parse_mode="HTML"
        )
        new_ids.append(msg.message_id)
    elif len(photos) == 1:
        msg = await safe_send_photo(event, p_code, photos[0], caption, builder.as_markup())
        new_ids.append(msg.message_id)
    else:
        media = [InputMediaPhoto(media=ph.tg_file_id) for ph in photos if ph.tg_file_id]
        try:
            msgs = await (event.answer_media_group if isinstance(event, Message) else event.message.answer_media_group)(
                media=media)
            new_ids.extend([m.message_id for m in msgs])
        except TelegramBadRequest:
            restored = []
            for ph in photos:
                if ph.photo_name:
                    clean_name = ph.photo_name.split('.')[0]
                    file_data = await asyncio.to_thread(drive.download_file_by_name, p_code, clean_name)
                    if file_data:
                        restored.append(
                            InputMediaPhoto(media=BufferedInputFile(file_data.read(), filename=f"{clean_name}.png")))
            if restored:
                msgs = await (
                    event.answer_media_group if isinstance(event, Message) else event.message.answer_media_group)(
                    media=restored)
                new_ids.extend([m.message_id for m in msgs])

        msg = await (event.answer if isinstance(event, Message) else event.message.answer)(
            text=caption, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
        new_ids.append(msg.message_id)

    return new_ids


# --- ХЕНДЛЕРИ ---

@router.message(F.text == BTN_CATALOG)
async def start_catalog_search(message: Message, state: FSMContext):
    await state.set_state(CatalogState.waiting_for_search_query)
    await message.answer("🔍 Введіть назву, код або каталожний номер товару:")


@router.callback_query(F.data == "cancel_search")
async def cancel_search_handler(callback: CallbackQuery, state: FSMContext):
    await clear_previous_results(callback, state)
    await state.clear()
    await callback.message.answer("📥 Пошук скасовано.")
    await callback.answer()


@router.message(CatalogState.waiting_for_search_query)
async def handle_search_input(message: Message, state: FSMContext):
    if len(message.text) < 2:
        return await message.answer("⚠️ Запит занадто короткий.")
    await clear_previous_results(message, state)
    await show_catalog_page(message, message.text, 0, state)


async def show_catalog_page(event, query: str, page: int, state: FSMContext):
    limit = 6
    offset = page * limit

    qs = Product.objects.filter(
        stocks__is_active=True
    ).filter(
        Q(code__icontains=query) | Q(name_ua__icontains=query) | Q(catalog_number__icontains=query)
    ).distinct()

    total_count = await qs.acount()

    if total_count == 0:
        nav = InlineKeyboardBuilder()
        nav.button(text="❌ Скасувати пошук", callback_data="cancel_search")

        method = event.answer if isinstance(event, Message) else event.message.answer
        return await method("❌ Нічого не знайдено.", reply_markup=nav.as_markup())

    total_pages = (total_count + limit - 1) // limit
    await clear_previous_results(event, state)

    h_msg = await (event.answer if isinstance(event, Message) else event.message.answer)(
        f"🔎 Знайдено: <b>{total_count}</b> | Сторінка <b>{page + 1}/{total_pages}</b>", parse_mode="HTML"
    )
    new_msg_ids = [h_msg.message_id]

    products = []
    async for p in qs.prefetch_related('photos', 'stocks')[offset:offset + limit]:
        products.append(p)

    try:
        user = await User.objects.prefetch_related('roles').aget(user_id=event.from_user.id)
    except User.DoesNotExist:
        user = None

    for p in products:
        info = await get_product_display_data(p, user)
        if info:
            ids = await send_product_display(event, p, user, info, is_preview=True)
            new_msg_ids.extend(ids)

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="⬅️ Назад", callback_data=CatalogPagination(action="list", page=page - 1, query=query))
    if page < total_pages - 1:
        nav.button(text="Вперед ➡️", callback_data=CatalogPagination(action="list", page=page + 1, query=query))
    nav.row(InlineKeyboardButton(text="❌ Скасувати пошук", callback_data="cancel_search"))

    f_msg = await (event.answer if isinstance(event, Message) else event.message.answer)(
        f"🏁 Сторінка {page + 1}/{total_pages}", reply_markup=nav.as_markup()
    )
    new_msg_ids.append(f_msg.message_id)
    await state.update_data(search_msg_ids=new_msg_ids)


@router.callback_query(CatalogPagination.filter(F.action == "list"))
async def process_pagination(callback: CallbackQuery, callback_data: CatalogPagination, state: FSMContext):
    await show_catalog_page(callback, callback_data.query, callback_data.page, state)
    await callback.answer()


@router.callback_query(F.data.startswith("view_prod_"))
async def show_product_card(callback: CallbackQuery, state: FSMContext):
    await delete_kit_messages(callback, state)
    await clear_previous_results(callback, state)
    await state.clear()

    p_id = int(callback.data.split("_")[2])

    try:
        product = await Product.objects.prefetch_related('photos', 'stocks').aget(id=p_id)
    except Product.DoesNotExist:
        return await callback.answer("Товар не знайдено!", show_alert=True)

    try:
        user = await User.objects.prefetch_related('roles').aget(user_id=callback.from_user.id)
    except User.DoesNotExist:
        user = None

    info = await get_product_display_data(product, user)

    await send_product_display(callback, product, user, info, is_preview=False)
    await callback.answer()