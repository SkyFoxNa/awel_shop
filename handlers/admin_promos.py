import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop.models import Promotion, Role
from utils.states import AdminPromoAdd

router = Router()


# ==========================================
# ДОПОМІЖНІ ФУНКЦІЇ (HELPERS)
# ==========================================

async def get_roles_keyboard(selected_ids: list, is_editing: bool = False, promo_id: int = None):
    """Генерує клавіатуру вибору ролей для створення або редагування"""
    builder = InlineKeyboardBuilder()

    async for r in Role.objects.all():
        mark = "✅ " if r.id in selected_ids else ""
        cb_data = f"edit_promo_role_{promo_id}_{r.id}" if is_editing else f"promo_role_toggle_{r.id}"
        builder.row(InlineKeyboardButton(text=f"{mark}{r.description or r.name}", callback_data=cb_data))

    confirm_cb = f"view_promo_{promo_id}" if is_editing else "promo_roles_confirm"
    builder.row(InlineKeyboardButton(text="📥 ПІДТВЕРДИТИ ТА ПОВЕРНУТИСЬ", callback_data=confirm_cb))
    return builder.as_markup()


# ==========================================
# ГОЛОВНЕ МЕНЮ ТА СПИСКИ
# ==========================================

@router.message(F.text == "📢 Акції")
async def admin_promos_selection(message: Message):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👥 Рефералка", callback_data="manage_promo_referral"))
    kb.row(InlineKeyboardButton(text="🔗 За посиланням", callback_data="manage_promo_link"))
    kb.row(InlineKeyboardButton(text="📦 Товарні", callback_data="manage_promo_product"))
    await message.answer("<b>Керування акціями:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "manage_promo_referral")
async def manage_referral_promo(callback: CallbackQuery):
    """Спеціальний обробник для рефералки (вона завжди одна)"""
    promo = await Promotion.objects.filter(promo_type="referral").afirst()

    if not promo:
        promo = await Promotion.objects.acreate(
            title="Приведи друга",
            description="Отримуйте бонуси за запрошення друзів!",
            promo_type="referral",
            is_active=False,
            bonus_points=50
        )

    await show_promo_card(callback, promo_id=promo.id)


@router.callback_query(F.data.startswith("manage_promo_"))
async def list_promos_by_type(callback: CallbackQuery):
    p_type = callback.data.split("_")[2]

    promos = []
    async for p in Promotion.objects.filter(promo_type=p_type).order_by('-id'):
        promos.append(p)

    builder = InlineKeyboardBuilder()

    for p in promos:
        status = "✅" if p.is_active else "🚫"
        builder.row(
            InlineKeyboardButton(text=f"{status} {p.title}", callback_data=f"view_promo_{p.id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"del_promo_{p.id}")
        )

    builder.row(InlineKeyboardButton(text="➕ Додати нову", callback_data=f"add_promo_{p_type}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_promos_main"))

    text = f"Список акцій [<b>{p_type.upper()}</b>]:"

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("add_promo_"))
async def start_add_promo(callback: CallbackQuery, state: FSMContext):
    """Початок процесу створення нової акції через FSM"""
    p_type = callback.data.split("_")[2]

    await state.clear()
    await state.update_data(promo_type=p_type)

    await state.set_state(AdminPromoAdd.waiting_for_title)

    await callback.message.answer(f"🚀 Створення акції типу: <b>{p_type}</b>\n\nВведіть назву акції:", parse_mode="HTML")
    await callback.answer()


# ==========================================
# КАРТКА РЕДАГУВАННЯ ТА РОЛІ
# ==========================================

@router.callback_query(F.data.startswith("view_promo_"))
async def show_promo_card(callback: CallbackQuery, promo_id: int = None):
    if not promo_id:
        promo_id = int(callback.data.split("_")[2])

    try:
        promo = await Promotion.objects.prefetch_related('target_roles').aget(id=promo_id)
    except Promotion.DoesNotExist:
        return await callback.answer("Акцію не знайдено.")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"📝 Назва: {promo.title}", callback_data=f"edit_field_title_{promo.id}"))

    img_status = "✅ Є" if promo.image_id else "❌ Немає"
    builder.row(
        InlineKeyboardButton(text=f"🖼 Фото: {img_status} (змінити)", callback_data=f"edit_field_photo_{promo.id}"))
    builder.row(InlineKeyboardButton(text="📖 Редагувати опис", callback_data=f"edit_field_desc_{promo.id}"))
    builder.row(
        InlineKeyboardButton(text=f"💰 Бали: {promo.bonus_points}", callback_data=f"edit_field_points_{promo.id}"))

    roles_count = len([r async for r in promo.target_roles.all()])
    builder.row(
        InlineKeyboardButton(text=f"🎯 Ролі: {roles_count} обрано", callback_data=f"edit_promo_roles_{promo.id}"))

    status_btn = "✅ Активна (Вимкнути?)" if promo.is_active else "🚫 Вимкнена (Увімкнути?)"
    builder.row(InlineKeyboardButton(text=status_btn, callback_data=f"tog_promo_{promo.id}"))

    back_data = "admin_promos_main" if promo.promo_type == "referral" else f"manage_promo_{promo.promo_type}"
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_data))

    text = (f"<b>Тип:</b> {promo.promo_type}\n"
            f"<b>Назва:</b> {promo.title}\n"
            f"<b>Опис:</b> {promo.description}\n\n"
            f"🛠 <b>Редагування #{promo.id}</b>")

    await callback.message.delete()
    if promo.image_id:
        await callback.message.answer_photo(photo=promo.image_id, caption=text, reply_markup=builder.as_markup(),
                                            parse_mode="HTML")
    else:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("edit_promo_roles_"))
async def edit_promo_roles_view(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[3])
    try:
        promo = await Promotion.objects.prefetch_related('target_roles').aget(id=promo_id)
    except Promotion.DoesNotExist:
        return await callback.answer("Акцію не знайдено.")

    selected_ids = [r.id async for r in promo.target_roles.all()]

    kb = await get_roles_keyboard(selected_ids, is_editing=True, promo_id=promo_id)
    text = "Оберіть ролі, які бачитимуть цю акцію:"

    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("edit_promo_role_"))
async def toggle_promo_role_db(callback: CallbackQuery):
    parts = callback.data.split("_")
    promo_id, role_id = int(parts[3]), int(parts[4])

    try:
        promo = await Promotion.objects.prefetch_related('target_roles').aget(id=promo_id)
        role = await Role.objects.aget(id=role_id)
    except (Promotion.DoesNotExist, Role.DoesNotExist):
        return await callback.answer("Помилка отримання даних")

    current_roles = [r.id async for r in promo.target_roles.all()]

    if role.id in current_roles:
        await promo.target_roles.aremove(role)
        current_roles.remove(role.id)
    else:
        await promo.target_roles.aadd(role)
        current_roles.append(role.id)

    kb = await get_roles_keyboard(current_roles, is_editing=True, promo_id=promo_id)
    await callback.message.edit_reply_markup(reply_markup=kb)


# ==========================================
# ОБРОБКА FSM (РЕДАГУВАННЯ ТА СТВОРЕННЯ)
# ==========================================

@router.callback_query(F.data.startswith("edit_field_"))
async def edit_field_start(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    field, promo_id = parts[2], int(parts[3])
    await state.update_data(edit_promo_id=promo_id, edit_field=field)

    prompts = {
        "title": "Введіть нову назву акції:",
        "photo": "Надішліть нове фото (одним зображенням):",
        "desc": "Введіть новий опис:",
        "points": "Введіть кількість бонусних балів:"
    }

    await callback.message.answer(prompts.get(field, "Введіть значення:"))
    await state.set_state(AdminPromoAdd.waiting_for_image if field == "photo" else AdminPromoAdd.waiting_for_title)


@router.message(AdminPromoAdd.waiting_for_title)
async def process_text_input(message: Message, state: FSMContext):
    data = await state.get_data()
    promo_id = data.get("edit_promo_id")
    field = data.get("edit_field")

    # РЕЖИМ РЕДАГУВАННЯ
    if promo_id:
        try:
            promo = await Promotion.objects.aget(id=promo_id)
            if field == "title":
                promo.title = message.text
            elif field == "desc":
                promo.description = message.text
            elif field == "points":
                if not message.text.isdigit():
                    return await message.answer("Будь ласка, введіть число!")
                promo.bonus_points = int(message.text)

            await promo.asave()
            await state.clear()
            kb = InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="📝 Назад до акції", callback_data=f"view_promo_{promo_id}"))
            return await message.answer("✅ Дані успішно оновлено!", reply_markup=kb.as_markup())
        except Promotion.DoesNotExist:
            await state.clear()
            return await message.answer("❌ Акцію не знайдено!")

    # РЕЖИМ СТВОРЕННЯ (Крок 1: Назва)
    await state.update_data(title=message.text)
    await message.answer("📖 Тепер введіть опис акції:")
    await state.set_state(AdminPromoAdd.waiting_for_desc)


@router.message(AdminPromoAdd.waiting_for_image)
async def process_image_input(message: Message, state: FSMContext):
    data = await state.get_data()
    promo_id = data.get("edit_promo_id")
    file_id = message.photo[-1].file_id if message.photo else None

    # РЕЖИМ РЕДАГУВАННЯ ФОТО
    if promo_id:
        if not file_id:
            return await message.answer("Потрібно надіслати фото!")
        try:
            promo = await Promotion.objects.aget(id=promo_id)
            promo.image_id = file_id
            await promo.asave()
            await state.clear()
            kb = InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="📝 Назад до акції", callback_data=f"view_promo_{promo_id}"))
            return await message.answer("✅ Фото акції оновлено!", reply_markup=kb.as_markup())
        except Promotion.DoesNotExist:
            await state.clear()
            return await message.answer("❌ Акцію не знайдено!")

    # РЕЖИМ СТВОРЕННЯ (Крок 3: Фото)
    await state.update_data(image_id=file_id)
    kb = await get_roles_keyboard([])
    await message.answer("🎯 Оберіть ролі, які зможуть бачити цю акцію:", reply_markup=kb)
    await state.set_state(AdminPromoAdd.waiting_for_role)


# ==========================================
# РЕШТА ОБРОБНИКІВ (TOGGLE, DELETE, CONFIRM)
# ==========================================

@router.callback_query(F.data.startswith("tog_promo_"))
async def toggle_promo_status(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[2])
    try:
        promo = await Promotion.objects.aget(id=promo_id)
        promo.is_active = not promo.is_active
        await promo.asave()
        await callback.answer("Статус змінено!")
        await show_promo_card(callback, promo_id=promo.id)
    except Promotion.DoesNotExist:
        await callback.answer("Акцію не знайдено", show_alert=True)


@router.callback_query(F.data.startswith("del_promo_"))
async def delete_promo(callback: CallbackQuery):
    promo_id = int(callback.data.split("_")[2])
    try:
        promo = await Promotion.objects.aget(id=promo_id)
        if promo.promo_type != "referral":
            await promo.adelete()
            await callback.answer("Акцію видалено")
            await list_promos_by_type(callback)
        else:
            await callback.answer("Цю акцію не можна видалити!", show_alert=True)
    except Promotion.DoesNotExist:
        await callback.answer("Акцію вже видалено", show_alert=True)


@router.callback_query(F.data == "admin_promos_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await admin_promos_selection(callback.message)


# ==========================================
# ПРОДОВЖЕННЯ ЛАНЦЮЖКА СТВОРЕННЯ (FSM)
# ==========================================

@router.message(AdminPromoAdd.waiting_for_desc)
async def process_desc(message: Message, state: FSMContext):
    """Крок 2: Отримання опису та перехід до фото"""
    await state.update_data(description=message.text)
    await message.answer("🖼 Тепер надішліть фото для акції (або надішліть будь-який текст, щоб пропустити):")
    await state.set_state(AdminPromoAdd.waiting_for_image)


@router.callback_query(F.data.startswith("promo_role_toggle_"))
async def toggle_role_in_state(callback: CallbackQuery, state: FSMContext):
    """Вибір ролей під час створення нової акції (зберігаємо в state)"""
    role_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    selected = data.get("selected_roles", [])

    if role_id in selected:
        selected.remove(role_id)
    else:
        selected.append(role_id)

    await state.update_data(selected_roles=selected)

    kb = await get_roles_keyboard(selected, is_editing=False)
    await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data == "promo_roles_confirm")
async def confirm_roles_and_move_on(callback: CallbackQuery, state: FSMContext):
    """Перехід до нарахування балів після вибору ролей"""
    data = await state.get_data()

    if data.get("promo_type") == "referral":
        await callback.message.answer("💰 Введіть кількість балів за друга (число):")
        await state.set_state(AdminPromoAdd.waiting_for_points)
    else:
        await callback.message.answer("🔗 Введіть посилання (URL) для акції:")
        await state.set_state(AdminPromoAdd.waiting_for_link)


@router.message(AdminPromoAdd.waiting_for_link)
async def process_link(message: Message, state: FSMContext):
    """Отримання лінка та перехід до балів"""
    await state.update_data(link_url=message.text)
    await message.answer("💰 Введіть кількість бонусних балів за виконання умов:")
    await state.set_state(AdminPromoAdd.waiting_for_points)


@router.message(AdminPromoAdd.waiting_for_points)
async def final_save_new_promo(message: Message, state: FSMContext):
    """Фінальне збереження нової акції в БД"""
    if not message.text.isdigit():
        return await message.answer("Будь ласка, введіть числове значення!")

    data = await state.get_data()

    new_p = await Promotion.objects.acreate(
        title=data['title'],
        description=data['description'],
        image_id=data.get('image_id'),
        link_url=data.get('link_url'),
        promo_type=data['promo_type'],
        bonus_points=int(message.text),
        is_active=True
    )

    if data.get('selected_roles'):
        async for role in Role.objects.filter(id__in=data['selected_roles']):
            await new_p.target_roles.aadd(role)

    await state.clear()

    await message.answer(f"✅ Акцію «{new_p.title}» успішно створено та активовано!")
    await admin_promos_selection(message)
