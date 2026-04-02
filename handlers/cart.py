from aiogram import Router, F, types

router = Router()

@router.callback_query(F.data.startswith("add_cart_"))
async def cmd_add_cart_stub(callback: types.CallbackQuery):
    # Виводимо спливаюче вікно (alert)
    await callback.answer(
        "🛒 Кошик наразі у розробці.\nСкоро ви зможете додавати товари!", 
        show_alert=True
    )

