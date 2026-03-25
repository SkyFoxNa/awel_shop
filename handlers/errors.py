import logging
import traceback
from aiogram import Router, Bot, html
from aiogram.types import ErrorEvent
from sqlalchemy import select

from db.models import User, Role, UserRole

router = Router()


async def get_admins_ids(session_pool):
    """Шукає в базі всіх користувачів з ролями admin або owner."""
    async with session_pool() as session:
        stmt = (
            select(User.user_id)
            .join(User.roles)
            .join(UserRole.role)
            .where(Role.name.in_(["admin", "owner"]))
        )
        result = await session.execute(stmt)

        # Отримуємо список один раз!
        admin_ids = list(result.scalars().all())

        # print(f"DEBUG: Знайдені адміни: {admin_ids}")
        return admin_ids


@router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot, session_pool):
    logging.error(f"🚨 Виникла помилка: {event.exception}", exc_info=True)

    # 1. Отримуємо ID адмінів
    admin_ids = await get_admins_ids(session_pool)

    # 2. Отримуємо повний Traceback
    tb_list = traceback.format_exception(
        None, event.exception, event.exception.__traceback__
    )
    tb_string = "".join(tb_list)

    # 3. Екрануємо текст, щоб символи < > & не ламали HTML
    safe_tb = html.quote(tb_string[-3500:])

    admin_message = (
        f"⚠️ <b>Критична помилка!</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"❌ <b>Тип:</b> <code>{type(event.exception).__name__}</code>\n"
        f"📝 <b>Текст:</b> <code>{html.quote(str(event.exception))}</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"📜 <b>Traceback:</b>\n<code>{safe_tb}</code>"
    )

    # 4. Розсилка
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_message)
        except Exception as e:
            logging.error(f"Не вдалося надіслати повідомлення адміну {admin_id}: {e}")

    # 5. Повідомлення користувачу (ваша стара логіка)
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(
                "⚠️ Внутрішня помилка. Адміністратори вже отримали звіт.",
                show_alert=True
            )
        elif event.update.message:
            await event.update.message.answer(
                "❌ Щось пішло не так. Ми вже працюємо над цим!"
            )
    except Exception as e:
        logging.error(f"Не вдалося відповісти користувачу: {e}")

    return True