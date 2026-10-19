from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from shop.models import User


class UserMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")

        if tg_user:
            try:
                # Отримуємо користувача разом з його ролями через prefetch_related
                user = await User.objects.prefetch_related('roles').aget(user_id=tg_user.id)
                data["user"] = user
            except User.DoesNotExist:
                data["user"] = None

        return await handler(event, data)