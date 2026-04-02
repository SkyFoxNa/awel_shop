import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, exists, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from db.models import Product, User, ProductStock, ProductPhoto, Location, UserRole
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


async def safe_send_photo(event, p_code, photo_record, caption, reply_markup, session):
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
            clean_name = photo_record.photo_name.split('.')[0]
            file_data = await asyncio.to_thread(drive.download_file_by_name, p_code, clean_name)
            if file_data:
                f = BufferedInputFile(file_data.read(), filename=f"{clean_name}.png")
                msg = await (event.answer_photo if isinstance(event, Message) else event.message.answer_photo)(
                    photo=f, caption=caption, reply_markup=reply_markup, parse_mode="HTML"
                )
                new_id = msg.photo[-1].file_id
                await session.execute(
                    update(ProductPhoto).where(ProductPhoto.id == photo_record.id).values(tg_file_id=new_id))
                await session.commit()
                return msg
    return await (event.answer if isinstance(event, Message) else event.message.answer)(
        text=f"🖼 <i>(Помилка фото)</i>\n\n{caption}", reply_markup=reply_markup, parse_mode="HTML"
    )


async def send_product_display(event, product, user, info, session, is_preview=True):
    new_ids = []
    photos = product.photos
    p_code = product.code

    # 1. Перевірка ролі клієнта (Шукаємо будь-яку роль, де в назві є "client")
    # Отримуємо назви всіх ролей користувача
    user_role_names = [ur.role.name.lower() for ur in user.roles]
    # Шукаємо будь-яку роль, що містить слово "client"
    is_any_client = any("client" in role for role in user_role_names)

    # 2. Формування тексту
    if is_preview:
        caption = (f"<b>{product.name_ua}</b>\n"
                   f"📝 {product.info or 'Опис відсутній'}\n\n" # Додано опис
                   f"Код: <code>{p_code}</code>\n"
                   f"Кат. номер: <code>{product.catalog_number or '—'}</code>\n"
                   f"Ціна: <b>{info['final_price']} грн</b>")
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✅ ОБРАТИ", callback_data=f"view_prod_{product.id}"))
    else:
        # ПОВНА КАРТКА
        lines = [
            f"📦 <b>{product.name_ua}</b>",
            f"📝 {product.info or 'Опис відсутній'}\n", # Додано опис
            f"Код: <code>{p_code}</code>",
            f"Кат. номер: <code>{product.catalog_number or '—'}</code>",
            f"Ціна: <b>{info['final_price']} грн</b>\n",
            "<b>📊 Наявність на складах:</b>"
        ]

        all_locations = (await session.execute(select(Location))).scalars().all()
        current_stocks = {s.location_id: s for s in product.stocks} if hasattr(product, 'stocks') else {}

        for loc in all_locations:
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
        # Використовуємо нашу нову перевірку ролей
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
        msg = await safe_send_photo(event, p_code, photos[0], caption, builder.as_markup(), session)
        new_ids.append(msg.message_id)
    else:
        # Альбом
        media = [InputMediaPhoto(media=ph.tg_file_id) for ph in photos]
        try:
            msgs = await (event.answer_media_group if isinstance(event, Message) else event.message.answer_media_group)(
                media=media)
            new_ids.extend([m.message_id for m in msgs])
        except TelegramBadRequest:
            restored = []
            for ph in photos:
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
async def handle_search_input(message: Message, state: FSMContext, session: AsyncSession):
    if len(message.text) < 2:
        return await message.answer("⚠️ Запит занадто короткий.")
    await clear_previous_results(message, state)
    await show_catalog_page(message, message.text, 0, session, state)


async def show_catalog_page(event, query: str, page: int, session: AsyncSession, state: FSMContext):
    limit = 6
    offset = page * limit
    pattern = f"%{query}%"

    active_exists = exists().where(ProductStock.product_code == Product.code, ProductStock.is_active == True)
    count_stmt = select(func.count(Product.id)).where(active_exists).where(
        (Product.code.ilike(pattern)) | (Product.name_ua.ilike(pattern)) | (Product.catalog_number.ilike(pattern))
    )
    total_count = (await session.execute(count_stmt)).scalar()

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

    stmt = (select(Product).where(active_exists)
            .where(
        (Product.code.ilike(pattern)) | (Product.name_ua.ilike(pattern)) | (Product.catalog_number.ilike(pattern)))
            .options(selectinload(Product.photos), selectinload(Product.stocks)).offset(offset).limit(limit))
    products = (await session.execute(stmt)).scalars().all()

    user_stmt = select(User).where(User.user_id == event.from_user.id).options(
        selectinload(User.roles).joinedload(UserRole.role)
    )
    result = await session.execute(user_stmt)
    user = result.scalar_one()

    for p in products:
        info = await get_product_display_data(session, p, user)
        if info:
            ids = await send_product_display(event, p, user, info, session, is_preview=True)
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
async def process_pagination(callback: CallbackQuery, callback_data: CatalogPagination, session: AsyncSession,
                             state: FSMContext):
    await show_catalog_page(callback, callback_data.query, callback_data.page, session, state)
    await callback.answer()


@router.callback_query(F.data.startswith("view_prod_"))
async def show_product_card(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await delete_kit_messages(callback, state)
    await clear_previous_results(callback, state)
    await state.clear()

    p_id = int(callback.data.split("_")[2])
    # Довантажуємо фото, залишки та локації для повного звіту
    product = await session.get(Product, p_id, options=[
        selectinload(Product.photos),
        selectinload(Product.stocks)
    ])
    user_stmt = select(User).where(User.user_id == callback.from_user.id).options(
        selectinload(User.roles).joinedload(UserRole.role)
    )
    user = (await session.execute(user_stmt)).scalar_one()

    info = await get_product_display_data(session, product, user)

    await send_product_display(callback, product, user, info, session, is_preview=False)
    await callback.answer()
