from datetime import datetime
from typing import List, Optional
import enum
from sqlalchemy import (
    BigInteger, String, Integer, ForeignKey, DateTime, func,
    UniqueConstraint, Numeric, Boolean, Text, Table, Column, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


# ==============================================================================
# 1. ЕНУМЕРАТОРИ (Списки статусів)
# ==============================================================================

class OrderStatus(enum.Enum):
    NEW = "new"  # Поточний кошик (чернетка)
    WAITING = "waiting"  # Відправлено менеджеру на перевірку
    APPROVED = "approved"  # Підтверджено менеджером (чекає оплати/відправки)
    COMPLETED = "completed"  # Отримано/Завершено
    CANCELLED = "cancelled"  # Скасовано


class ItemStatus(enum.Enum):
    ACTIVE = "active"  # В замовленні
    SOLD_OUT = "sold_out"  # Продано (немає в наявності)
    REJECTED = "rejected"  # Відхилено менеджером
    REPLACED = "replaced"  # Замінено на аналог


class ReviewType(enum.Enum):
    SERVICE = "service"  # Відгук про обслуговування/менеджера
    PRODUCT = "product"  # Відгук про товар
    USER = "user"  # Відгук менеджера про клієнта


class PromoType(enum.Enum):
    SIMPLE = "simple"
    QUANTITY = "quantity"
    BUNDLE = "bundle"
    FLASH = "flash"


# ==============================================================================
# 2. ДОПОМІЖНІ ТАБЛИЦІ (Many-to-Many)
# ==============================================================================

promo_roles = Table(
    "promo_roles",
    Base.metadata,
    Column("promo_id", Integer, ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# ==============================================================================
# 3. КОРИСТУВАЧІ ТА ДОСТУП
# ==============================================================================

class Role(Base):
    """Доступні ролі: client, manager, admin, owner, pro_client"""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    user_links: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="role")
    promotions: Mapped[List["Promotion"]] = relationship(
        "Promotion", secondary=promo_roles, back_populates="target_roles"
    )


class User(Base):
    """Основна таблиця користувачів"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)

    user_name: Mapped[str] = mapped_column(String(255))
    user_surname: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))

    full_name_1c: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    one_c_id: Mapped[Optional[str]] = mapped_column(String(30))
    barcode: Mapped[Optional[str]] = mapped_column(String(50), unique=True)

    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=3.0, server_default="3.0")
    total_spent: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    balance_points: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

    referrer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    referral_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)
    personal_manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    visit: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="user", cascade="all, delete-orphan",
                                                   lazy="selectin")
    delivery_addresses: Mapped[List["DeliveryAddress"]] = relationship("DeliveryAddress", back_populates="user",
                                                                       cascade="all, delete-orphan")
    point_transactions: Mapped[List["PointTransaction"]] = relationship("PointTransaction", back_populates="user",
                                                                        cascade="all, delete-orphan")

    # Нові зв'язки для замовлень та відгуків
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user", foreign_keys="[Order.user_id]")
    user_reviews: Mapped[List["Review"]] = relationship("Review", back_populates="author",
                                                        foreign_keys="[Review.author_id]")
    received_reviews: Mapped[List["Review"]] = relationship("Review", back_populates="target_user",
                                                            foreign_keys="[Review.target_user_id]")


class UserRole(Base):
    __tablename__ = "user_roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_links", lazy="selectin")
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)


# ==============================================================================
# 4. ЛОГІСТИКА ТА ВІДГУКИ
# ==============================================================================

class DeliveryAddress(Base):
    __tablename__ = "delivery_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    address_label: Mapped[str] = mapped_column(String(100))
    recipient_fio: Mapped[str] = mapped_column(String(255))
    recipient_phone: Mapped[str] = mapped_column(String(50))
    delivery_details: Mapped[str] = mapped_column(Text)
    delivery_type: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship("User", back_populates="delivery_addresses")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="address")


class Review(Base):
    """Універсальна система відгуків"""
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_type: Mapped[ReviewType] = mapped_column(Enum(ReviewType), nullable=False)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    target_product_code: Mapped[Optional[str]] = mapped_column(ForeignKey("products.code"))

    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text)

    is_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], back_populates="user_reviews")
    target_user: Mapped["User"] = relationship("User", foreign_keys=[target_user_id], back_populates="received_reviews")
    target_product: Mapped["Product"] = relationship("Product", back_populates="product_reviews")


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship("User", back_populates="point_transactions")


# ==============================================================================
# 5. КАТАЛОГ ТОВАРІВ
# ==============================================================================

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name_ua: Mapped[Optional[str]] = mapped_column(Text)
    catalog_number: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(Text)
    is_package: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sticker: Mapped[bool] = mapped_column(Boolean, default=False)
    info: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    tiktok_url: Mapped[Optional[str]] = mapped_column(String(500))
    instagram_url: Mapped[Optional[str]] = mapped_column(String(500))

    photos: Mapped[List["ProductPhoto"]] = relationship(back_populates="product", cascade="all, delete-orphan",
                                                        lazy="selectin")
    stocks: Mapped[List["ProductStock"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    # Нові зв'язки
    order_entries: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product")
    product_reviews: Mapped[List["Review"]] = relationship("Review", back_populates="target_product")
    related_news: Mapped[List["ProductNews"]] = relationship("ProductNews", back_populates="product")


class ProductPhoto(Base):
    __tablename__ = "product_photos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    photo_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text)
    tg_file_id: Mapped[Optional[str]] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    product: Mapped["Product"] = relationship("Product", back_populates="photos")


class ProductStock(Base):
    __tablename__ = "product_stocks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    storage_address: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship(back_populates="stocks")
    location: Mapped["Location"] = relationship()
    __table_args__ = (UniqueConstraint("product_code", "location_id"),)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


# ==============================================================================
# 6. КОМПЛЕКТАЦІЯ ТА АНАЛОГИ
# ==============================================================================

class ProductComponent(Base):
    __tablename__ = "product_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    component_code: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1.0)
    is_boxing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sticker: Mapped[bool] = mapped_column(Boolean, default=False)


class ProductAnalogue(Base):
    __tablename__ = "product_analogues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    analogue_code: Mapped[str] = mapped_column(String(30), index=True)
    __table_args__ = (UniqueConstraint("product_code", "analogue_code"),)


# ==============================================================================
# 7. ЗАМОВЛЕННЯ ТА КОШИК
# ==============================================================================

class Order(Base):
    """Голова замовлення"""
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NEW)

    delivery_type: Mapped[int] = mapped_column(Integer, default=1)  # 0-Самовивіз, 1-НП
    address_id: Mapped[Optional[int]] = mapped_column(ForeignKey("delivery_addresses.id"))

    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    manager_comment: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="orders")
    address: Mapped["DeliveryAddress"] = relationship("DeliveryAddress", back_populates="orders")


class OrderItem(Base):
    """Рядки замовлення"""
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"))
    quantity: Mapped[float] = mapped_column(Numeric(10, 2))

    price_base: Mapped[float] = mapped_column(Numeric(10, 2))
    price_client: Mapped[float] = mapped_column(Numeric(10, 2))
    price_manager: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.ACTIVE)
    manager_note: Mapped[Optional[str]] = mapped_column(Text)
    is_user_notified: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_entries")


# ==============================================================================
# 8. НОВИНИ ТА АКЦІЇ
# ==============================================================================

class ProductNews(Base):
    """Новини товарів"""
    __tablename__ = "product_news"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    photo_id: Mapped[Optional[str]] = mapped_column(String(255))
    product_code: Mapped[Optional[str]] = mapped_column(ForeignKey("products.code", ondelete="SET NULL"))

    views_count: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    published_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="related_news")


class Promotion(Base):
    __tablename__ = "promotions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    image_id: Mapped[Optional[str]] = mapped_column(String(255))
    link_url: Mapped[Optional[str]] = mapped_column(String(255))
    promo_type: Mapped[str] = mapped_column(String(20), default="link")
    bonus_points: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    items: Mapped[List["PromotionItem"]] = relationship("PromotionItem", back_populates="promotion",
                                                        cascade="all, delete-orphan", lazy="selectin")
    target_roles: Mapped[List["Role"]] = relationship("Role", secondary=promo_roles, back_populates="promotions")
    user_logs: Mapped[List["UserPromoLog"]] = relationship("UserPromoLog", back_populates="promotion",
                                                           cascade="all, delete-orphan")


class PromotionItem(Base):
    __tablename__ = "promotion_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="CASCADE"))
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code", ondelete="CASCADE"))
    discount_price: Mapped[float] = mapped_column(Numeric(10, 2))
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="items")
    product: Mapped["Product"] = relationship("Product")


class UserPromoLog(Base):
    __tablename__ = "user_promo_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    promo_id: Mapped[int] = mapped_column(ForeignKey("promotions.id", ondelete="CASCADE"))
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())

    promotion: Mapped["Promotion"] = relationship("Promotion", back_populates="user_logs")
    user: Mapped["User"] = relationship("User")

