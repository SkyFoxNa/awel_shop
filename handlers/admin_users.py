import logging
from contextlib import suppress
from aiogram import Router, F, Bot, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from django.db.models import Q

from shop.models import User, Role, Review
from utils.states import AdminUserSearch, AdminUserAction, AdminUserEdit
from keyboards.admin_kb import get_admin_panel_kb, get_user_list_kb
from keyboards.reply import get_main_kb
from utils.barcode_gen import generate_user_barcode

router = Router()


# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def calculate_rating(reviews_list: list) -> tuple[float, str]:
    """Розрахунок середнього рейтингу (лише ті відгуки, що стосуються користувача)"""
    user_reviews = [r for r in reviews_list if getattr(r, 'review_type', '') == "user"]

    if not user_reviews:
        return 5.0, "⭐" * 5

    avg = sum(r.rating for r in user_reviews) / len(user_reviews)
    avg = round(avg, 1)
    stars = "⭐" * int(avg) + ("🌓" if (avg - int(avg)) >= 0.4 else "")
    return avg, stars


async def get_user_card_content(user: User):
    """Формує текст картки та інлайн-кнопки (вимагає завантажених roles та received_reviews)"""
    roles_list = []
    if user and user.roles:
        async for role in user.roles.all():
            roles_list.append(role.description or role.name)

    roles_str = ", ".join(roles_list) if roles_list else "Немає ролей"
    lock_emoji = "🔐" if user.is_locked else "🔓"
    active_emoji = "✅ Активний" if user.is_active else "🚫 Забанений"

    received_reviews = [r async for r in user.received_reviews.all()]
    rating_val, stars = calculate_rating(received_reviews)

    text = (
        f"👤 <b>Клієнт:</b> {user.user_name} {user.user_surname or ''}\n"
        f"📊 <b>Рейтинг:</b> {rating_val} {stars} ({len(received_reviews)} відгуків)\n"
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


async def get_user_with_relations(user_db_id: int) -> User | None:
    """Отримуємо юзера з префетчем ролей та отриманих відгуків"""
    try:
        return await User.objects.prefetch_related('roles', 'received_reviews').aget(id=user_db_id)
    except User.DoesNotExist:
        return None


# --- НАВІГАЦІЯ ТА ПОШУК ---

@router.message(F.text == "🛠 Панель керування")
async def cmd_admin_panel(message: Message):
    await message.answer("🛠 Панель керування відкрита", reply_markup=get_admin_panel_kb())


@router.message(F.text == "👥 Користувачі")
@router.callback_query(AdminUserAction.filter(F.action == "list"))
async def admin_users_main(union: Message | CallbackQuery):
    users = []
    async for u in User.objects.all().order_by('id')[:10]:
        users.append(u)

    kb = get_user_list_kb(users, page=0)
    msg_text = "👥 Список користувачів (перші 10):"

    if isinstance(union, Message):
        await union.answer(msg_text, reply_markup=kb)
    else:
        with suppress(Exception):
            await union.message.delete()
        await union.message.answer(msg_text, reply_markup=kb)


@router.callback_query(F.data == "start_user_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminUserSearch.waiting_for_query)
    await callback.message.answer("🔍 Введіть ПІБ або номер телефону клієнта:")
    await callback.answer()


@router.message(AdminUserSearch.waiting_for_query)
async def process_search(message: Message, state: FSMContext):
    q = message.text.strip()

    users = []
    qs = User.objects.filter(
        Q(user_name__icontains=q) |
        Q(user_surname__icontains=q) |
        Q(username__icontains=q) |
        Q(phone__icontains=q)
    ).prefetch_related('roles', 'received_reviews')[:10]

    async for u in qs:
        users.append(u)

    if not users:
        return await message.answer("❌ Нікого не знайдено. Спробуйте ще раз.")

    await state.clear()
    await message.answer(f"🔎 Результати для '{message.text}':", reply_markup=get_user_list_kb(users, 0))


@router.callback_query(AdminUserAction.filter(F.action == "view"))
async def view_user_card(callback: CallbackQuery, callback_data: AdminUserAction):
    user = await get_user_with_relations(callback_data.user_db_id)
    if not user:
        return await callback.answer("Користувача не знайдено!")

    barcode_img = generate_user_barcode(user.barcode)
    photo = BufferedInputFile(barcode_img.getvalue(), filename=f"u_{user.id}.png")
    text, kb = await get_user_card_content(user)

    with suppress(Exception):
        await callback.message.delete()

    await callback.message.answer_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")


# --- РЕДАГУВАННЯ (FSM) ---

@router.callback_query(AdminUserAction.filter(F.action == "edit_balance"))
async def start_balance(callback: CallbackQuery, callback_data: AdminUserAction, state: FSMContext):
    await state.update_data(target_id=callback_data.user_db_id)
    await state.set_state(AdminUserEdit.waiting_for_balance)
    await callback.message.answer("💰 Введіть суму для зміни балансу (напр. 100 або -50):")
    await callback.answer()


@router.message(AdminUserEdit.waiting_for_balance)
async def save_balance(message: Message, state: FSMContext):
    clean_text = message.text.lstrip('-')
    if not clean_text.isdigit():
        return await message.answer("❌ Введіть ціле число.")

    data = await state.get_data()
    user = await get_user_with_relations(data['target_id'])

    if user:
        user.balance_points = float(user.balance_points or 0.0) + float(message.text)
        await user.asave()

        user = await get_user_with_relations(user.id)
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
async def save_discount(message: Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("❌ Введіть число.")

    data = await state.get_data()
    user = await get_user_with_relations(data['target_id'])

    if user:
        user.discount_pct = val
        await user.asave()

        user = await get_user_with_relations(user.id)
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
async def save_note(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await get_user_with_relations(data['target_id'])

    if user:
        user.admin_notes = message.text
        await user.asave()

        user = await get_user_with_relations(user.id)
        text, kb = await get_user_card_content(user)
        await message.answer_photo(
            photo=BufferedInputFile(generate_user_barcode(user.barcode).getvalue(), filename="u.png"),
            caption=text, reply_markup=kb, parse_mode="HTML"
        )

    await state.clear()


# --- ВІДГУКИ ТА СТАТУСИ ---

@router.callback_query(AdminUserAction.filter(F.action == "view_reviews"))
async def view_reviews(callback: CallbackQuery, callback_data: AdminUserAction):
    reviews = []
    async for r in Review.objects.filter(target_user_id=callback_data.user_db_id).order_by('-created_at')[:5]:
        reviews.append(r)

    if not reviews:
        return await callback.answer("Відгуків про цього клієнта ще немає.", show_alert=True)

    text = "💬 <b>Останні відгуки про клієнта:</b>\n\n"
    for r in reviews:
        stars_str = "⭐" * int(r.rating)
        date_str = r.created_at.strftime('%d.%m.%y') if r.created_at else ''
        text += f"{stars_str} ({date_str})\n<i>{r.comment}</i>\n\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=AdminUserAction(action="view", user_db_id=callback_data.user_db_id))

    await callback.message.edit_caption(
        caption=text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(AdminUserAction.filter(F.action.in_({"toggle_active", "toggle_lock"})))
async def toggle_status(callback: CallbackQuery, callback_data: AdminUserAction):
    user = await get_user_with_relations(callback_data.user_db_id)
    if not user:
        return await callback.answer("Помилка завантаження!")

    if callback_data.action == "toggle_active":
        user.is_active = not user.is_active
    else:
        user.is_locked = not user.is_locked

    await user.asave()
    user = await get_user_with_relations(user.id)

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
async def edit_roles(callback: CallbackQuery, callback_data: AdminUserAction):
    user = await get_user_with_relations(callback_data.user_db_id)
    if not user:
        return await callback.answer("Користувача не знайдено!")

    user_role_ids = [r.id async for r in user.roles.all()]

    builder = InlineKeyboardBuilder()
    async for r in Role.objects.all():
        prefix = "✅ " if r.id in user_role_ids else ""
        builder.button(
            text=f"{prefix}{r.description or r.name}",
            callback_data=AdminUserAction(action="toggle_role", user_db_id=user.id, role_id=r.id).pack()
        )

    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminUserAction(action="view", user_db_id=user.id).pack())
    )

    msg_text = f"🎭 Ролі користувача {user.user_name}:"
    try:
        await callback.message.edit_text(msg_text, reply_markup=builder.as_markup())
    except Exception:
        with suppress(Exception):
            await callback.message.delete()
        await callback.message.answer(msg_text, reply_markup=builder.as_markup())


@router.callback_query(AdminUserAction.filter(F.action == "toggle_role"))
async def toggle_role(callback: CallbackQuery, callback_data: AdminUserAction, bot: Bot):
    target_user = await get_user_with_relations(callback_data.user_db_id)
    try:
        role_obj = await Role.objects.aget(id=callback_data.role_id)
    except Role.DoesNotExist:
        role_obj = None

    if not target_user or not role_obj:
        return await callback.answer("Помилка даних")

    # Захист адміна (не можна зняти з себе)
    if role_obj.name == "admin" and target_user.user_id == callback.from_user.id:
        return await callback.answer("🚨 Ви не можете зняти адміна із себе!", show_alert=True)

    user_has_role = await target_user.roles.filter(id=role_obj.id).aexists()

    if user_has_role:
        await target_user.roles.aremove(role_obj)
        notif_text = f"❌ У вас відкликано роль: {role_obj.description or role_obj.name}"
    else:
        await target_user.roles.aadd(role_obj)
        notif_text = f"✅ Вам надано нову роль: {role_obj.description or role_obj.name}"

    target_user = await get_user_with_relations(target_user.id)

    try:
        await bot.send_message(
            chat_id=target_user.user_id,
            text=f"{notif_text}\n\nВаше головне меню оновлено.",
            reply_markup=get_main_kb(user=target_user)
        )
    except Exception as e:
        logging.error(f"Не вдалося сповістити користувача: {e}")

    await edit_roles(callback, callback_data)
