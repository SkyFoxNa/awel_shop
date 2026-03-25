from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User, UserReview
from states.user_states import ProfileEdit
from keyboards.reply import get_main_kb
from utils.validators import validate_ua_phone

router = Router()


# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def calculate_user_rating(reviews: list[UserReview]) -> tuple[float, str]:
    """Розрахунок рейтингу для профілю"""
    if not reviews:
        return 5.0, "⭐" * 5
    avg = sum(r.rating for r in reviews) / len(reviews)
    avg = round(avg, 1)
    stars = "⭐" * int(avg) + ("🌓" if (avg - int(avg)) >= 0.4 else "")
    return avg, stars


def get_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_edit_profile")]
    ])


async def send_profile_info(message: types.Message, user: User):
    """Вивід розширеної картки профілю з новими даними."""

    # ПІБ або нікнейм
    display_name = f"{user.user_surname or ''} {user.user_name or ''}".strip() or user.username or "Не вказано"
    phone = user.phone or "❌ Не додано"

    # Розрахунок рейтингу (reviews мають бути підвантажені через selectinload)
    rating_val, stars = calculate_user_rating(user.reviews)

    # Ролі (красивий список)
    roles_list = [r.role.description for r in user.roles if r.role.description]
    roles_str = ", ".join(roles_list) if roles_list else "Клієнт"

    # Статус активності
    status_str = "✅ Активний" if user.is_active else "🚫 Заблокований"

    text = (
        f"<b>👤 Ваш профіль</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 <b>Ім'я:</b> {display_name}\n"
        f"📞 <b>Тел:</b> <code>{phone}</code>\n"
        f"🎭 <b>Ролі:</b> {roles_str}\n"
        f"📊 <b>Статус:</b> {status_str}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 <b>Ваш рейтинг:</b> {rating_val} {stars}\n"
        f"💰 <b>Бонусний баланс:</b> <b>{user.balance_points}</b> балів\n"
        f"📈 <b>Загальний оборот:</b> <b>{user.total_spent}</b> грн\n"
        f"📉 <b>Персональна знижка:</b> {user.discount_pct}%\n"
        f"━━━━━━━━━━━━━━\n"
        f"📝 <b>Нотатка від магазину:</b>\n<i>{user.admin_notes or 'Відсутня'}</i>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<i>Покажіть штрихкод вище касиру для нарахування бонусів</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Змінити ПІБ", callback_data="edit_name")],
        [InlineKeyboardButton(text="📱 Змінити телефон", callback_data="edit_phone_step")],
        [InlineKeyboardButton(text="🔄 Оновити дані", callback_data="refresh_profile")]
    ])

    # Якщо повідомлення вже з фото (штрихкодом), міняємо caption, інакше answer
    if message.photo:
        await message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


# --- ЗАГАЛЬНІ ХЕНДЛЕРИ ---

@router.message(F.text == "👤 Профіль")
async def show_profile_cmd(message: types.Message, user: User, session: AsyncSession):
    # Оскільки нам потрібні відгуки та описи ролей, переконуємось, що вони завантажені
    from sqlalchemy import select
    from db.models import UserRole, Role

    # Оновлюємо об'єкт user з усіма зв'язками для коректного відображення
    stmt = select(User).where(User.id == user.id).options(
        selectinload(User.roles).joinedload(UserRole.role),
        selectinload(User.reviews)
    )
    user_updated = (await session.execute(stmt)).scalar_one()

    from utils.barcode_gen import generate_user_barcode
    from aiogram.types import BufferedInputFile

    barcode_img = generate_user_barcode(user_updated.barcode)
    photo = BufferedInputFile(barcode_img.getvalue(), filename=f"profile_{user_updated.id}.png")

    await message.delete()
    await message.answer_photo(photo=photo)
    await send_profile_info(message, user_updated)


@router.callback_query(F.data == "refresh_profile")
async def refresh_profile(callback: CallbackQuery, user: User, session: AsyncSession):
    from sqlalchemy import select
    from db.models import UserRole

    stmt = select(User).where(User.id == user.id).options(
        selectinload(User.roles).joinedload(UserRole.role),
        selectinload(User.reviews)
    )
    user_updated = (await session.execute(stmt)).scalar_one()

    await send_profile_info(callback.message, user_updated)
    await callback.answer("Дані оновлено")


@router.callback_query(F.data == "cancel_edit_profile")
async def cancel_edit(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession):
    await state.clear()
    await callback.answer("Скасовано")
    # Повертаємось до профілю (передаємо session для підвантаження даних)
    await show_profile_cmd(callback.message, user, session)


# --- ЛОГІКА: РЕДАГУВАННЯ ПІБ ---

@router.callback_query(F.data == "edit_name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введіть ваше <b>Прізвище</b>:", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(ProfileEdit.waiting_for_surname)
    await callback.answer()


@router.message(ProfileEdit.waiting_for_surname)
async def process_surname(message: types.Message, state: FSMContext):
    if not message.text or len(message.text) < 2:
        return await message.answer("Прізвище занадто коротке. Спробуйте ще раз:", reply_markup=get_cancel_kb())
    await state.update_data(surname=message.text.strip())
    await message.answer("Тепер введіть ваше <b>Ім'я</b>:", reply_markup=get_cancel_kb(), parse_mode="HTML")
    await state.set_state(ProfileEdit.waiting_for_name)


@router.message(ProfileEdit.waiting_for_name)
async def process_name_finish(message: types.Message, state: FSMContext, session: AsyncSession, user: User):
    if not message.text or len(message.text) < 2:
        return await message.answer("Ім'я занадто коротке. Спробуйте ще раз:", reply_markup=get_cancel_kb())

    data = await state.get_data()
    user.user_surname = data['surname']
    user.user_name = message.text.strip()

    # Оновлюємо повне ім'я для документів
    user.full_name_1c = f"{user.user_surname} {user.user_name}".strip()

    await session.commit()
    await state.clear()
    await message.answer("✅ Дані оновлено!", reply_markup=get_main_kb(user))
    await show_profile_cmd(message, user, session)


# --- ЛОГІКА: ТЕЛЕФОН ---

@router.callback_query(F.data == "edit_phone_step")
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    contact_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📲 Надіслати номер", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await callback.message.answer("Надішліть номер кнопкою або введіть вручну (0XXXXXXXXX):", reply_markup=contact_kb)
    await state.set_state(ProfileEdit.waiting_for_phone)
    await callback.answer()


@router.message(ProfileEdit.waiting_for_phone)
async def process_phone_finish(message: types.Message, state: FSMContext, session: AsyncSession, user: User):
    raw_phone = message.contact.phone_number if message.contact else message.text
    valid_phone = validate_ua_phone(raw_phone)

    if not valid_phone:
        return await message.answer("❌ Невірний формат. Спробуйте ще раз (0XXXXXXXXX):", reply_markup=get_cancel_kb())

    user.phone = valid_phone
    await session.commit()
    await state.clear()

    await message.answer(f"✅ Номер збережено!", reply_markup=get_main_kb(user))
    await show_profile_cmd(message, user, session)
