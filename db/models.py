from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    BigInteger, String, Integer, ForeignKey, DateTime, func,
    UniqueConstraint, Numeric, Boolean, Text, Table, Column
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum
import enum


from db.base import Base


# ==============================================================================
# 1. КОРИСТУВАЧІ ТА СИСТЕМА ДОСТУПУ
# ==============================================================================

# --- ТАБЛИЦЯ ЗВ'ЯЗКУ (Many-to-Many) ---
# Ця таблиця дозволяє одній акції належати декільком ролям одночасно
promo_roles = Table(
    "promo_roles",
    Base.metadata,
    Column("promo_id", Integer, ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

class Role(Base):
    """Доступні ролі: client, manager, admin, owner, pro_client"""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    # Зв'язок з користувачами
    user_links: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="role")

    # ОНОВЛЕНО: Тепер зв'язок через secondary таблицю
    promotions: Mapped[List["Promotion"]] = relationship(
        "Promotion",
        secondary=promo_roles,
        back_populates="target_roles"
    )


class User(Base):
    """Основна таблиця користувачів з логікою лояльності та адміністрування"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)  # Telegram ID

    # Профіль Telegram
    user_name: Mapped[str] = mapped_column(String(255))
    user_surname: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))  # @nickname

    # Реквізити для документів
    full_name_1c: Mapped[Optional[str]] = mapped_column(String(255))  # ПІБ для накладних
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))

    # Інтеграція з 1С 7.7
    one_c_id: Mapped[Optional[str]] = mapped_column(String(30))  # Код контрагента
    barcode: Mapped[Optional[str]] = mapped_column(String(50), unique=True)  # Штрихкод клієнта

    # Фінанси та Лояльність
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=3.0, server_default="3.0") # Початкова знижка 3%
    total_spent: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)  # Оборот за весь час
    balance_points: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)  # Наявні бонусні бали

    # Реферальна програма
    referrer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # Хто запросив
    referral_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)  # Власний код для посилання

    # Персоналізація сервісу
    personal_manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # Адміністрування
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # False - бан
    admin_notes: Mapped[Optional[str]] = mapped_column(Text)  # Службові замітки про клієнта
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)  # Заборона клієнту самому міняти дані

    # Статистика
    visit: Mapped[int] = mapped_column(default=1)  # Скільки разів запускав бота
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="user", cascade="all, delete-orphan",
                                                   lazy="selectin")
    delivery_addresses: Mapped[List["DeliveryAddress"]] = relationship("DeliveryAddress", back_populates="user",
                                                                       cascade="all, delete-orphan")
    reviews: Mapped[List["UserReview"]] = relationship("UserReview", back_populates="user",
                                                       foreign_keys="[UserReview.user_id]",
                                                       cascade="all, delete-orphan")
    point_transactions: Mapped[List["PointTransaction"]] = relationship("PointTransaction", back_populates="user",
                                                                        cascade="all, delete-orphan")


class UserRole(Base):
    """Проміжна таблиця для багатьох ролей (напр. адмін + менеджер)"""
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_links", lazy="selectin")

    __table_args__ = (UniqueConstraint("user_id", "role_id"),)


# ==============================================================================
# 2. ДОСТАВКА ТА ВІДГУКИ
# ==============================================================================

class DeliveryAddress(Base):
    """Книга адрес користувача (для себе та клієнтів)"""
    __tablename__ = "delivery_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    address_label: Mapped[str] = mapped_column(String(100))  # Напр. "Склад Запоріжжя"
    recipient_fio: Mapped[str] = mapped_column(String(255))  # ПІБ отримувача
    recipient_phone: Mapped[str] = mapped_column(String(50))  # Тел. отримувача
    delivery_details: Mapped[str] = mapped_column(Text)  # Повна адреса / Відділення НП
    delivery_type: Mapped[int] = mapped_column(Integer, default=1)  # 0-Самовивіз, 1-НП, 2-Інше
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # Чи пропонувати першою

    user: Mapped["User"] = relationship("User", back_populates="delivery_addresses")


class UserReview(Base):
    """Система репутації клієнта (відгуки від менеджерів)"""
    __tablename__ = "user_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))  # Про кого відгук
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))  # Хто написав (адмін)

    rating: Mapped[int] = mapped_column(Integer)  # Оцінка 1-5
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="reviews")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])


class PointTransaction(Base):
    """Журнал аудиту балів: звідки взялися і куди витрачені"""
    __tablename__ = "point_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    amount: Mapped[float] = mapped_column(Numeric(10, 2))  # Напр. +50.0 або -100.0
    description: Mapped[str] = mapped_column(String(255))  # Причина нарахування/списання
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="point_transactions")


# ==============================================================================
# 3. КАТАЛОГ ТОВАРІВ ТА СКЛАД (ЛОКАЦІЇ)
# ==============================================================================

class Location(Base):
    """Склади, магазини, торгові точки"""
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)  # Напр. "Склад Запоріжжя"


class Product(Base):
    """Майстер-картка товару"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # Артикул 1С
    name_ua: Mapped[Optional[str]] = mapped_column(Text)
    catalog_number: Mapped[Optional[str]] = mapped_column(Text)  # Заводський номер
    category: Mapped[Optional[str]] = mapped_column(Text)
    is_package: Mapped[bool] = mapped_column(Boolean, default=False)  # Чи є це комплект/набір

    # Медіа-ресурси
    url: Mapped[Optional[str]] = mapped_column(Text)  # Посилання на сайт
    tiktok_url: Mapped[Optional[str]] = mapped_column(String(500))
    instagram_url: Mapped[Optional[str]] = mapped_column(String(500))

    photos: Mapped[List["ProductPhoto"]] = relationship("ProductPhoto", back_populates="product",
                                                        cascade="all, delete-orphan", lazy="selectin")


class ProductPhoto(Base):
    """Зв'язок товару з фотографіями в Telegram"""
    __tablename__ = "product_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    photo_name: Mapped[str] = mapped_column(String(255))  # Ім'я файлу
    file_path: Mapped[str] = mapped_column(Text)  # Локальний шлях
    tg_file_id: Mapped[Optional[str]] = mapped_column(Text)  # cached file_id від Telegram
    display_order: Mapped[int] = mapped_column(Integer, default=0)  # Порядок відображення

    product: Mapped["Product"] = relationship("Product", back_populates="photos")


class ProductStock(Base):
    """Залишки та ціни у розрізі локацій та стану упаковки"""
    __tablename__ = "product_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))

    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)  # Ціна на цій локації
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)  # Кількість
    min_balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)  # Поріг для сповіщення
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Чи доступний для продажу тут
    storage_address: Mapped[Optional[str]] = mapped_column(String(50))  # Полиця/Ряд
    is_packed: Mapped[bool] = mapped_column(Boolean, default=False)  # Стан: False-розсип, True-пакет

    __table_args__ = (UniqueConstraint("product_code", "location_id", "is_packed", name="uq_product_location_packed"),)
    product: Mapped["Product"] = relationship("Product", backref="stocks")
    location: Mapped["Location"] = relationship("Location", lazy="joined")


# ==============================================================================
# 4. КОМПЛЕКТАЦІЯ ТА АНАЛОГИ
# ==============================================================================

class Package(Base):
    """Тара: пакети, коробки, стікери"""
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    info: Mapped[Optional[str]] = mapped_column(Text)  # Характеристики тари
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)  # Вартість тари
    is_sticker: Mapped[bool] = mapped_column(Boolean, default=False)  # Чи це наклейка

    stocks: Mapped[List["PackageStock"]] = relationship("PackageStock", back_populates="package")


class PackageStock(Base):
    """Залишки тари на складах"""
    __tablename__ = "package_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    storage_address: Mapped[Optional[str]] = mapped_column(String(50))

    package: Mapped["Package"] = relationship("Package", back_populates="stocks")
    __table_args__ = (UniqueConstraint("package_id", "location_id"),)


class ProductComponent(Base):
    """Специфікація наборів: що входить у складний товар"""
    __tablename__ = "product_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))  # Набір
    component_code: Mapped[str] = mapped_column(String(30))  # Що всередині
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1.0)  # Скільки штук
    package_id: Mapped[Optional[int]] = mapped_column(ForeignKey("packages.id"))  # Яке пакування треба для вузла
    is_sticker: Mapped[bool] = mapped_column(Boolean, default=False)  # Чи потрібен стікер


class ProductAnalogue(Base):
    """Таблиця взаємозамінності товарів"""
    __tablename__ = "product_analogues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    analogue_code: Mapped[str] = mapped_column(String(30), index=True)  # Код замінника

    __table_args__ = (UniqueConstraint("product_code", "analogue_code"),)


# ==============================================================================
# 5. АКЦІЇ
# ==============================================================================

class PromoType(enum.Enum):
    SIMPLE = "simple"  # Просто знижка на 1 шт
    QUANTITY = "quantity"  # Купи 5+ шт — отримай ціну X
    BUNDLE = "bundle"  # Купи Набір (Товар А + Товар Б)
    FLASH = "flash"  # Встигни до певного часу


class PromotionItem(Base):
    """Детальні умови для товарів всередині акції"""
    __tablename__ = "promotion_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="CASCADE"))
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))

    # Специфічні умови для цього товару в цій акції
    discount_price: Mapped[float] = mapped_column(Numeric(10, 2))  # Акційна ціна
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)  # Купи від X одиниць

    # Пріоритет (якщо товар в декількох акціях, вибираємо вищий)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Зв'язки
    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="items")
    product: Mapped["Product"] = relationship("Product")


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    image_id: Mapped[Optional[str]] = mapped_column(String(255))
    link_url: Mapped[Optional[str]] = mapped_column(String(255))

    # Залишаємо String, щоб не зламати старі записи 'link' та 'referral'
    promo_type: Mapped[str] = mapped_column(String(20), default="link")

    bonus_points: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    # --- НОВІ ПОЛЯ (Безпечні) ---
    # nullable=True дозволить базі створити колонку для старих записів без помилок
    start_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Новий зв'язок
    items: Mapped[List["PromotionItem"]] = relationship(
        "PromotionItem",
        back_populates="promotion",
        cascade="all, delete-orphan",
        lazy="selectin"  # Додаємо для швидкості, щоб ролі підвантажувались відразу
    )
    # ----------------------------

    target_roles: Mapped[List["Role"]] = relationship("Role", secondary=promo_roles, back_populates="promotions")
    user_logs: Mapped[List["UserPromoLog"]] = relationship("UserPromoLog", back_populates="promotion",
                                                           cascade="all, delete-orphan")


class UserPromoLog(Base):
    """Лог використання акцій для контролю одноразовості та нарахування бонусів"""
    __tablename__ = "user_promo_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    promo_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="CASCADE"))
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Зворотні зв'язки для зручності вибірки
    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="user_logs")
    user: Mapped["User"] = relationship("User")