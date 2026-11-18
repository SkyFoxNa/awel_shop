# shop/models.py
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ==============================================================================
# 1. ЕНУМЕРАТОРИ (Списки статусів та типів)
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


class CounterpartyType(models.TextChoices):
    CUSTOMER = "customer", _("Покупець")
    SUPPLIER = "supplier", _("Постачальник")
    INTERNAL_STOCK = "internal_stock", _("Внутрішній склад (Поповнення)")


class IncomingOrderStatus(models.TextChoices):
    DRAFT = "draft", _("Чернетка")
    PROCESSED = "processed", _("Проведено (Оприбутковано)")
    CANCELLED = "cancelled", _("Скасовано")


class OutgoingInvoiceStatus(models.TextChoices):
    NEW = "new", _("Нова (Очікує)")
    PICKING = "picking", _("На збірці у комірника")
    WAITING_PACKAGING = "waiting_packaging", _("Очікує пакування")
    PACKED_READY = "packed_ready", _("Зібрана (Готова до відправки)")
    SHIPPED_CLOSED = "shipped_closed", _("Закрита та відвантажена")
    MERGED = "merged", _("Об'єднана з іншою накладною")
    CANCELLED = "cancelled", _("Скасована")


class ContainerType(models.TextChoices):
    BOX = "box", _("Коробка")
    BAG = "bag", _("Мішок")
    PALLET = "pallet", _("Палета")
    OTHER = "other", _("Інше місце")


class ShipmentPackagingMode(models.TextChoices):
    SEPARATE_PLACES = "separate_places", _("Окремими місцями (коробки / мішки)")
    SINGLE_PALLET = "single_pallet", _("Все спаковано на одну палету")
    MULTIPLE_PALLETS = "multiple_pallets", _("Спаковано на декілька палет")


class DeliveryMethod(models.TextChoices):
    NOVA_POSHTA = "nova_poshta", _("Нова Пошта")
    DELIVERY = "delivery", _("Делівері")
    SAT = "sat", _("САТ")
    SELF_PICKUP = "self_pickup", _("Самовивіз")
    OWN_TRANSPORT = "own_transport", _("Наш транспорт")
    OTHER = "other", _("Інше")


class PackagingOrderStatus(models.TextChoices):
    NEED_CREATED = "need_created", _("1. Потреба (Сформовано)")
    IN_PROGRESS = "in_progress", _("2. Взято в роботу")
    PACKED_HANDOVER = "packed_handover", _("3. Спаковано / Передано на склад")
    ACCEPTED_BY_STOCK = "accepted_by_stock", _("4. Отримано складом (Проведено)")
    CANCELLED = "cancelled", _("Скасовано")


class StockBalanceType(models.TextChoices):
    BULK = "bulk", _("Розсип")
    PACKAGED = "packaged", _("Спакований")


class MovementSourceType(models.TextChoices):
    INCOMING = "incoming", _("Прихідний ордер")
    OUTGOING = "outgoing", _("Видаткова накладна")
    PACKAGING = "packaging", _("Накладна на пакування")
    ADJUSTMENT = "adjustment", _("Корекція залишків")


# ==============================================================================
# 2. КОРИСТУВАЧІ ТА ДОСТУП
# ==============================================================================

class Role(models.Model):
    """Доступні ролі: client, manager, admin, owner, storekeeper, packer тощо"""
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

    referrer = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='referrals', verbose_name=_("Хто запросив")
    )
    referral_code = models.CharField(_("Реферальний код"), max_length=50, unique=True, null=True, blank=True)
    personal_manager = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_users', verbose_name=_("Персональний менеджер")
    )

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
        return f"{self.full_name_1c or self.user_name} ({self.user_id})"


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", verbose_name=_("Користувач"))
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id", verbose_name=_("Роль"))

    class Meta:
        db_table = "user_roles"
        unique_together = ('user', 'role')
        verbose_name = _("Зв'язок користувача і ролі")
        verbose_name_plural = _("Зв'язки користувачів і ролей")


# ==============================================================================
# 3. ЛОГІСТИКА, СКЛАДИ ТА КОНТРАГЕНТИ
# ==============================================================================

class DeliveryAddress(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id",
        related_name="delivery_addresses", verbose_name=_("Користувач")
    )
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


class PackagingType(models.Model):
    """Довідник стандартів пакування (напр.: Фірмова коробка AWEL, Зіп-пакет, Без наліпок, Розсипом)"""
    name = models.CharField(_("Назва типу пакування"), max_length=100, unique=True)
    description = models.TextField(_("Опис / Інструкція для пакувальника"), blank=True, null=True)

    class Meta:
        db_table = "packaging_types"
        verbose_name = _("Тип пакування")
        verbose_name_plural = _("Типи пакування")

    def __str__(self):
        return self.name


class Counterparty(models.Model):
    """
    Єдиний довідник контрагентів (заміна старої таблиці customers):
    - Покупці (CUSTOMER)
    - Постачальники (SUPPLIER)
    - Внутрішні склади для завдань на поповнення (INTERNAL_STOCK)
    """
    name = models.CharField(_("Назва контрагента / складу"), max_length=255, db_index=True)
    code = models.CharField(_("Код (1С / внутрішній)"), max_length=20, unique=True, db_index=True)
    counterparty_type = models.CharField(
        _("Тип контрагента"),
        max_length=20,
        choices=CounterpartyType.choices,
        default=CounterpartyType.CUSTOMER,
        db_index=True,
    )
    edrpou = models.CharField(_("ЄДРПОУ / ІПН"), max_length=20, blank=True, null=True)
    phone = models.CharField(_("Телефон"), max_length=100, blank=True, null=True)
    shipping_info = models.TextField(_("Дані для відправки (Перевізник, місто, відділення)"), blank=True, null=True)
    discount = models.DecimalField(_("Базова знижка %"), max_digits=5, decimal_places=2, default=0.0)

    packaging_type = models.ForeignKey(
        PackagingType, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Стандарт пакування")
    )
    packing_note = models.TextField(
        _("Примітка по пакуванню та збірці"),
        blank=True, null=True,
        help_text=_("Виводиться як підказка комірнику при збірці та пакувальнику при пакуванні")
    )
    note = models.TextField(_("Загальна примітка"), blank=True, null=True)

    # Прив'язка до фізичного складу (якщо counterparty_type == INTERNAL_STOCK)
    linked_location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="internal_counterparties",
        verbose_name=_("Прив'язаний склад (для поповнення)")
    )
    is_active = models.BooleanField(_("Активний"), default=True)

    class Meta:
        db_table = "counterparties"
        verbose_name = _("Контрагент")
        verbose_name_plural = _("Контрагенти")

    def __str__(self):
        prefix = "🏭 [СКЛАД] " if self.counterparty_type == CounterpartyType.INTERNAL_STOCK else ""
        return f"{prefix}{self.name} ({self.code})"


# ==============================================================================
# 4. КАТАЛОГ ТОВАРІВ ТА ЗАЛИШКИ
# ==============================================================================

class Product(models.Model):
    code = models.CharField(_("Код товару"), max_length=30, unique=True, db_index=True)
    name_ua = models.TextField(_("Назва (UA)"), blank=True, null=True)
    catalog_number = models.TextField(_("Каталогний номер"), blank=True, null=True)
    category = models.TextField(_("Категорія"), blank=True, null=True)
    weight = models.DecimalField(_("Вага одиниці (кг)"), max_digits=8, decimal_places=3, default=0.0)

    is_package = models.BooleanField(_("Це фасування / комплект"), default=False)
    is_sticker = models.BooleanField(_("Це наклейка"), default=False)
    printed_stickers_count = models.PositiveIntegerField(_("Надруковано наліпок (на полиці)"), default=0)
    is_boxing = models.BooleanField(_("Це тара"), default=False)

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
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        related_name="photos", verbose_name=_("Товар")
    )
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
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        related_name="stocks", verbose_name=_("Товар")
    )
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, db_column="location_id",
        verbose_name=_("Локація")
    )
    price = models.DecimalField(_("Ціна"), max_digits=10, decimal_places=2, default=0.0)
    balance = models.DecimalField(_("Загальний залишок"), max_digits=10, decimal_places=2, default=0.0)
    packaged_balance = models.DecimalField(_("Спакований залишок"), max_digits=10, decimal_places=2, default=0.0)

    # Пороги мінімальних залишків для вітрини дефіциту та автоформування пакування
    min_balance = models.DecimalField(_("Мін. загальний залишок"), max_digits=10, decimal_places=2, default=0.0)
    min_packaged_balance = models.DecimalField(_("Мін. спакований залишок"), max_digits=10, decimal_places=2, default=0.0)

    storage_address = models.CharField(_("Адреса зберігання (комірка)"), max_length=50, blank=True, null=True)
    is_active = models.BooleanField(_("Активний"), default=True)

    class Meta:
        db_table = "product_stocks"
        unique_together = ('product', 'location')
        verbose_name = _("Залишок/Ціна товару")
        verbose_name_plural = _("Залишки та ціни")

    def __str__(self):
        return f"{self.product_id} @ {self.location.name}: заг. {self.balance} / спак. {self.packaged_balance}"

    @property
    def bulk_balance(self) -> Decimal:
        """Залишок розсипом = Загальний залишок - Спакований залишок"""
        return max(Decimal("0.00"), (self.balance or Decimal("0.00")) - (self.packaged_balance or Decimal("0.00")))

    def save(self, *args, **kwargs):
        if self.balance < self.packaged_balance:
            self.balance = self.packaged_balance
        super().save(*args, **kwargs)


class ProductComponent(models.Model):
    parent_code = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="parent_code",
        related_name="components", verbose_name=_("Основний товар")
    )
    component_code = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="component_code",
        related_name="used_as_components", verbose_name=_("Компонент")
    )
    quantity = models.DecimalField(_("Кількість"), max_digits=10, decimal_places=2, default=1.0)
    is_boxing = models.BooleanField(_("Упаковка (Тара)"), default=False)
    is_sticker = models.BooleanField(_("Наклейка"), default=False)

    class Meta:
        db_table = "product_components"
        verbose_name = _("Компонент комплекту")
        verbose_name_plural = _("Комплектуючі")

    def __str__(self):
        return f"Компонент {self.component_code_id} (Кількість: {self.quantity})"


class ProductAnalogue(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        related_name="analogues", verbose_name=_("Основний товар")
    )
    analogue_code = models.CharField(_("Код аналога"), max_length=30, db_index=True)

    class Meta:
        db_table = "product_analogues"
        unique_together = ('product', 'analogue_code')
        verbose_name = _("Аналог товару")
        verbose_name_plural = _("Аналоги товарів")


class CustomerProductRule(models.Model):
    """
    Матриця індивідуальних вимог по зв'язці Покупець + Товар.
    Слугує інформаційним попередженням при збірці та пакуванні.
    """
    customer = models.ForeignKey(
        Counterparty, on_delete=models.CASCADE,
        related_name="product_rules", verbose_name=_("Покупець")
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        related_name="customer_rules", verbose_name=_("Товар")
    )
    packaging_type = models.ForeignKey(
        PackagingType, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Вимога до пакування")
    )
    note = models.CharField(_("Коментар / Попередження"), max_length=255, blank=True, null=True)

    class Meta:
        db_table = "customer_product_rules"
        unique_together = ('customer', 'product')
        verbose_name = _("Правило пакування (Клієнт–Товар)")
        verbose_name_plural = _("Правила пакування (Клієнт–Товар)")

    def __str__(self):
        return f"{self.customer.name} -> {self.product_id}: {self.packaging_type or self.note}"


# ==============================================================================
# 5. СКЛАДСЬКІ ДОКУМЕНТИ ТА ОБЛІК РУХУ
# ==============================================================================

class StockMovement(models.Model):
    """Журнал історії всіх змін залишків (розсип та спакований)"""
    created_at = models.DateTimeField(_("Дата та час"), auto_now_add=True, db_index=True)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        related_name="movements", verbose_name=_("Товар")
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name=_("Склад"))
    source_type = models.CharField(_("Тип документа"), max_length=20, choices=MovementSourceType.choices)
    document_number = models.CharField(_("Номер документа"), max_length=100, blank=True, null=True)

    bulk_delta = models.DecimalField(_("Зміна розсипу (+/-)"), max_digits=10, decimal_places=2, default=0.0)
    packaged_delta = models.DecimalField(_("Зміна спакованого (+/-)"), max_digits=10, decimal_places=2, default=0.0)

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Користувач"))
    comment = models.CharField(_("Коментар"), max_length=255, blank=True, null=True)

    class Meta:
        db_table = "stock_movements"
        ordering = ("-created_at",)
        verbose_name = _("Рух товару")
        verbose_name_plural = _("Журнал руху товарів")

    def __str__(self):
        return f"{self.product_id} ({self.source_type} {self.document_number}): розсип {self.bulk_delta:+} / спак {self.packaged_delta:+}"


class StockAdjustment(models.Model):
    """
    Корекція / Інвентаризація залишків на складі.
    Зберігає хто, коли, який товар і який тип залишку (розсип чи спакований) відкоригував.
    Після збереження автоматично оновлює ProductStock та створює запис у StockMovement.
    """
    created_at = models.DateTimeField(_("Дата корекції"), auto_now_add=True)
    adjusted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name="stock_adjustments", verbose_name=_("Хто коректував")
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        related_name="adjustments", verbose_name=_("Товар")
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, verbose_name=_("Склад"))
    balance_type = models.CharField(
        _("Тип залишку"), max_length=15,
        choices=StockBalanceType.choices, default=StockBalanceType.BULK
    )

    old_quantity = models.DecimalField(_("Було в базі"), max_digits=10, decimal_places=2, default=0.0)
    new_quantity = models.DecimalField(_("Фактична кількість (Нове)"), max_digits=10, decimal_places=2)
    reason = models.CharField(_("Причина корекції"), max_length=255, blank=True, null=True)
    is_applied = models.BooleanField(_("Застосовано до залишків"), default=False, editable=False)

    class Meta:
        db_table = "stock_adjustments"
        ordering = ("-created_at",)
        verbose_name = _("Корекція залишку")
        verbose_name_plural = _("Корекція залишків")

    def __str__(self):
        return f"Корекція {self.product_id} ({self.get_balance_type_display()}) -> {self.new_quantity}"

    @transaction.atomic
    def apply_adjustment(self):
        """Застосовує фактичну кількість до ProductStock одноразово при першому збереженні"""
        if self.is_applied:
            return

        stock, _ = ProductStock.objects.select_for_update().get_or_create(
            product=self.product,
            location=self.location,
            defaults={"balance": Decimal("0.00"), "packaged_balance": Decimal("0.00")}
        )

        if self.balance_type == StockBalanceType.PACKAGED:
            self.old_quantity = stock.packaged_balance
            delta = self.new_quantity - self.old_quantity
            stock.packaged_balance = self.new_quantity
            stock.balance = max(Decimal("0.00"), stock.balance + delta)
            stock.save()

            StockMovement.objects.create(
                product=self.product,
                location=self.location,
                source_type=MovementSourceType.ADJUSTMENT,
                document_number=f"ADJ-{self.id or ''}",
                packaged_delta=delta,
                user=self.adjusted_by,
                comment=self.reason or "Корекція спакованого залишку",
            )
        else:
            self.old_quantity = stock.bulk_balance
            delta = self.new_quantity - self.old_quantity
            stock.balance = max(stock.packaged_balance, stock.balance + delta)
            stock.save()

            StockMovement.objects.create(
                product=self.product,
                location=self.location,
                source_type=MovementSourceType.ADJUSTMENT,
                document_number=f"ADJ-{self.id or ''}",
                bulk_delta=delta,
                user=self.adjusted_by,
                comment=self.reason or "Корекція розсипу",
            )

        self.is_applied = True

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.is_applied:
            self.apply_adjustment()
            super().save(update_fields=["old_quantity", "is_applied"])


# --- 5.1 ПРИХІДНИЙ ОРДЕР ---

class IncomingOrder(models.Model):
    """Прихідний ордер (створюється вручну або завантажується з пошти)"""
    order_number = models.CharField(_("Номер прихідного ордера"), max_length=50, unique=True, db_index=True)
    order_date = models.DateField(_("Дата документа"), default=timezone.now)
    supplier = models.ForeignKey(
        Counterparty, on_delete=models.RESTRICT,
        limit_choices_to={"counterparty_type": CounterpartyType.SUPPLIER},
        related_name="incoming_orders", verbose_name=_("Постачальник")
    )
    location = models.ForeignKey(Location, on_delete=models.RESTRICT, verbose_name=_("Склад приймання"))
    status = models.CharField(
        _("Статус"), max_length=20,
        choices=IncomingOrderStatus.choices, default=IncomingOrderStatus.DRAFT
    )

    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="accepted_incoming_orders", verbose_name=_("Хто прийняв")
    )
    is_from_email = models.BooleanField(_("Завантажено з пошти"), default=False)
    is_manager_notified = models.BooleanField(_("Менеджера сповіщено"), default=False)
    note = models.TextField(_("Примітка"), blank=True, null=True)

    created_at = models.DateTimeField(_("Створено"), auto_now_add=True)
    processed_at = models.DateTimeField(_("Дата проведення"), blank=True, null=True)

    class Meta:
        db_table = "incoming_orders"
        ordering = ("-order_date", "-id")
        verbose_name = _("Прихідний ордер")
        verbose_name_plural = _("Прихідні ордери")

    def __str__(self):
        return f"Прихід №{self.order_number} від {self.order_date} ({self.supplier.name})"


class IncomingOrderItem(models.Model):
    incoming_order = models.ForeignKey(
        IncomingOrder, on_delete=models.CASCADE,
        related_name="items", verbose_name=_("Прихідний ордер")
    )
    product = models.ForeignKey(
        Product, on_delete=models.RESTRICT, to_field="code", db_column="product_code",
        verbose_name=_("Товар")
    )
    quantity = models.DecimalField(_("Кількість"), max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(_("Закупівельна ціна"), max_digits=10, decimal_places=2, default=0.0)
    storage_cell = models.CharField(_("Комірка розміщення"), max_length=50, blank=True, null=True)

    class Meta:
        db_table = "incoming_order_items"
        unique_together = ('incoming_order', 'product')
        verbose_name = _("Позиція приходу")
        verbose_name_plural = _("Позиції приходу")


# --- 5.2 ВИДАТКОВА НАКЛАДНА ТА ЛИСТ ПІДБОРУ КОМІРНИКА ---

class OutgoingInvoice(models.Model):
    """
    Видаткова накладна:
    - Підтримує злиття 2-х файлів з пошти (ціни + комірки/вага)
    - Підтримує злиття ручної чернетки з поштовим файлом
    - Підтримує розділення (спліт) на кілька накладних
    - Веде паралельну збірку, пакування місць і відправку ТТН
    """
    invoice_number = models.CharField(_("Номер видаткової накладної"), max_length=50, unique=True, db_index=True)
    invoice_date = models.DateField(_("Дата накладної"), default=timezone.now)
    customer = models.ForeignKey(
        Counterparty, on_delete=models.RESTRICT,
        related_name="outgoing_invoices", verbose_name=_("Покупець / Отримувач")
    )
    location = models.ForeignKey(Location, on_delete=models.RESTRICT, verbose_name=_("Склад відвантаження"))
    status = models.CharField(
        _("Статус накладної"), max_length=25,
        choices=OutgoingInvoiceStatus.choices, default=OutgoingInvoiceStatus.NEW
    )

    # Прапорці джерел завантаження з пошти та ручних чернеток
    is_manual_draft = models.BooleanField(_("Ручна чернетка (очікує файл з пошти)"), default=False)
    has_client_price_file = models.BooleanField(_("Завантажено файл з цінами"), default=False)
    has_warehouse_cell_file = models.BooleanField(_("Завантажено файл з комірками"), default=False)

    # Зв'язок при розділенні накладних (Спліт)
    parent_invoice = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="split_children", verbose_name=_("Створено розділенням з")
    )

    # Логістика та відправка (ТТН)
    shipment_packaging_mode = models.CharField(
        _("Формат тари відвантаження"), max_length=25,
        choices=ShipmentPackagingMode.choices, default=ShipmentPackagingMode.SEPARATE_PLACES
    )
    places_count = models.PositiveIntegerField(_("Кількість місць (коробок/мішків/палет)"), default=1)
    delivery_method = models.CharField(
        _("Спосіб доставки"), max_length=25,
        choices=DeliveryMethod.choices, default=DeliveryMethod.NOVA_POSHTA
    )
    delivery_destination = models.TextField(_("Куди відвантажуємо (Адреса / Відділення)"), blank=True, null=True)
    ttn_number = models.CharField(_("Номер ТТН"), max_length=100, blank=True, null=True, db_index=True)
    ttn_photo = models.ImageField(_("Фото ТТН"), upload_to="ttn_photos/%Y/%m/", blank=True, null=True)
    ttn_tg_file_id = models.TextField(_("Telegram File ID фото ТТН"), blank=True, null=True)

    # Відповідальні та сповіщення
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="managed_outgoing_invoices", verbose_name=_("Менеджер")
    )
    is_manager_notified = models.BooleanField(_("Менеджера сповіщено про обробку"), default=False)
    note = models.TextField(_("Примітка до накладної"), blank=True, null=True)

    created_at = models.DateTimeField(_("Створено"), auto_now_add=True)
    closed_at = models.DateTimeField(_("Дата закриття та відвантаження"), blank=True, null=True)

    class Meta:
        db_table = "outgoing_invoices"
        ordering = ("-invoice_date", "-id")
        verbose_name = _("Видаткова накладна")
        verbose_name_plural = _("Видаткові накладні")

    def __str__(self):
        return f"Видаткова №{self.invoice_number} від {self.invoice_date} — {self.customer.name}"

    @property
    def total_sum(self) -> Decimal:
        return sum((item.total_price for item in self.items.all()), Decimal("0.00"))


class OutgoingInvoiceItem(models.Model):
    """
    Рядок видаткової накладної:
    - Містить дані для збірки комірником (розсип + спаковано, номер місця/мішка, хто зібрав)
    - Містить фінансові дані для накладної клієнта (ціна, видана кількість, сума)
    """
    invoice = models.ForeignKey(
        OutgoingInvoice, on_delete=models.CASCADE,
        related_name="items", verbose_name=_("Видаткова накладна")
    )
    item_number = models.PositiveIntegerField(_("№ п/п"), default=1)
    product = models.ForeignKey(
        Product, on_delete=models.RESTRICT, to_field="code", db_column="product_code",
        verbose_name=_("Товар")
    )

    # Кількості збірки та списання
    quantity_ordered = models.DecimalField(_("Потрібно (Замовлено)"), max_digits=10, decimal_places=2, default=0.0)
    deduct_from_packaged = models.DecimalField(_("Взято спакованого (зі складу)"), max_digits=10, decimal_places=2, default=0.0)
    added_from_new_packaging = models.DecimalField(_("Додано нового з пакування"), max_digits=10, decimal_places=2, default=0.0)
    deduct_from_bulk = models.DecimalField(_("Взято розсипом"), max_digits=10, decimal_places=2, default=0.0)
    quantity_issued = models.DecimalField(_("Видано (у накладну клієнта)"), max_digits=10, decimal_places=2, default=0.0)

    # Інформація для комірника та пошуку в місцях при відмові
    storage_cell = models.CharField(_("Комірка зберігання"), max_length=50, blank=True, null=True)
    package_container_type = models.CharField(
        _("Тип тари відвантаження"), max_length=15,
        choices=ContainerType.choices, default=ContainerType.BOX
    )
    package_number = models.CharField(
        _("№ місця (коробки/мішка)"), max_length=50, blank=True, null=True,
        help_text=_("Напр.: Мішок №1 або Коробка №3 — для швидкого пошуку при відмові")
    )
    picked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="picked_invoice_items", verbose_name=_("Хто зібрав (Комірник)")
    )

    # Фінансові поля та вага
    unit = models.CharField(_("Од. вим."), max_length=20, default="шт.")
    price = models.DecimalField(_("Ціна без ПДВ"), max_digits=10, decimal_places=2, default=0.0)
    weight = models.DecimalField(_("Вага рядка (кг)"), max_digits=8, decimal_places=3, default=0.0)

    class Meta:
        db_table = "outgoing_invoice_items"
        unique_together = ('invoice', 'product')
        ordering = ("item_number", "id")
        verbose_name = _("Позиція видаткової накладної")
        verbose_name_plural = _("Позиції видаткової накладної")

    @property
    def total_price(self) -> Decimal:
        return (self.quantity_issued or Decimal("0.00")) * (self.price or Decimal("0.00"))

    def save(self, *args, **kwargs):
        # Автоматично підраховуємо сумарно видану кількість із усіх джерел, якщо не задано вручну
        calculated_issued = (
            (self.deduct_from_packaged or Decimal("0.00")) +
            (self.added_from_new_packaging or Decimal("0.00")) +
            (self.deduct_from_bulk or Decimal("0.00"))
        )
        if calculated_issued > 0:
            self.quantity_issued = calculated_issued
        super().save(*args, **kwargs)


# --- 5.3 НАКЛАДНА НА ПАКУВАННЯ (4 ЕТАПИ + ТАРА + НАЛІПКИ) ---

class PackagingOrder(models.Model):
    """
    Накладна на пакування (Пакувальний лист):
    Етапи:
    1. Потреба (загальна кількість під клієнтів та/або на склад)
    2. Взято в роботу (пакувальник)
    3. Виконано пакування та передано на склад (+ сповіщення комірнику)
    4. Отримано складом (списання розсипу/тари/наліпок і зарахування в спакований залишок)
    """
    order_number = models.CharField(_("Номер пакувального листа"), max_length=50, unique=True, db_index=True)
    created_at = models.DateTimeField(_("Дата створення"), auto_now_add=True)
    location = models.ForeignKey(Location, on_delete=models.RESTRICT, verbose_name=_("Склад виконання"))
    status = models.CharField(
        _("Етап пакування"), max_length=25,
        choices=PackagingOrderStatus.choices, default=PackagingOrderStatus.NEED_CREATED
    )

    # Відповідальні на етапах
    packer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="packed_orders", verbose_name=_("2. Пакувальник (Взяв у роботу)")
    )
    started_at = models.DateTimeField(_("Час початку пакування"), blank=True, null=True)
    packed_at = models.DateTimeField(_("3. Час передачі на склад"), blank=True, null=True)

    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="accepted_packaging_orders", verbose_name=_("4. Хто прийняв на склад (Комірник)")
    )
    accepted_at = models.DateTimeField(_("Час приймання складом"), blank=True, null=True)

    is_storekeeper_notified = models.BooleanField(_("Комірника сповіщено про готовність"), default=False)
    note = models.TextField(_("Примітка для пакувальника"), blank=True, null=True)

    class Meta:
        db_table = "packaging_orders"
        ordering = ("-created_at",)
        verbose_name = _("Накладна на пакування")
        verbose_name_plural = _("Накладні на пакування")

    def __str__(self):
        return f"Пакування №{self.order_number} ({self.get_status_display()})"


class PackagingOrderItem(models.Model):
    """
    Позиція завдання на пакування з деталізацією, під якого саме замовника (чи склад) вона пакується.
    """
    packaging_order = models.ForeignKey(
        PackagingOrder, on_delete=models.CASCADE,
        related_name="items", verbose_name=_("Накладна на пакування")
    )
    product = models.ForeignKey(
        Product, on_delete=models.RESTRICT, to_field="code", db_column="product_code",
        verbose_name=_("Товар для пакування")
    )
    customer = models.ForeignKey(
        Counterparty, on_delete=models.RESTRICT,
        related_name="packaging_items", verbose_name=_("Замовник (Покупець або Склад)")
    )
    source_invoice = models.ForeignKey(
        OutgoingInvoice, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="packaging_tasks", verbose_name=_("Видаткова накладна (якщо під замовлення)")
    )

    quantity_planned = models.DecimalField(_("1. Потрібно спакувати"), max_digits=10, decimal_places=2)
    quantity_packed = models.DecimalField(_("3. Фактично спаковано"), max_digits=10, decimal_places=2, default=0.0)
    quantity_accepted = models.DecimalField(_("4. Прийнято складом"), max_digits=10, decimal_places=2, default=0.0)

    # Можливість обрати нестандартну тару під конкретного клієнта, якщо штатної не вистачило
    custom_boxing = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        to_field="code", db_column="custom_boxing_code",
        limit_choices_to={"is_boxing": True},
        related_name="used_as_custom_boxing",
        verbose_name=_("Фактична тара (якщо замінено під клієнта)")
    )
    packing_hint = models.CharField(_("Підказка по пакуванню клієнта"), max_length=255, blank=True, null=True)

    class Meta:
        db_table = "packaging_order_items"
        verbose_name = _("Позиція пакування")
        verbose_name_plural = _("Позиції пакування")


class PackagingOrderMaterial(models.Model):
    """
    Зведена таблиця списання комплектуючих, тари та наліпок під накладну на пакування.
    Дозволяє пакувальнику скоригувати фактичну кількість або додати іншу тару для списання.
    """
    packaging_order = models.ForeignKey(
        PackagingOrder, on_delete=models.CASCADE,
        related_name="materials", verbose_name=_("Накладна на пакування")
    )
    material = models.ForeignKey(
        Product, on_delete=models.RESTRICT, to_field="code", db_column="material_code",
        verbose_name=_("Компонент / Тара / Наліпка")
    )
    for_customer = models.ForeignKey(
        Counterparty, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Під замовника (якщо індивідуальна заміна)")
    )
    planned_quantity = models.DecimalField(_("Потрібно за нормою комплекту"), max_digits=10, decimal_places=2, default=0.0)
    actual_quantity = models.DecimalField(_("Фактично використано (До списання)"), max_digits=10, decimal_places=2, default=0.0)

    class Meta:
        db_table = "packaging_order_materials"
        verbose_name = _("Витрачений матеріал / тара")
        verbose_name_plural = _("Витрачені матеріали, комплектуючі та тара")


class PackagingStickerLog(models.Model):
    """
    Облік наліпок під час пакування:
    Скільки було надруковано до початку -> скільки додрукували -> скільки витратили -> скільки повернули на полицю.
    """
    packaging_order = models.ForeignKey(
        PackagingOrder, on_delete=models.CASCADE,
        related_name="sticker_logs", verbose_name=_("Накладна на пакування")
    )
    sticker = models.ForeignKey(
        Product, on_delete=models.RESTRICT, to_field="code", db_column="sticker_code",
        limit_choices_to={"is_sticker": True},
        verbose_name=_("Наліпка")
    )
    already_printed = models.PositiveIntegerField(_("Було в наявності (надрукованих)"), default=0)
    newly_printed = models.PositiveIntegerField(_("Надруковано додатково"), default=0)
    used_count = models.PositiveIntegerField(_("Використано на пакування"), default=0)
    spoiled_count = models.PositiveIntegerField(_("Зіпсовано (брак)"), default=0)
    remaining_returned = models.PositiveIntegerField(_("Залишок (покладено в залишки)"), default=0)

    class Meta:
        db_table = "packaging_sticker_logs"
        unique_together = ('packaging_order', 'sticker')
        verbose_name = _("Облік наліпок пакування")
        verbose_name_plural = _("Облік надрукованих наліпок")

    def save(self, *args, **kwargs):
        total_available = (self.already_printed or 0) + (self.newly_printed or 0)
        total_spent = (self.used_count or 0) + (self.spoiled_count or 0)
        self.remaining_returned = max(0, total_available - total_spent)
        super().save(*args, **kwargs)


# ==============================================================================
# 6. ВІДГУКИ ТА БАЛИ
# ==============================================================================

class Review(models.Model):
    review_type = models.CharField(_("Тип відгуку"), max_length=20, choices=ReviewType.choices)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="author_id",
        related_name="user_reviews", verbose_name=_("Автор")
    )
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_column="target_user_id",
        related_name="received_reviews", verbose_name=_("Отримувач відгуку")
    )
    target_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        to_field="code", db_column="target_product_code",
        related_name="product_reviews", verbose_name=_("Товар")
    )

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
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id",
        related_name="point_transactions", verbose_name=_("Користувач")
    )
    amount = models.DecimalField(_("Сума балів"), max_digits=10, decimal_places=2)
    description = models.CharField(_("Опис транзакції"), max_length=255)
    created_at = models.DateTimeField(_("Дата"), auto_now_add=True)

    class Meta:
        db_table = "point_transactions"
        verbose_name = _("Транзакція балів")
        verbose_name_plural = _("Транзакції балів")


# ==============================================================================
# 7. ЗАМОВЛЕННЯ ТА КОШИК (З БОТА)
# ==============================================================================

class Order(models.Model):
    order_number = models.CharField(_("Номер замовлення"), max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id",
        related_name="orders", verbose_name=_("Клієнт")
    )
    status = models.CharField(_("Статус"), max_length=20, choices=OrderStatus.choices, default=OrderStatus.NEW)
    delivery_type = models.IntegerField(_("Тип доставки"), default=1)
    address = models.ForeignKey(
        DeliveryAddress, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="address_id", verbose_name=_("Адреса")
    )

    total_amount = models.DecimalField(_("Загальна сума"), max_digits=12, decimal_places=2, default=0.0)
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, db_column="manager_id",
        related_name="managed_orders", verbose_name=_("Менеджер")
    )
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
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, db_column="order_id",
        related_name="items", verbose_name=_("Замовлення")
    )
    product = models.ForeignKey(
        Product, on_delete=models.RESTRICT, to_field="code", db_column="product_code",
        related_name="order_entries", verbose_name=_("Товар")
    )
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
# 8. НОВИНИ ТА АКЦІЇ
# ==============================================================================

class ProductNews(models.Model):
    title = models.CharField(_("Заголовок"), max_length=255)
    content = models.TextField(_("Контент/Опис"))
    photo_id = models.CharField(_("Photo File ID"), max_length=255, blank=True, null=True)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        to_field="code", db_column="product_code",
        related_name="related_news", verbose_name=_("Прив'язаний товар")
    )

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

    target_roles = models.ManyToManyField(
        Role, through='PromoRole', related_name='promotions',
        verbose_name=_("Цільові ролі")
    )

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
    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, db_column="promo_id",
        related_name="items", verbose_name=_("Акція")
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, to_field="code", db_column="product_code",
        verbose_name=_("Товар")
    )
    discount_price = models.DecimalField(_("Акційна ціна"), max_digits=10, decimal_places=2)
    min_quantity = models.IntegerField(_("Мін. кількість"), default=1)
    priority = models.IntegerField(_("Пріоритет"), default=0)

    class Meta:
        db_table = "promotion_items"
        verbose_name = _("Товар в акції")
        verbose_name_plural = _("Товари в акціях")


class UserPromoLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", verbose_name=_("Користувач"))
    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, db_column="promo_id",
        related_name="user_logs", verbose_name=_("Акція")
    )
    received_at = models.DateTimeField(_("Дата отримання"), auto_now_add=True)

    class Meta:
        db_table = "user_promo_logs"
        verbose_name = _("Лог використання акції")
        verbose_name_plural = _("Логи використання акцій")
