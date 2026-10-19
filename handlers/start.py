import logging
from aiogram import Router, types, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import BufferedInputFile

# Імпорт моделей Django та утиліт
from shop.models import User, Role, UserRole, Promotion
from utils.barcode_gen import generate_user_barcode
from keyboards.reply import get_main_kb

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message, bot: Bot, command: CommandObject = None):
    """
    Головний обробник команди /start на Django ORM.
    """
    user_id = message.from_user.id
    args = command.args if command else None

    # 1. Перевірка, чи існує користувач у базі
    try:
        user = await User.objects.prefetch_related('roles').aget(user_id=user_id)
    except User.DoesNotExist:
        user = None

    if not user:
        # --- БЛОК РЕФЕРАЛЬНОЇ СИСТЕМИ ---
        referrer = None
        ref_bonus = 50.0  # Значення за замовчуванням

        # Шукаємо налаштування реферальної акції
        promo_ref = await Promotion.objects.filter(
            promo_type="referral",
            is_active=True
        ).afirst()

        if promo_ref:
            ref_bonus = float(promo_ref.bonus_points)

        # Перевіряємо реферальне посилання
        if args and args.startswith("ref_"):
            try:
                target_tg_id = int(args.replace("ref_", ""))
                if target_tg_id != user_id:
                    referrer = await User.objects.filter(user_id=target_tg_id).afirst()
            except ValueError:
                logging.warning(f"Невірний формат реферального ID: {args}")

        # 2. Створення нового користувача
        new_barcode_value = f"AW{user_id}"

        user = await User.objects.acreate(
            user_id=user_id,
            user_name=message.from_user.first_name,
            user_surname=message.from_user.last_name,
            username=message.from_user.username,
            barcode=new_barcode_value,
            visit=1,
            discount_pct=3.0,
            balance_points=0.0,
            referrer=referrer
        )

        # 3. Нарахування балів обом сторонам
        if referrer:
            if referrer.balance_points is None:
                referrer.balance_points = 0.0

            user.balance_points = ref_bonus
            await user.asave()

            referrer.balance_points = float(referrer.balance_points) + ref_bonus
            await referrer.asave()

            try:
                await bot.send_message(
                    referrer.user_id,
                    f"🎉 Ваше реферальне посилання спрацювало!\n"
                    f"Новий клієнт <b>{user.user_name}</b> зареєструвався.\n"
                    f"Вам нараховано <b>{int(ref_bonus)} балів</b>! 💰"
                )
            except Exception as e:
                logging.error(f"Не вдалося надіслати повідомлення рефереру {referrer.user_id}: {e}")

        # 4. Призначення базової ролі "client"
        client_role = await Role.objects.filter(name="client").afirst()

        if client_role:
            await UserRole.objects.acreate(user=user, role=client_role)
        else:
            logging.error("КРИТИЧНА ПОМИЛКА: Роль 'client' не знайдена в БД!")

        # 5. Привітання та картка клієнта
        welcome_text = "🎉 <b>Вітаємо в AWEL Shop!</b>\n"
        if referrer:
            welcome_text += f"\n🎁 Вам нараховано <b>{int(ref_bonus)} бонусів</b> за реферальною програмою!\n"

        try:
            barcode_img = generate_user_barcode(user.barcode)
            photo = BufferedInputFile(barcode_img.getvalue(), filename=f"card_{user.barcode}.png")

            await message.answer_photo(
                photo=photo,
                caption=(
                    f"{welcome_text}\n"
                    f"Ви зареєстровані як клієнт. Вище — ваша віртуальна карта.\n"
                    f"Пред'являйте її менеджеру для отримання знижок."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Помилка генерації штрихкоду для {user_id}: {e}")
            await message.answer(f"{welcome_text}\nВи успішно зареєстровані!")

        # 6. Сповіщення адміністрації
        await notify_staff(bot, user)

    else:
        # Оновлюємо лічильник візитів
        user.visit += 1
        await user.asave()
        await message.answer(f"З поверненням, {user.user_name}! Раді бачити вас знову. 😊")

    # 7. Головне меню
    await message.answer("Оберіть розділ меню:", reply_markup=get_main_kb(user))


async def notify_staff(bot: Bot, user: User):
    """Сповіщення менеджерів та адміністраторів"""
    staff_members = []
    async for staff in User.objects.filter(roles__name__in=["admin", "manager"]).distinct():
        staff_members.append(staff)

    admin_msg = (
        f"🆕 <b>Новий користувач у боті!</b>\n"
        f"👤 Ім'я: {user.user_name} {user.user_surname or ''}\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"🏷 Штрихкод: <code>{user.barcode}</code>\n"
        f"🔗 Username: @{user.username or 'немає'}"
    )

    for staff in staff_members:
        try:
            await bot.send_message(staff.user_id, admin_msg, parse_mode="HTML")
        except Exception:
            continue