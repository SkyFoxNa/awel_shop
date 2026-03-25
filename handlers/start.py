import logging
from aiogram import Router, types, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Імпорт моделей та утиліт
from db.models import User, Role, UserRole, Promotion
from utils.barcode_gen import generate_user_barcode
from keyboards.reply import get_main_kb

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message, session: AsyncSession, bot: Bot, command: CommandObject = None):
    """
    Головний обробник команди /start.
    Відповідає за реєстрацію, реферальну систему, генерацію картки клієнта та меню.
    """
    user_id = message.from_user.id
    # Отримуємо аргументи (наприклад, для посилання виду t.me/bot?start=ref_12345)
    args = command.args if command else None

    # 1. Перевірка, чи існує користувач у базі
    stmt = select(User).where(User.user_id == user_id).options(selectinload(User.roles))
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user:
        # --- БЛОК РЕФЕРАЛЬНОЇ СИСТЕМИ ---
        referrer = None
        ref_bonus = 50.0  # Значення за замовчуванням

        # Шукаємо налаштування реферальної акції в БД
        promo_stmt = select(Promotion).where(
            Promotion.promo_type == "referral",
            Promotion.is_active == True
        )
        promo_ref = (await session.execute(promo_stmt)).scalar_one_or_none()

        if promo_ref:
            ref_bonus = float(promo_ref.bonus_points)

        # Перевіряємо, чи прийшов користувач за посиланням
        if args and args.startswith("ref_"):
            try:
                target_tg_id = int(args.replace("ref_", ""))
                # Забороняємо саморефералку
                if target_tg_id != user_id:
                    ref_query = select(User).where(User.user_id == target_tg_id)
                    referrer = (await session.execute(ref_query)).scalar_one_or_none()
            except ValueError:
                logging.warning(f"Невірний формат реферального ID: {args}")

        # 2. Створення нового запису користувача
        # Генеруємо унікальний штрихкод для 1С
        new_barcode_value = f"AW{user_id}"

        user = User(
            user_id=user_id,
            user_name=message.from_user.first_name,
            user_surname=message.from_user.last_name,
            username=message.from_user.username,
            barcode=new_barcode_value,
            visit=1,
            discount_pct=3.0,
            balance_points=0.0,  # Ініціалізуємо нулем, щоб уникнути NoneType помилок
            referrer_id=referrer.id if referrer else None
        )

        # 3. Нарахування балів обом сторонам
        if referrer:
            # Захист реферера від NULL у базі
            if referrer.balance_points is None:
                referrer.balance_points = 0.0

            user.balance_points = ref_bonus
            referrer.balance_points = float(referrer.balance_points) + ref_bonus

            # Повідомляємо того, хто запросив
            try:
                await bot.send_message(
                    referrer.user_id,
                    f"🎉 Ваше реферальне посилання спрацювало!\n"
                    f"Новий клієнт <b>{user.user_name}</b> зареєструвався.\n"
                    f"Вам нараховано <b>{int(ref_bonus)} балів</b>! 💰"
                )
            except Exception as e:
                logging.error(f"Не вдалося надіслати повідомлення рефереру {referrer.user_id}: {e}")

        session.add(user)
        await session.flush()  # Отримуємо ID для створення зв'язку з роллю

        # 4. Призначення базової ролі "client"
        role_stmt = select(Role).where(Role.name == "client")
        client_role = (await session.execute(role_stmt)).scalar_one_or_none()

        if client_role:
            session.add(UserRole(user_id=user.id, role_id=client_role.id))
        else:
            logging.error("КРИТИЧНА ПОМИЛКА: Роль 'client' не знайдена в БД!")

        await session.commit()
        await session.refresh(user)

        # 5. Привітання та відправка віртуальної картки
        welcome_text = "🎉 <b>Вітаємо в AWEL Shop!</b>\n"
        if referrer:
            welcome_text += f"\n🎁 Вам нараховано <b>{int(ref_bonus)} бонусів</b> за реферальною програмою!\n"

        try:
            # Генерація зображення штрихкоду
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

        # 6. Сповіщення адміністрації про нового юзера
        await notify_staff(bot, session, user)

    else:
        # Користувач вже існує — оновлюємо лічильник візитів
        user.visit += 1
        await session.commit()
        await message.answer(f"З поверненням, {user.user_name}! Раді бачити вас знову. 😊")

    # 7. Виклик головного меню
    await message.answer("Оберіть розділ меню:", reply_markup=get_main_kb(user))


async def notify_staff(bot: Bot, session: AsyncSession, user: User):
    """Допоміжна функція для сповіщення менеджерів"""
    staff_stmt = (
        select(User)
        .join(User.roles)
        .join(Role)
        .where(Role.name.in_(["admin", "manager"]))
    )
    staff_members = (await session.execute(staff_stmt)).unique().scalars().all()

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