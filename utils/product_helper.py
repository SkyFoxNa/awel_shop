from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from db.models import ProductStock, PromotionItem, Promotion, User


def get_user_permissions(user_roles: list):
    """Визначає категорії доступу на основі імен ролей"""
    # Перетворюємо об'єкти ролей у список назв (маленькими літерами)
    role_names = [r.role.name.lower() for r in user_roles]

    # Шукаємо корінь 'client' для масштабованості
    is_any_client = any("client" in name for name in role_names)

    # Список привілейованих ролей
    privileged_roles = ['admin', 'owner', 'manager', 'seller', 'warehouse']
    is_privileged = any(name in privileged_roles for name in role_names)

    return is_any_client, is_privileged


async def get_product_display_data(session, product, user):
    """
    Збирає всі дані для відображення: ціни, акції, залишки.
    """
    is_client, is_privileged = get_user_permissions(user.roles)

    # 1. Завантажуємо залишки (Location підтягнеться через lazy="joined")
    stmt = select(ProductStock).where(ProductStock.product_code == product.code)
    stocks = (await session.execute(stmt)).scalars().all()

    if not stocks:
        return None

    # Беремо ціну з першого знайденого складу як базу
    base_price = Decimal(str(stocks[0].price))

    # 2. Перевірка активної акції
    promo_stmt = (
        select(PromotionItem)
        .join(Promotion)
        .where(
            PromotionItem.product_code == product.code,
            Promotion.is_active == True
        )
        .where((Promotion.end_date == None) | (Promotion.end_date > func.now()))
    )
    promo_item = (await session.execute(promo_stmt)).scalar_one_or_none()

    final_price = base_price
    is_promo = False

    if promo_item:
        final_price = Decimal(str(promo_item.discount_price))
        is_promo = True
    elif is_client:
        # Якщо не акція, застосовуємо персональну знижку клієнта
        discount = Decimal(str(user.discount_pct or 0))
        final_price = base_price * (1 - discount / 100)

    # 3. Фільтрація залишків: Клієнти бачать тільки ID 2 (Автокрамниця) та 3 (Магазин)
    shop_ids = [2, 3]
    visible_stocks = [s for s in stocks if is_privileged or s.location_id in shop_ids]

    return {
        "final_price": round(final_price, 2),
        "base_price": round(base_price, 2),
        "is_promo": is_promo,
        "is_client": is_client,
        "is_privileged": is_privileged,
        "total_balance": sum(s.balance for s in visible_stocks),
        "visible_stocks": visible_stocks
    }