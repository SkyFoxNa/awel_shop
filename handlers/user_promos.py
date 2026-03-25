from aiogram import Router, F, types
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Promotion, User, UserPromoLog

router = Router()


@router.message(F.text == "🔥 Акції")
async def list_promos(message: types.Message, session: AsyncSession, user: User):
    user_role_ids = [r.role_id for r in user.roles]

    stmt = select(Promotion).options(
        selectinload(Promotion.target_roles),
        selectinload(Promotion.user_logs)
    ).where(Promotion.is_active == True)

    result = await session.execute(stmt)
    all_promos = result.scalars().all()

    # Фільтрація за ролями
    promos = [
        p for p in all_promos
        if any(r.id in user_role_ids for r in p.target_roles) or not p.target_roles
    ]

    if not promos:
        return await message.answer("🎁 Зараз немає доступних акцій.")

    bot_info = await message.bot.get_me()

    for promo in promos:
        builder = InlineKeyboardBuilder()

        # ЛОГІКА РЕФЕРАЛКИ
        if promo.promo_type == "referral":
            ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.user_id}"
            text = (f"🤝 <b>{promo.title}</b>\n\n{promo.description}\n\n"
                    f"🔗 Твоє посилання (натисни, щоб скопіювати):\n"
                    f"<code>{ref_link}</code>")

            builder.row(InlineKeyboardButton(
                text="📤 Поділитися з другом",
                switch_inline_query=f"\nПриєднуйся до AWEL Shop за моїм посиланням та отримуй бонуси!\n{ref_link}"
            ))

        # ЛОГІКА АКЦІЙ ЗА ПОСИЛАННЯМ
        else:
            is_claimed = any(log.user_id == user.id for log in promo.user_logs)
            if promo.promo_type == "link" and not is_claimed:
                builder.row(InlineKeyboardButton(
                    text=f"🔗 Перейти та отримати {promo.bonus_points} балів",
                    callback_data=f"claim_link_reward_{promo.id}"
                ))
            elif promo.link_url:
                builder.row(InlineKeyboardButton(text="🔗 Перейти до сайту", url=promo.link_url))

            text = f"<b>{promo.title}</b>\n\n{promo.description}"
            if is_claimed:
                text += "\n\n✅ <i>Ви вже отримали бонус за перехід</i>"

        if promo.image_id:
            await message.answer_photo(photo=promo.image_id, caption=text, reply_markup=builder.as_markup(),
                                       parse_mode="HTML")
        else:
            await message.answer(text=text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("claim_link_reward_"))
async def claim_link_reward(callback: CallbackQuery, session: AsyncSession, user: User):
    promo_id = int(callback.data.split("_")[3])
    promo = await session.get(Promotion, promo_id)

    if not promo:
        return await callback.answer()

    stmt = select(UserPromoLog).where(UserPromoLog.user_id == user.id, UserPromoLog.promo_id == promo_id)
    exists = (await session.execute(stmt)).scalar_one_or_none()

    if not exists:
        user.balance_points += promo.bonus_points
        session.add(UserPromoLog(user_id=user.id, promo_id=promo_id))
        await session.commit()

    await callback.answer()

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=f"🔗 Перейти до сайту", url=promo.link_url))
    await callback.message.edit_reply_markup(reply_markup=kb.as_markup())