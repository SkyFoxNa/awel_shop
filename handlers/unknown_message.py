from aiogram import Router, types
from aiogram.fsm.context import FSMContext

router = Router()


@router.message()
async def delete_unexpected(message: types.Message, state: FSMContext):
    """
    Видаляє всі повідомлення, що не пройшли фільтри інших роутерів.
    Це дозволяє тримати чат чистим від випадкових текстів, стікерів або команд.
    """
    try:
        await message.delete()
    except Exception:
        # Може виникнути помилка, якщо у бота немає прав на видалення
        # або повідомлення вже видалене
        pass

    # Очищуємо стан, якщо користувач застряг у якомусь FSM процесі
    await state.clear()