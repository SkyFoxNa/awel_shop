import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            logging.exception(f"Критична помилка у хендлері: {e}")

            # Визначаємо, як відповісти користувачу
            error_text = "⚠️ Сталася помилка при обробці запиту. Спробуйте пізніше."

            if isinstance(event, Message):
                await event.answer(error_text)
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(error_text, show_alert=True)
                except Exception:
                    pass

            return None