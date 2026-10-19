from aiogram import Router, F, types
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop.models import Promotion, User, UserPromoLog

router = Router()


@router.message(F.text == "🔥 Акції")
async def list_promos(message: types.Message, user: User = None):
    if not user:
        try:
            user = await User.objects.prefetch_related('roles').aget(user_id=message.from_user.id)
        except User.DoesNotExist:
            return await message.answer("❌ Помилка завантаження даних користувача.")

    user_role_ids = [r.id async for r in user.roles.all()]

    # Завантажуємо активні акції з ролями та логами
    all_promos = []
    qs = Promotion.objects.prefetch_related('target_roles', 'user_logs').filter(is_active=True)

    async for p in qs:
        all_promos.append(p)

    # Фільтрація за ролями
    promos = []
    for p in all_promos:
        target_roles_ids = [r.id async for r in p.target_roles.all()]
        if not target_roles_ids or any(r_id in user_role_ids for r_id in target_roles_ids):
            promos.append(p)

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
            # Виправлено promo_id -> promotion_id
            is_claimed = await UserPromoLog.objects.filter(user_id=user.id, promotion_id=promo.id).aexists()

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
async def claim_link_reward(callback: CallbackQuery, user: User = None):
    promo_id = int(callback.data.split("_")[3])

    try:
        promo = await Promotion.objects.aget(id=promo_id)
    except Promotion.DoesNotExist:
        return await callback.answer("❌ Акцію не знайдено.")

    if not user:
        try:
            user = await User.objects.aget(user_id=callback.from_user.id)
        except User.DoesNotExist:
            return await callback.answer("❌ Помилка користувача.")

    # Виправлено promo_id -> promotion_id
    is_claimed = await UserPromoLog.objects.filter(user_id=user.id, promotion_id=promo.id).aexists()

    if not is_claimed:
        user.balance_points = float(user.balance_points or 0.0) + float(promo.bonus_points)
        await user.asave()
        # Виправлено promo_id -> promotion_id
        await UserPromoLog.objects.acreate(user_id=user.id, promotion_id=promo.id)

    await callback.answer("🎉 Бонус успішно нараховано!")

    kb = InlineKeyboardBuilder()
    if promo.link_url:
        kb.row(InlineKeyboardButton(text="🔗 Перейти до сайту", url=promo.link_url))

    await callback.message.edit_reply_markup(reply_markup=kb.as_markup())