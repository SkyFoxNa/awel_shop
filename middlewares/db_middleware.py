from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable
from django.db import connection, close_old_connections


class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        # Закриваємо будь-які старі/завислі з'єднання перед початком обробки
        close_old_connections()

        try:
            return await handler(event, data)
        finally:
            # Примусово закриваємо з'єднання після завершення події,
            # щоб вощого не тримати сокет відкритим під час простою
            connection.close()