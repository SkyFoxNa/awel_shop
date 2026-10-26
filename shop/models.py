from django.db import models
from django.utils.translation import gettext_lazy as _

# ==============================================================================
# 1. ЕНУМЕРАТОРИ (Списки статусів)
# ==============================================================================

class OrderStatus(models.TextChoices):
    NEW = "new", _("Новий (Чернетка)")
    WAITING = "waiting", _("Очікує перевірки")
    APPROVED = "approved", _("Підтверджено")
    COMPLETED = "completed", _("Завершено")
    CANCELLED = "cancelled", _("Скасовано")


class ItemStatus(models.TextChoices):
    ACTIVE = "active", _("В замовленні")
    SOLD_OUT = "sold_out", _("Продано (Немає в наявності)")
    REJECTED = "rejected", _("Відхилено")
    REPLACED = "replaced", _("Замінено")


class ReviewType(models.TextChoices):
    SERVICE = "service", _("Обслуговування")
    PRODUCT = "product", _("Товар")
    USER = "user", _("Клієнт")


class PromoType(models.TextChoices):
    SIMPLE = "simple", _("Проста")
    QUANTITY = "quantity", _("За кількість")
    BUNDLE = "bundle", _("Комплект")
    FLASH = "flash", _("Швидка акція")


# ==============================================================================
# 2. КОРИСТУВАЧІ ТА ДОСТУП
# ==============================================================================

class Role(models.Model):
    """Доступні ролі: client, manager, admin, owner, pro_client тощо"""
    name = models.CharField(_("Назва ролі"), max_length=50, unique=True)
    description = models.CharField(_("Опис"), max_length=255, blank=True, null=True)

    class Meta:
        db_table = "roles"
        verbose_name = _("Роль")
        verbose_name_plural = _("Ролі")

    def __str__(self):
        return self.name


class User(models.Model):
    """Основна таблиця користувачів"""
    user_id = models.BigIntegerField(_("Telegram User ID"), unique=True)
    user_name = models.CharField(_("Ім'я TG"), max_length=255)
    user_surname = models.CharField(_("Прізвище TG"), max_length=255, blank=True, null=True)
    username = models.CharField(_("Username TG"), max_length=255, blank=True, null=True)

    full_name_1c = models.CharField(_("ПІБ в 1С"), max_length=255, blank=True, null=True)
    phone = models.CharField(_("Телефон"), max_length=50, blank=True, null=True)
    email = models.EmailField(_("Email"), max_length=255, blank=True, null=True)
    one_c_id = models.CharField(_("ID в 1С"), max_length=30, blank=True, null=True)
    barcode = models.CharField(_("Штрихкод"), max_length=50, unique=True, blank=True, null=True)

    discount_pct = models.DecimalField(_("Знижка %"), max_digits=5, decimal_places=2, default=3.0)
    total_spent = models.DecimalField(_("Всього витрачено"), max_digits=12, decimal_places=2, default=0.0)
    balance_points = models.DecimalField(_("Баланс балів"), max_digits=10, decimal_places=2, default=0.0)

    referrer = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='referrals', verbose_name=_("Хто запросив"))
    referral_code = models.CharField(_("Реферальний код"), max_length=50, unique=True, null=True, blank=True)
    personal_manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='managed_users', verbose_name=_("Персональний менеджер"))

    is_active = models.BooleanField(_("Активний"), default=True)
    admin_notes = models.TextField(_("Замітки адміна"), blank=True, null=True)
    is_locked = models.BooleanField(_("Заблокований"), default=False)
    visit = models.IntegerField(_("Кількість візитів"), default=1)
    created_at = models.DateTimeField(_("Дата реєстрації"), auto_now_add=True)

    roles = models.ManyToManyField(Role, through='UserRole', related_name='users', verbose_name=_("Ролі"))

    class Meta:
        db_table = "users"
        verbose_name = _("Користувач")
        verbose_name_plural = _("Користувачі")

    def __str__(self):
        return f"{self.user_name} ({self.user_id})"


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", verbose_name=_("Користувач"))
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id", verbose_name=_("Роль"))

    class Meta:
        db_table = "user_roles"
        unique_together = ('user', 'role')
        verbose_name = _("Зв'язок користувача і ролі")
        verbose_name_plural = _("Зв'язки користувачів і ролей")


# ==============================================================================
# 3. ЛОГІСТИКА ТА ВІДГУКИ
# ==============================================================================

class DeliveryAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id",
                             related_name="delivery_addresses", verbose_name=_("Користувач"))
    address_label = models.CharField(_("Назва адреси"), max_length=100)
    recipient_fio = models.CharField(_("ПІБ Отримувача"), max_length=255)
    recipient_phone = models.CharField(_("Телефон отримувача"), max_length=50)
    delivery_details = models.TextField(_("Деталі доставки"))
    delivery_type = models.IntegerField(_("Тип доставки"), default=1)
    is_default = models.BooleanField(_("За замовчуванням"), default=False)

    class Meta:
        db_table = "delivery_addresses"
        verbose_name = _("Адреса доставки")
        verbose_name_plural = _("Адреси доставки")

    def __str__(self):
        return f"{self.address_label} - {self.recipient_fio}"


class Location(models.Model):
    name = models.CharField(_("Назва локації/складу"), max_length=50, unique=True)

    class Meta:
        db_table = "locations"
        verbose_name = _("Локація/Склад")
        verbose_name_plural = _("Локації/Склади")

    def __str__(self):
        return self.name


# ==============================================================================
# 4. КАТАЛОГ ТОВАРІВ
# ==============================================================================

class Product(models.Model):
    code = models.CharField(_("Код товару"), max_length=30, unique=True, db_index=True)
    name_ua = models.TextField(_("Назва (UA)"), blank=True, null=True)
    catalog_number = models.TextField(_("Каталогний номер"), blank=True, null=True)
    category = models.TextField(_("Категорія"), blank=True, null=True)
    is_package = models.BooleanField(_("Це фасування"), default=False)
    is_sticker = models.BooleanField(_("Це наклейка"), default=False)
    info = models.TextField(_("Інформація/Опис"), blank=True, null=True)
    url = models.TextField(_("Посилання на сайт"), blank=True, null=True)
    tiktok_url = models.CharField(_("TikTok URL"), max_length=500, blank=True, null=True)
    instagram_url = models.CharField(_("Instagram URL"), max_length=500, blank=True, null=True)

    class Meta:
        db_table = "products"
        verbose_name = _("Товар")
        verbose_name_plural = _("Товари")

    def __str__(self):
        return f"[{self.code}] {self.name_ua or 'Без назви'}"


class ProductPhoto(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
                                related_name="photos", verbose_name=_("Товар"))
    photo_name = models.CharField(_("Назва фото"), max_length=255)
    file_path = models.TextField(_("Шлях до файлу"))
    tg_file_id = models.TextField(_("Telegram File ID"), blank=True, null=True)
    display_order = models.IntegerField(_("Порядок відображення"), default=0)

    class Meta:
        db_table = "product_photos"
        verbose_name = _("Фото товару")
        verbose_name_plural = _("Фото товарів")

    def __str__(self):
        return f"{self.photo_name} (Товар: {self.product_id})"


class ProductStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
                                related_name="stocks", verbose_name=_("Товар"))
    location = models.ForeignKey(Location, on_delete=models.CASCADE, db_column="location_id",
                                 verbose_name=_("Локація"))
    price = models.DecimalField(_("Ціна"), max_digits=10, decimal_places=2, default=0.0)
    balance = models.DecimalField(_("Залишок"), max_digits=10, decimal_places=2, default=0.0)
    storage_address = models.CharField(_("Адреса зберігання (комірка)"), max_length=50, blank=True, null=True)
    is_active = models.BooleanField(_("Активний"), default=True)

    class Meta:
        db_table = "product_stocks"
        unique_together = ('product', 'location')
        verbose_name = _("Залишок/Ціна товару")
        verbose_name_plural = _("Залишки та ціни")


class ProductComponent(models.Model):
    parent_code = models.ForeignKey(Product, on_delete=models.CASCADE, to_field="code", db_column="parent_code",
                                    related_name="components", verbose_name=_("Основний товар"))
    component_code = models.CharField(_("Код компонента"), max_length=30)
    quantity = models.DecimalField(_("Кількість"), max_digits=10, decimal_places=2, default=1.0)
    is_boxing = models.BooleanField(_("Упаковка"), default=False)
    is_sticker = models.BooleanField(_("Наклейка"), default=False)

    class Meta:
        db_table = "product_components"
        verbose_name = _("Компонент комплекту")
        verbose_name_plural = _("Комплектуючі")


class ProductAnalogue(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
                                related_name="analogues", verbose_name=_("Основний товар"))
    analogue_code = models.CharField(_("Код аналога"), max_length=30, db_index=True)

    class Meta:
        db_table = "product_analogues"
        unique_together = ('product', 'analogue_code')
        verbose_name = _("Аналог товару")
        verbose_name_plural = _("Аналоги товарів")


# ==============================================================================
# 5. ВІДГУКИ ТА БАЛИ
# ==============================================================================

class Review(models.Model):
    review_type = models.CharField(_("Тип відгуку"), max_length=20, choices=ReviewType.choices)
    author = models.ForeignKey(User, on_delete=models.CASCADE, db_column="author_id",
                               related_name="user_reviews", verbose_name=_("Автор"))
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column="target_user_id",
                                    related_name="received_reviews", verbose_name=_("Отримувач відгуку"))
    target_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                       to_field="code", db_column="target_product_code",
                                       related_name="product_reviews", verbose_name=_("Товар"))

    rating = models.IntegerField(_("Оцінка (1-5)"))
    comment = models.TextField(_("Коментар"))
    is_requested = models.BooleanField(_("Запитувався"), default=False)
    requested_at = models.DateTimeField(_("Дата запиту"), blank=True, null=True)
    created_at = models.DateTimeField(_("Дата створення"), auto_now_add=True)

    class Meta:
        db_table = "reviews"
        verbose_name = _("Відгук")
        verbose_name_plural = _("Відгуки")


class PointTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id",
                             related_name="point_transactions", verbose_name=_("Користувач"))
    amount = models.DecimalField(_("Сума балів"), max_digits=10, decimal_places=2)
    description = models.CharField(_("Опис транзакції"), max_length=255)
    created_at = models.DateTimeField(_("Дата"), auto_now_add=True)

    class Meta:
        db_table = "point_transactions"
        verbose_name = _("Транзакція балів")
        verbose_name_plural = _("Транзакції балів")


# ==============================================================================
# 6. ЗАМОВЛЕННЯ ТА КОШИК
# ==============================================================================

class Order(models.Model):
    order_number = models.CharField(_("Номер замовлення"), max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id",
                             related_name="orders", verbose_name=_("Клієнт"))
    status = models.CharField(_("Статус"), max_length=20, choices=OrderStatus.choices, default=OrderStatus.NEW)
    delivery_type = models.IntegerField(_("Тип доставки"), default=1)
    address = models.ForeignKey(DeliveryAddress, on_delete=models.SET_NULL, null=True, blank=True,
                                db_column="address_id", verbose_name=_("Адреса"))

    total_amount = models.DecimalField(_("Загальна сума"), max_digits=12, decimal_places=2, default=0.0)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column="manager_id",
                                related_name="managed_orders", verbose_name=_("Менеджер"))
    manager_comment = models.TextField(_("Коментар менеджера"), blank=True, null=True)

    created_at = models.DateTimeField(_("Створено"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Оновлено"), auto_now=True)

    class Meta:
        db_table = "orders"
        verbose_name = _("Замовлення")
        verbose_name_plural = _("Замовлення")

    def __str__(self):
        return f"Замовлення №{self.order_number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, db_column="order_id",
                              related_name="items", verbose_name=_("Замовлення"))
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, to_field="code", db_column="product_code",
                                related_name="order_entries", verbose_name=_("Товар"))
    quantity = models.DecimalField(_("Кількість"), max_digits=10, decimal_places=2)

    price_base = models.DecimalField(_("Базова ціна"), max_digits=10, decimal_places=2)
    price_client = models.DecimalField(_("Ціна клієнта"), max_digits=10, decimal_places=2)
    price_manager = models.DecimalField(_("Ціна менеджера"), max_digits=10, decimal_places=2, blank=True, null=True)

    status = models.CharField(_("Статус позиції"), max_length=20, choices=ItemStatus.choices, default=ItemStatus.ACTIVE)
    manager_note = models.TextField(_("Примітка менеджера"), blank=True, null=True)
    is_user_notified = models.BooleanField(_("Клієнта сповіщено"), default=False)

    class Meta:
        db_table = "order_items"
        verbose_name = _("Позиція замовлення")
        verbose_name_plural = _("Позиції замовлення")


# ==============================================================================
# 7. НОВИНИ ТА АКЦІЇ
# ==============================================================================

class ProductNews(models.Model):
    title = models.CharField(_("Заголовок"), max_length=255)
    content = models.TextField(_("Контент/Опис"))
    photo_id = models.CharField(_("Photo File ID"), max_length=255, blank=True, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                to_field="code", db_column="product_code",
                                related_name="related_news", verbose_name=_("Прив'язаний товар"))

    views_count = models.IntegerField(_("Перегляди"), default=0)
    is_published = models.BooleanField(_("Опубліковано"), default=True)

    created_at = models.DateTimeField(_("Створено"), auto_now_add=True)
    published_at = models.DateTimeField(_("Дата публікації"), auto_now_add=True)

    class Meta:
        db_table = "product_news"
        verbose_name = _("Новина товару")
        verbose_name_plural = _("Новини товарів")

    def __str__(self):
        return self.title


class Promotion(models.Model):
    title = models.CharField(_("Заголовок акції"), max_length=100)
    description = models.TextField(_("Опис акції"))
    image_id = models.CharField(_("Image File ID"), max_length=255, blank=True, null=True)
    link_url = models.CharField(_("Посилання"), max_length=255, blank=True, null=True)
    promo_type = models.CharField(_("Тип акції"), max_length=20, default="link")
    bonus_points = models.IntegerField(_("Бонусні бали"), default=0)
    is_active = models.BooleanField(_("Активна"), default=True)
    start_date = models.DateTimeField(_("Дата початку"), auto_now_add=True)
    end_date = models.DateTimeField(_("Дата закінчення"), blank=True, null=True)

    target_roles = models.ManyToManyField(Role, through='PromoRole', related_name='promotions',
                                          verbose_name=_("Цільові ролі"))

    class Meta:
        db_table = "promotions"
        verbose_name = _("Акція")
        verbose_name_plural = _("Акції")

    def __str__(self):
        return self.title


class PromoRole(models.Model):
    promo = models.ForeignKey(Promotion, on_delete=models.CASCADE, db_column="promo_id")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id")

    class Meta:
        db_table = "promo_roles"
        unique_together = ('promo', 'role')


class PromotionItem(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, db_column="promo_id",
                                  related_name="items", verbose_name=_("Акція"))
    product = models.ForeignKey(Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
                                verbose_name=_("Товар"))
    discount_price = models.DecimalField(_("Акційна ціна"), max_digits=10, decimal_places=2)
    min_quantity = models.IntegerField(_("Мін. кількість"), default=1)
    priority = models.IntegerField(_("Пріоритет"), default=0)

    class Meta:
        db_table = "promotion_items"
        verbose_name = _("Товар в акції")
        verbose_name_plural = _("Товари в акціях")


class UserPromoLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", verbose_name=_("Користувач"))
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, db_column="promo_id",
                                  related_name="user_logs", verbose_name=_("Акція"))
    received_at = models.DateTimeField(_("Дата отримання"), auto_now_add=True)

    class Meta:
        db_table = "user_promo_logs"
        verbose_name = _("Лог використання акції")
        verbose_name_plural = _("Логи використання акцій")
