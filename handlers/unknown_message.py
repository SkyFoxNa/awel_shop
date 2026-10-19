from contextlib import suppress
from aiogram import Router, types
from aiogram.fsm.context import FSMContext

router = Router()


@router.message()
async def delete_unexpected(message: types.Message, state: FSMContext):
    """
    Видаляє всі повідомлення, що не пройшли фільтри інших роутерів.
    Тримає чат чистим від випадкових текстів, стікерів або неопрацьованих команд.
    """
    with suppress(Exception):
        await message.delete()

    # Очищуємо стан на випадок, якщо користувач застряг у FSM
    await state.clear()