import logging
import traceback
from aiogram import Router, Bot, html
from aiogram.types import ErrorEvent
from asgiref.sync import sync_to_async  # <-- Додати імпорт
from django.db import connection

from shop.models import User

router = Router()


async def get_admins_ids():
    """Шукає в базі через Django ORM усіх користувачів з ролями admin або owner."""
    admin_ids = []
    async for user_id in User.objects.filter(
        roles__name__in=["admin", "owner"]
    ).values_list('user_id', flat=True).distinct():
        admin_ids.append(user_id)

    return admin_ids


@router.errors()
async def global_error_handler(event: ErrorEvent, bot: Bot):
    logging.error(f"🚨 Виникла помилка: {event.exception}", exc_info=True)

    # 2. Безпечно закриваємо з'єднання в асинхронному контексті
    try:
        await sync_to_async(connection.close)()
    except Exception as db_err:
        logging.error(f"Помилка при закритті з'єднання з БД: {db_err}")

    # 1. Отримуємо ID адмінів
    admin_ids = await get_admins_ids()

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

    # 4. Розсилка сповіщень адмінам
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=admin_message)
        except Exception as e:
            logging.error(f"Не вдалося надіслати повідомлення адміну {admin_id}: {e}")

    # 5. Відповідь користувачу
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