from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

from shop.models import ProductStock, PromotionItem


async def get_user_permissions(user):
    """Визначає категорії доступу на основі імен ролей користувача"""
    if not user or not hasattr(user, 'roles'):
        return False, False

    role_names = [role.name.lower() async for role in user.roles.all()]

    is_any_client = any("client" in name for name in role_names)

    privileged_roles = ['admin', 'owner', 'manager', 'seller', 'warehouse']
    is_privileged = any(name in privileged_roles for name in role_names)

    return is_any_client, is_privileged


async def get_product_display_data(product, user):
    """
    Збирає всі дані для відображення: ціни, акції, залишки.
    """
    is_client, is_privileged = await get_user_permissions(user)

    # 1. Завантажуємо залишки (використовуємо поле product)
    stocks = []
    async for stock in ProductStock.objects.filter(product=product):
        stocks.append(stock)

    if not stocks:
        return None

    # Беремо ціну з першого знайденого складу як базу
    base_price = Decimal(str(stocks[0].price))

    # 2. Перевірка активної акції (виправлено: product=product замість product_code=product.code)
    now = timezone.now()
    promo_item = await PromotionItem.objects.filter(
        product=product,
        promotion__is_active=True
    ).filter(
        Q(promotion__end_date__isnull=True) | Q(promotion__end_date__gt=now)
    ).select_related('promotion').afirst()

    final_price = base_price
    is_promo = False

    if promo_item and promo_item.discount_price:
        final_price = Decimal(str(promo_item.discount_price))
        is_promo = True
    elif is_client and user:
        discount = Decimal(str(user.discount_pct or 0))
        final_price = base_price * (Decimal('1') - (discount / Decimal('100')))

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