import asyncio
from datetime import datetime, timedelta
from contextlib import suppress
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, exists
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ProductNews, User, Product, ProductStock
from utils.product_helper import get_product_display_data
from utils.states import NewsAdminStates
from keyboards.reply import BTN_NEWS

router = Router()


class NewsPagination(CallbackData, prefix="news_nav"):
    page: int


# --- СЕРВІСНІ ФУНКЦІЇ ---

async def get_news_caption(news: ProductNews, user: User, session: AsyncSession):
    """Формує текст новини для клієнтів"""
    text = f"<b>📰 {news.title}</b>\n━━━━━━━━━━━━━━\n{news.content}\n"
    if news.product:
        info = await get_product_display_data(session, news.product, user)
        text += (f"\n📦 <b>Товар:</b> {news.product.name_ua}\n"
                 f"🔢 Код: <code>{news.product.code}</code>\n"
                 f"💰 Ціна: <b>{info['final_price']} грн</b>\n")
    text += f"\n📅 <i>{news.published_at.strftime('%d.%m.%Y')}</i>"
    return text


async def get_editor_markup(data: dict, session: AsyncSession):
    """Генерація інтерфейсу редактора"""
    title = data.get("title") or "❌ Відсутній"
    content = data.get("content") or "❌ Відсутній"
    photo_id = data.get("photo_id")
    photo_status = "Додано ✅" if photo_id else "Відсутнє ❌ (Тільки текст)"
    status = "✅ Активна" if data.get("is_published") else "⚪️ Чернетка"
    date = data.get("pub_date") or datetime.now().strftime("%d.%m.%Y")

    product_info = "📦 <b>Товар:</b> Не додано"
    has_product = False

    if data.get("product_code"):
        stmt = (select(Product).where(Product.code == data.get("product_code"))
                .options(selectinload(Product.stocks)))
        product = (await session.execute(stmt)).scalar_one_or_none()
        if product:
            has_product = True
            # Ціна з першого активного складу
            price = next((s.price for s in product.stocks if s.is_active), 0.0)
            product_info = (
                f"📦 <b>Товар обрано:</b>\n"
                f"├ <b>Назва:</b> {product.name_ua}\n"
                f"├ <b>Код:</b> <code>{product.code}</code>\n"
                f"└ <b>Ціна:</b> {price} грн"
            )

    text = (
        f"🛠 <b>РЕДАКТОР НОВИНИ</b>\n\n"
        f"🖼 <b>Фото:</b> {photo_status}\n"
        f"📌 <b>Заголовок:</b> {title}\n"
        f"📝 <b>Опис:</b> {content}\n\n"
        f"{product_info}\n\n"
        f"📅 <b>Дата:</b> {date}\n"
        f"📊 <b>Статус:</b> {status}"
    )

    kb = InlineKeyboardBuilder()
    # Перший ряд: Фото та Заголовок
    kb.row(InlineKeyboardButton(text="🖼 Фото", callback_data="n_edit_photo"),
           InlineKeyboardButton(text="📌 Заголовок", callback_data="n_edit_title"))

    # Кнопка видалення фото (тільки якщо воно є)
    if photo_id:
        kb.row(InlineKeyboardButton(text="🗑 Видалити фото", callback_data="n_remove_photo"))

    # Другий ряд: Опис та Пошук товару
    kb.row(InlineKeyboardButton(text="📝 Опис", callback_data="n_edit_content"),
           InlineKeyboardButton(text="🔍 Обрати товар", callback_data="n_search_prod"))

    # Видалення прив'язки товару
    if has_product:
        kb.row(InlineKeyboardButton(text="🛒 Прибрати товар", callback_data="n_remove_prod"))

    # Керування публікацією
    kb.row(InlineKeyboardButton(text="📅 Дата", callback_data="n_edit_date"),
           InlineKeyboardButton(text="🔄 Статус", callback_data="n_edit_status"))

    kb.row(InlineKeyboardButton(text="🚀 ОПУБЛІКУВАТИ", callback_data="n_publish"))
    kb.row(InlineKeyboardButton(text="❌ Скасувати", callback_data="n_cancel"))

    return text, kb.as_markup(), photo_id


async def refresh_editor(event, state: FSMContext, session: AsyncSession):
    """Оновлює повідомлення редактора (з фото або без)"""
    data = await state.get_data()
    text, kb, photo_id = await get_editor_markup(data, session)

    with suppress(Exception):
        if isinstance(event, CallbackQuery):
            await event.message.delete()
        else:
            await event.delete()

    if photo_id:
        await (event.message.answer_photo if isinstance(event, CallbackQuery) else event.answer_photo)(
            photo=photo_id, caption=text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await (event.message.answer if isinstance(event, CallbackQuery) else event.answer)(
            text=text, reply_markup=kb, parse_mode="HTML"
        )


# --- ХЕНДЛЕРИ ПЕРЕГЛЯДУ ---

@router.message(F.text == BTN_NEWS)
async def cmd_show_news(message: Message, session: AsyncSession, user: User, state: FSMContext):
    await state.clear()
    await show_news_list(message, session, user, page=0)


async def show_news_list(event, session: AsyncSession, user: User, page: int):
    limit, offset = 5, page * 5
    year_ago = datetime.now() - timedelta(days=365)
    staff_roles = {"admin", "manager", "seller", "owner", "creator"}
    is_staff = not {ur.role.name.lower() for ur in user.roles}.isdisjoint(staff_roles)

    # Рахуємо новини
    count_stmt = select(func.count(ProductNews.id)).where(ProductNews.published_at >= year_ago)
    if not is_staff:
        count_stmt = count_stmt.where(ProductNews.is_published == True)
    total_count = (await session.execute(count_stmt)).scalar()

    if total_count == 0:
        kb = InlineKeyboardBuilder()
        if is_staff: kb.button(text="➕ Додати новину", callback_data="add_news_start")
        return await (event.answer if isinstance(event, Message) else event.message.answer)(
            "📭 Новин поки немає.", reply_markup=kb.as_markup() if is_staff else None)

    # Отримуємо новини
    stmt = select(ProductNews).where(ProductNews.published_at >= year_ago)
    if not is_staff:
        stmt = stmt.where(ProductNews.is_published == True)

    news_list = (await session.execute(
        stmt.options(selectinload(ProductNews.product))
        .order_by(ProductNews.published_at.desc())
        .offset(offset).limit(limit)
    )).scalars().all()

    for news in news_list:
        cap = await get_news_caption(news, user, session)
        kb = InlineKeyboardBuilder()
        if news.product:
            kb.button(text="🛒 Товар", callback_data=f"view_prod_{news.product.id}")
        if is_staff:
            kb.row(InlineKeyboardButton(text="📝 Ред.", callback_data=f"edit_news_{news.id}"),
                   InlineKeyboardButton(text="🗑 Вид.", callback_data=f"del_news_{news.id}"))

        if news.photo_id:
            await (event.answer_photo if isinstance(event, Message) else event.message.answer_photo)(
                photo=news.photo_id, caption=cap, reply_markup=kb.as_markup(), parse_mode="HTML")
        else:
            await (event.answer if isinstance(event, Message) else event.message.answer)(
                text=cap, reply_markup=kb.as_markup(), parse_mode="HTML")

    # Навігація
    nav = InlineKeyboardBuilder()
    if page > 0: nav.button(text="⬅️", callback_data=NewsPagination(page=page - 1).pack())
    nav.button(text=f"{page + 1}/{(total_count + 4) // 5}", callback_data="none")
    if (page + 1) * 5 < total_count: nav.button(text="➡️", callback_data=NewsPagination(page=page + 1).pack())
    if is_staff: nav.row(InlineKeyboardButton(text="➕ Створити новину", callback_data="add_news_start"))

    await (event.answer if isinstance(event, Message) else event.message.answer)(
        text="Стрічка новин:", reply_markup=nav.as_markup())


# --- ЛОГІКА РЕДАКТОРА ---

@router.callback_query(F.data == "add_news_start")
async def add_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.update_data(title=None, content=None, product_code=None, photo_id=None,
                            is_published=False, pub_date=datetime.now().strftime("%d.%m.%Y"))
    await state.set_state(NewsAdminStates.in_editor)
    await refresh_editor(callback, state, session)


@router.callback_query(F.data.startswith("edit_news_"))
async def edit_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    news_id = int(callback.data.split("_")[2])
    news = await session.get(ProductNews, news_id)
    await state.update_data(
        news_id=news.id, title=news.title, content=news.content,
        product_code=news.product_code, photo_id=news.photo_id,
        is_published=news.is_published, pub_date=news.published_at.strftime("%d.%m.%Y")
    )
    await state.set_state(NewsAdminStates.in_editor)
    await refresh_editor(callback, state, session)


@router.callback_query(NewsAdminStates.in_editor, F.data.startswith("n_edit_"))
async def edit_field_trigger(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    field = callback.data.replace("n_edit_", "")

    if field == "status":
        data = await state.get_data()
        await state.update_data(is_published=not data.get("is_published", False))
        return await refresh_editor(callback, state, session)

    await state.update_data(editing_field=field)
    await state.set_state(NewsAdminStates.waiting_for_field)

    prompts = {
        "title": "📌 Введіть заголовок новини:",
        "content": "📝 Введіть текст новини:",
        "photo": "🖼 Надішліть фотографію:",
        "date": "📅 Введіть дату (напр. 30.03.2026):"
    }
    await callback.message.answer(prompts.get(field, "Чекаю ввід:"))
    await callback.answer()


@router.callback_query(NewsAdminStates.in_editor, F.data == "n_remove_photo")
async def remove_photo(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Видаляє фото, роблячи новину суто текстовою"""
    await state.update_data(photo_id=None)
    await refresh_editor(callback, state, session)
    await callback.answer("Фото видалено")


@router.callback_query(NewsAdminStates.in_editor, F.data == "n_remove_prod")
async def remove_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Прибирає прив'язку товару"""
    await state.update_data(product_code=None)
    await refresh_editor(callback, state, session)
    await callback.answer("Товар прибрано")


# --- ОБРОБКА ВВОДУ (ОБ'ЄДНАНА ЛОГІКА) ---

@router.message(NewsAdminStates.waiting_for_field)
async def process_admin_input(message: Message, state: FSMContext, session: AsyncSession):
    """Універсальний обробник вводу для всіх полів редактора новин"""
    data = await state.get_data()
    field = data.get("editing_field")

    # 1. ОБРОБКА ФОТО ДЛЯ НОВИНИ
    if field == "photo":
        if message.photo:
            # Беремо останнє фото (найкраща якість)
            await state.update_data(photo_id=message.photo[-1].file_id)
        else:
            return await message.answer("⚠️ Будь ласка, надішліть зображення як фото (не файл).")

    # 2. ПОШУК ТОВАРУ ДЛЯ ПРИВ'ЯЗКИ
    elif field == "product_search":
        if not message.text:
            return await message.answer("⚠️ Введіть назву або код товару текстом.")

        pattern = f"%{message.text}%"
        # Шукаємо товари, у яких є хоча б один активний склад
        active_exists = exists().where(
            ProductStock.product_code == Product.code,
            ProductStock.is_active == True
        )

        stmt = (
            select(Product)
            .where(active_exists)
            .where((Product.code.ilike(pattern)) | (Product.name_ua.ilike(pattern)))
            .limit(5)
            .options(selectinload(Product.photos))
        )
        products = (await session.execute(stmt)).scalars().all()

        if not products:
            return await message.answer("❌ Товарів не знайдено або вони відсутні на складі. Спробуйте ще раз:")

        for p in products:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ ОБРАТИ ЦЕЙ ТОВАР", callback_data=f"n_select_p_{p.code}")
            cap = f"<b>{p.name_ua}</b>\nКод: <code>{p.code}</code>"

            # Безпечна відправка фото товару
            photo_to_send = None
            if p.photos and p.photos[0].tg_file_id:
                photo_to_send = p.photos[0].tg_file_id

            if photo_to_send:
                try:
                    await message.answer_photo(
                        photo=photo_to_send,
                        caption=cap,
                        reply_markup=kb.as_markup(),
                        parse_mode="HTML"
                    )
                except Exception:
                    # Якщо ID файлу невірний, відправляємо текстом
                    await message.answer(cap, reply_markup=kb.as_markup(), parse_mode="HTML")
            else:
                await message.answer(cap, reply_markup=kb.as_markup(), parse_mode="HTML")
        return  # Виходимо, щоб не викликати refresh_editor завчасно

    # 3. ТЕКСТОВІ ПОЛЯ (ЗАГОЛОВОК, ТЕКСТ, ДАТА)
    else:
        if not message.text:
            return await message.answer("⚠️ Будь ласка, введіть текст.")

        # Якщо редагуємо дату, записуємо в потрібний ключ
        key = "pub_date" if field == "date" else field
        await state.update_data({key: message.text})

    # Повертаємо користувача в головне меню редактора
    await state.set_state(NewsAdminStates.in_editor)
    await refresh_editor(message, state, session)


# Ви можете видалити стару функцію process_input, оскільки NewsAdminStates.waiting_for_field
# тепер повністю обробляється однією функцією вище.


@router.callback_query(F.data.startswith("n_select_p_"))
async def select_product_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    code = callback.data.replace("n_select_p_", "")
    data = await state.get_data()

    stmt = select(Product).where(Product.code == code).options(selectinload(Product.photos))
    product = (await session.execute(stmt)).scalar_one()

    # Розумне фото: тільки якщо в новині порожньо
    photo_id = data.get("photo_id")
    if not photo_id and product.photos:
        photo_id = product.photos[0].tg_file_id

    await state.update_data(product_code=code, photo_id=photo_id)
    await state.set_state(NewsAdminStates.in_editor)
    await refresh_editor(callback, state, session)


# --- ПОШУК ТОВАРУ ДЛЯ НОВИНИ ---

@router.callback_query(NewsAdminStates.in_editor, F.data == "n_search_prod")
async def news_search_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(NewsAdminStates.waiting_for_field)
    await state.update_data(editing_field="product_search")
    await callback.message.answer("🔍 Введіть назву або код товару для пошуку:")


# @router.message(NewsAdminStates.waiting_for_field, F.text)
# async def process_input(message: Message, state: FSMContext, session: AsyncSession):
#     data = await state.get_data()
#     field = data.get("editing_field")
#
#     if field == "product_search":
#         pattern = f"%{message.text}%"
#         active_exists = exists().where(ProductStock.product_code == Product.code, ProductStock.is_active == True)
#         stmt = select(Product).where(active_exists).where(
#             (Product.code.ilike(pattern)) | (Product.name_ua.ilike(pattern))
#         ).limit(5).options(selectinload(Product.photos))
#         products = (await session.execute(stmt)).scalars().all()
#
#         if not products:
#             return await message.answer("❌ Нічого не знайдено. Спробуйте інший запит:")
#
#         for p in products:
#             kb = InlineKeyboardBuilder()
#             kb.button(text="✅ ОБРАТИ", callback_data=f"n_select_p_{p.code}")
#             cap = f"<b>{p.name_ua}</b>\nКод: <code>{p.code}</code>"
#             if p.photos:
#                 await message.answer_photo(p.photos[0].tg_file_id, caption=cap, reply_markup=kb.as_markup(),
#                                            parse_mode="HTML")
#             else:
#                 await message.answer(cap, reply_markup=kb.as_markup(), parse_mode="HTML")
#         return
#
#     # Для інших полів (title, content, date)
#     if field == "photo" and message.photo:
#         await state.update_data(photo_id=message.photo[-1].file_id)
#     else:
#         key = "pub_date" if field == "date" else field
#         await state.update_data({key: message.text})
#
#     await state.set_state(NewsAdminStates.in_editor)
#     await refresh_editor(message, state, session)


@router.callback_query(F.data.startswith("n_select_p_"))
async def select_product_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    code = callback.data.replace("n_select_p_", "")
    data = await state.get_data()

    stmt = select(Product).where(Product.code == code).options(selectinload(Product.photos))
    product = (await session.execute(stmt)).scalar_one()

    # Розумне фото
    new_photo = data.get("photo_id")
    if not new_photo and product.photos:
        new_photo = product.photos[0].tg_file_id

    await state.update_data(product_code=code, photo_id=new_photo)
    await state.set_state(NewsAdminStates.in_editor)
    await refresh_editor(callback, state, session)


@router.callback_query(NewsAdminStates.in_editor, F.data == "n_remove_prod")
async def n_rem_prod(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.update_data(product_code=None)
    await refresh_editor(callback, state, session)


# --- ПУБЛІКАЦІЯ ---

@router.callback_query(NewsAdminStates.in_editor, F.data == "n_publish")
async def n_publish(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    if not data.get("title") or not data.get("content"):
        return await callback.answer("⚠️ Заголовок та опис обов'язкові!", show_alert=True)

    try:
        dt = datetime.strptime(data["pub_date"], "%d.%m.%Y")
    except:
        return await callback.answer("⚠️ Невірний формат дати (ДД.ММ.РРРР)", show_alert=True)

    news_status = data.get("is_published", False)

    if data.get("news_id"):
        news = await session.get(ProductNews, data["news_id"])
        news.title = data["title"]
        news.content = data["content"]
        news.product_code = data["product_code"]
        news.photo_id = data["photo_id"]
        news.published_at = dt
        # news.is_published = data.get("is_published", True)
        news.is_published = news_status
    else:
        session.add(ProductNews(
            title=data["title"], content=data["content"],
            product_code=data["product_code"], photo_id=data["photo_id"],
            published_at=dt, is_published=news_status
        ))

    await session.commit()
    await state.clear()
    status_text = "опубліковано" if news_status else "збережено як чернетку"
    await callback.message.answer(f"✅ Новину успішно {status_text}!")

    with suppress(Exception):
        await callback.message.delete()


@router.callback_query(F.data.startswith("del_news_"))
async def delete_news(callback: CallbackQuery, session: AsyncSession):
    news = await session.get(ProductNews, int(callback.data.split("_")[2]))
    if news:
        await session.delete(news)
        await session.commit()
        await callback.message.delete()
        await callback.answer("✅ Видалено")


@router.callback_query(F.data == "n_cancel")
async def n_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Скасовано")