from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable
from asgiref.sync import sync_to_async
from django.db import close_old_connections


class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Закриваємо старі/неробочі з'єднання перед обробкою події у поточному потоці
        await sync_to_async(close_old_connections)()

        try:
            return await handler(event, data)
        finally:
            # Очищаємо з'єднання після завершення обробки
            await sync_to_async(close_old_connections)()