from aiogram import Router, F, types

router = Router()

@router.callback_query(F.data.startswith("anlg_"))
async def cmd_show_analogs_stub(callback: types.CallbackQuery):
    await callback.answer(
        "🔄 Пошук аналогів у розробці.\nЦя функція з'явиться найближчим часом.", 
        show_alert=True
    )