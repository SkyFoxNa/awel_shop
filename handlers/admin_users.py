from aiogram import Router, F, Bot, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramBadRequest
from contextlib import suppress

from db.models import User, Role, UserRole, UserReview
from utils.states import AdminUserSearch, AdminUserAction, AdminUserEdit
from keyboards.admin_kb import get_admin_panel_kb, get_user_list_kb
from keyboards.reply import get_main_kb
from utils.barcode_gen import generate_user_barcode

router = Router()


# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def calculate_rating(reviews: list[UserReview]) -> tuple[float, str]:
    """Розрахунок середнього рейтингу та зірочок (безпечний для асинхронності)"""
    if not reviews:
        return 5.0, "⭐" * 5

    # Працюємо зі списком, який вже завантажений через selectinload
    rev_list = list(reviews)
    avg = sum(r.rating for r in rev_list) / len(rev_list)
    avg = round(avg, 1)
    stars = "⭐" * int(avg) + ("🌓" if (avg - int(avg)) >= 0.4 else "")
    return avg, stars


async def get_user_card_content(user: User):
    """Формує текст картки та інлайн-кнопки (вимагає завантажених roles та reviews)"""
    roles_list = []
    if user.roles:
        for ur in user.roles:
            roles_list.append(ur.role.description or ur.role.name)

    roles_str = ", ".join(roles_list) if roles_list else "Немає ролей"
    lock_emoji = "🔐" if user.is_locked else "🔓"
    active_emoji = "✅ Активний" if user.is_active else "🚫 Забанений"

    rating_val, stars = calculate_rating(user.reviews)

    text = (
        f"👤 <b>Клієнт:</b> {user.user_name} {user.user_surname or ''}\n"
        f"📊 <b>Рейтинг:</b> {rating_val} {stars} ({len(user.reviews) if user.reviews else 0} відгуків)\n"
        f"🔌 <b>1С ID:</b> <code>{user.one_c_id or '---'}</code>\n"
        f"----------------------------------\n"
        f"📞 <b>Тел:</b> <code>{user.phone or '---'}</code>\n"
        f"🎭 <b>Ролі:</b> {roles_str}\n"
        f"💰 <b>Баланс:</b> <b>{user.balance_points}</b> балів\n"
        f"📈 <b>Оборот:</b> <b>{user.total_spent}</b> грн\n"
        f"📉 <b>Знижка:</b> {user.discount_pct}%\n"
        f"📝 <b>Нотатка:</b> <i>{user.admin_notes or 'порожньо'}</i>\n"
        f"📊 <b>Статус:</b> {active_emoji} | {lock_emoji} Дані 1С"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎭 Ролі",
                             callback_data=AdminUserAction(action="edit_roles", user_db_id=user.id).pack()),
        InlineKeyboardButton(text="🚫 Бан/Розбан",
                             callback_data=AdminUserAction(action="toggle_active", user_db_id=user.id).pack())
    )
    builder.row(
        InlineKeyboardButton(text="💰 Баланс +/-",
                             callback_data=AdminUserAction(action="edit_balance", user_db_id=user.id).pack()),
        InlineKeyboardButton(text="📉 Знижка %",
                             callback_data=AdminUserAction(action="edit_discount", user_db_id=user.id).pack()),
        InlineKeyboardButton(text="💬 Відгуки",
                             callback_data=AdminUserAction(action="view_reviews", user_db_id=user.id).pack())
    )
    builder.row(
        InlineKeyboardButton(text="📝 Нотатка",
                             callback_data=AdminUserAction(action="edit_note", user_db_id=user.id).pack()),
        InlineKeyboardButton(text=f"{lock_emoji} Замок 1С",
                             callback_data=AdminUserAction(action="toggle_lock", user_db_id=user.id).pack())
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад до списку",
                                     callback_data=AdminUserAction(action="list", user_db_id=0).pack()))

    return text, builder.as_markup()


async def get_user_with_relations(session: AsyncSession, user_db_id: int):
    """Універсальна функція для отримання юзера з повним набором даних без помилок сесії"""
    stmt = select(User).where(User.id == user_db_id).options(
        selectinload(User.roles).joinedload(UserRole.role),
        selectinload(User.reviews)
    )
    result = await session.execute(stmt)
    user = result.unique().scalar_one_or_none()

    if user:
        # Важливо для випадків, коли адмін редагує сам себе (merge об'єднує дані в сесії)
        user = await session.merge(user)
    return user


# --- НАВІГАЦІЯ ТА ПОШУК ---

@router.message(F.text == "🛠 Панель керування")
async def cmd_admin_panel(message: Message):
    await message.answer("🛠 Панель керування відкрита", reply_markup=get_admin_panel_kb())


@router.message(F.text == "👥 Користувачі")
@router.callback_query(AdminUserAction.filter(F.action == "list"))
async def admin_users_main(union: Message | CallbackQuery, session: AsyncSession):
    stmt = select(User).limit(10).order_by(User.id)
    users = (await session.execute(stmt)).scalars().all()
    kb = get_user_list_kb(users, page=0)
    msg_text = "👥 Список користувачів (перші 10):"

    if isinstance(union, Message):
        await union.answer(msg_text, reply_markup=kb)
    else:
        try:
            await union.message.delete()
        except:
            pass
        await union.message.answer(msg_text, reply_markup=kb)


@router.callback_query(F.data == "start_user_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminUserSearch.waiting_for_query)
    await callback.message.answer("🔍 Введіть ПІБ або номер телефону клієнта:")
    await callback.answer()


@router.message(AdminUserSearch.waiting_for_query)
async def process_search(message: Message, session: AsyncSession, state: FSMContext):
    q = f"%{message.text.strip()}%"
    stmt = select(User).where(or_(
        User.user_name.ilike(q), User.user_surname.ilike(q),
        User.username.ilike(q), User.phone.ilike(q)
    )).limit(10).options(selectinload(User.roles).joinedload(UserRole.role), selectinload(User.reviews))

    result = await session.execute(stmt)
    users = result.unique().scalars().all()

    if not users:
        return await message.answer("❌ Нікого не знайдено. Спробуйте ще раз.")

    await state.clear()
    await message.answer(f"🔎 Результати для '{message.text}':", reply_markup=get_user_list_kb(users, 0))


@router.callback_query(AdminUserAction.filter(F.action == "view"))
async def view_user_card(callback: CallbackQuery, callback_data: AdminUserAction, session: AsyncSession):
    user = await get_user_with_relations(session, callback_data.user_db_id)
    if not user: return await callback.answer("Користувача не знайдено!")

    barcode_img = generate_user_barcode(user.barcode)
    photo = BufferedInputFile(barcode_img.getvalue(), filename=f"u_{user.id}.png")
    text, kb = await get_user_card_content(user)

    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")


# --- РЕДАГУВАННЯ (FSM) ---

@router.callback_query(AdminUserAction.filter(F.action == "edit_balance"))
async def start_balance(callback: CallbackQuery, callback_data: AdminUserAction, state: FSMContext):
    await state.update_data(target_id=callback_data.user_db_id)
    await state.set_state(AdminUserEdit.waiting_for_balance)
    await callback.message.answer("💰 Введіть суму для зміни балансу (напр. 100 або -50):")
    await callback.answer()


@router.message(AdminUserEdit.waiting_for_balance)
async def save_balance(message: Message, state: FSMContext, session: AsyncSession):
    clean_text = message.text.lstrip('-')
    if not clean_text.isdigit():
        return await message.answer("❌ Введіть ціле число.")

    data = await state.get_data()
    user = await get_user_with_relations(session, data['target_id'])

    if user:
        user.balance_points += int(message.text)
        await session.commit()

        # Оновлюємо об'єкт після коміту для коректного відображення
        user = await get_user_with_relations(session, user.id)

        text, kb = await get_user_card_content(user)
        barcode_img = generate_user_barcode(user.barcode)
        photo = BufferedInputFile(barcode_img.getvalue(), filename="u.png")

        await message.answer("✅ Баланс оновлено.")
        await message.answer_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")

    await state.clear()


@router.callback_query(AdminUserAction.filter(F.action == "edit_discount"))
async def start_discount(callback: CallbackQuery, callback_data: AdminUserAction, state: FSMContext):
    await state.update_data(target_id=callback_data.user_db_id)
    await state.set_state(AdminUserEdit.waiting_for_discount)
    await callback.message.answer("📉 Введіть новий % знижки (напр. 5.5):")
    await callback.answer()


@router.message(AdminUserEdit.waiting_for_discount)
async def save_discount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = float(message.text.replace(",", "."))
    except:
        return await message.answer("❌ Введіть число.")

    data = await state.get_data()
    user = await get_user_with_relations(session, data['target_id'])

    if user:
        user.discount_pct = val
        await session.commit()
        user = await get_user_with_relations(session, user.id)

        text, kb = await get_user_card_content(user)
        await message.answer_photo(
            photo=BufferedInputFile(generate_user_barcode(user.barcode).getvalue(), filename="u.png"),
            caption=text, reply_markup=kb, parse_mode="HTML"
        )

    await state.clear()


@router.callback_query(AdminUserAction.filter(F.action == "edit_note"))
async def start_note(callback: CallbackQuery, callback_data: AdminUserAction, state: FSMContext):
    await state.update_data(target_id=callback_data.user_db_id)
    await state.set_state(AdminUserEdit.waiting_for_note)
    await callback.message.answer("📝 Введіть нотатку для клієнта:")
    await callback.answer()


@router.message(AdminUserEdit.waiting_for_note)
async def save_note(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    user = await get_user_with_relations(session, data['target_id'])

    if user:
        user.admin_notes = message.text
        await session.commit()
        user = await get_user_with_relations(session, user.id)

        text, kb = await get_user_card_content(user)
        await message.answer_photo(
            photo=BufferedInputFile(generate_user_barcode(user.barcode).getvalue(), filename="u.png"),
            caption=text, reply_markup=kb, parse_mode="HTML"
        )

    await state.clear()


# --- ВІДГУКИ ТА СТАТУСИ ---

@router.callback_query(AdminUserAction.filter(F.action == "view_reviews"))
async def view_reviews(callback: CallbackQuery, callback_data: AdminUserAction, session: AsyncSession):
    stmt = select(UserReview).where(UserReview.user_id == callback_data.user_db_id).order_by(
        UserReview.created_at.desc())
    reviews = (await session.execute(stmt)).scalars().all()
    if not reviews: return await callback.answer("Відгуків ще немає.", show_alert=True)

    text = "💬 <b>Останні відгуки:</b>\n\n"
    for r in reviews[:5]:
        text += f"{'⭐' * r.rating} ({r.created_at.strftime('%d.%m.%y')})\n<i>{r.comment}</i>\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=AdminUserAction(action="view", user_db_id=callback_data.user_db_id))
    await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(AdminUserAction.filter(F.action.in_({"toggle_active", "toggle_lock"})))
async def toggle_status(callback: CallbackQuery, callback_data: AdminUserAction, session: AsyncSession):
    user = await get_user_with_relations(session, callback_data.user_db_id)
    if not user: return await callback.answer("Помилка завантаження!")

    if callback_data.action == "toggle_active":
        user.is_active = not user.is_active
    else:
        user.is_locked = not user.is_locked

    await session.commit()
    user = await get_user_with_relations(session, user.id)

    text, kb = await get_user_card_content(user)
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=BufferedInputFile(generate_user_barcode(user.barcode).getvalue(), filename="u.png"),
            caption=text,
            parse_mode="HTML"
        ),
        reply_markup=kb
    )
    await callback.answer("Статус оновлено")


# --- РОЛІ ---

@router.callback_query(AdminUserAction.filter(F.action == "edit_roles"))
async def edit_roles(callback: CallbackQuery, callback_data: AdminUserAction, session: AsyncSession):
    # 1. Знаходимо юзера в кеші сесії, якщо він там є
    existing_user = await session.get(User, callback_data.user_db_id)
    if existing_user:
        # ПРИМУСОВО скидаємо кеш для цього об'єкта, щоб SQL запит нижче
        # реально пішов у базу за новими зв'язками ролей
        session.expire(existing_user)

    # 2. Отримуємо свіжі ролі та юзера з бази (через наш get_user_with_relations)
    all_roles = (await session.execute(select(Role))).scalars().all()
    user = await get_user_with_relations(session, callback_data.user_db_id)

    builder = InlineKeyboardBuilder()
    for r in all_roles:
        # Перевіряємо наявність ролі через завантажений список
        has_role = any(ur.role_id == r.id for ur in user.roles)
        prefix = "✅ " if has_role else ""
        builder.button(
            text=f"{prefix}{r.description or r.name}",
            callback_data=AdminUserAction(action="toggle_role", user_db_id=user.id, role_id=r.id).pack()
        )

    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminUserAction(action="view", user_db_id=user.id).pack()))

    msg_text = f"🎭 Ролі користувача {user.user_name}:"
    try:
        await callback.message.edit_text(msg_text, reply_markup=builder.as_markup())
    except:
        await callback.message.delete()
        await callback.message.answer(msg_text, reply_markup=builder.as_markup())


@router.callback_query(AdminUserAction.filter(F.action == "toggle_role"))
async def toggle_role(callback: CallbackQuery, callback_data: AdminUserAction, session: AsyncSession, bot: Bot):
    target_user = await get_user_with_relations(session, callback_data.user_db_id)
    role_obj = await session.get(Role, callback_data.role_id)

    if not target_user or not role_obj:
        return await callback.answer("Помилка даних")

    # Захист адміна (не можна зняти з себе)
    if role_obj.name == "admin" and target_user.user_id == callback.from_user.id:
        return await callback.answer("🚨 Ви не можете зняти адміна із себе!", show_alert=True)

    stmt = select(UserRole).where(UserRole.user_id == target_user.id, UserRole.role_id == role_obj.id)
    link = (await session.execute(stmt)).scalar_one_or_none()

    notif_text = ""
    if link:
        await session.delete(link)
        notif_text = f"❌ У вас відкликано роль: {role_obj.description or role_obj.name}"
    else:
        session.add(UserRole(user_id=target_user.id, role_id=role_obj.id))
        notif_text = f"✅ Вам надано нову роль: {role_obj.description or role_obj.name}"

    await session.commit()

    # Оновлюємо дані користувача для коректної передачі в клавіатуру
    target_user = await get_user_with_relations(session, target_user.id)

    try:
        await bot.send_message(
            chat_id=target_user.user_id,
            text=f"{notif_text}\n\nВаше головне меню оновлено.",
            reply_markup=get_main_kb(user=target_user)  # Виправлено: передаємо аргумент 'user'
        )
    except Exception as e:
        print(f"Не вдалося сповістити користувача: {e}")

    await edit_roles(callback, callback_data, session)