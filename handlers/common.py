from aiogram import Router, F, types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from aiogram.filters import Command

from keyboards.reply import BTN_CARD, BTN_HOME, get_main_kb
from db.models import User, UserRole
from utils.barcode_gen import generate_user_barcode

router = Router()

# --- ХЕНДЛЕР ПОВЕРНЕННЯ ДОДОМУ ---
@router.message(F.text.in_({BTN_HOME, "🏠", "/start"}))
async def cmd_home(message: types.Message, session: AsyncSession):
    # Отримуємо свіжі дані користувача з ролями
    stmt = (
        select(User)
        .where(User.user_id == message.from_user.id)
        .options(selectinload(User.roles).joinedload(UserRole.role))
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return await message.answer("Помилка: користувача не знайдено в базі.")

    await message.answer(
        f"🏠 <b>Головне меню</b>\nПривіт, {user.user_name}! Оберіть потрібний розділ:",
        reply_markup=get_main_kb(user),
        parse_mode="HTML"
    )

# --- ВАША КАРТКА ---
@router.message(F.text == BTN_CARD)
async def show_card(message: types.Message, user: User):
    if not user: return
    try: await message.delete()
    except: pass

    barcode_img = generate_user_barcode(user.barcode)
    photo = types.BufferedInputFile(barcode_img.getvalue(), filename=f"card.png")

    full_name = f"{user.user_surname or ''} {user.user_name or ''}".strip() or user.username or "Клієнт"
    caption = (
        f"💳 <b>Ваша картка клієнта</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 <b>Клієнт:</b> {full_name}\n"
        f"📞 <b>Тел:</b> {user.phone or 'не вказано'}\n"
        f"━━━━━━━━━━━━━━\n"
        f"<i>Покажіть цей штрихкод на касі</i>"
    )
    await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")

# --- ДОПОМОГА ТА ПРО НАС ---
@router.message(F.text == "❓ Допомога")
async def help_msg(message: types.Message):
    await message.answer("📞 Техпідтримка: @awel_admin\nДопоможемо з будь-яким питанням!")

@router.message(F.text == "ℹ️ Про нас")
async def about_msg(message: types.Message):
    await message.answer("🏢 <b>AWEL Shop</b>\nМи займаємося запчастинами вже багато років...")