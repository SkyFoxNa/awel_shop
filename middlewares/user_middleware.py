from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models import User


class UserMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        tg_user = data.get("event_from_user")

        if tg_user and session:
            # Шукаємо юзера разом з ролями
            stmt = select(User).where(User.user_id == tg_user.id).options(selectinload(User.roles))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            # Передаємо об'єкт user в хендлери
            data["user"] = user

        return await handler(event, data)