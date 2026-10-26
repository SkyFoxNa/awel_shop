# shop/admin/catalog.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from shop.models import (
    Product, ProductPhoto, ProductStock,
    ProductComponent, ProductAnalogue, Location
)
from .utils import get_drive_image_thumbnail


# ==============================================================================
# ВКЛАДЕНІ ТАБЛИЦІ (INLINES) ДЛЯ КАТАЛОГУ
# ==============================================================================

class ProductPhotoInline(admin.TabularInline):
    """
    Вкладена таблиця для фотографій товару.
    Показує великі мініатюри та ховає зайві службові поля від ручного редагування.
    """
    model = ProductPhoto
    extra = 0

    # Залишаємо для показу мініатюру та назву фото, інші поля робимо незмінними (readonly)
    fields = ('image_thumbnail', 'photo_name')
    readonly_fields = ('image_thumbnail',)

    # Сортування аналогічне до логіки бота
    ordering = ('display_order', 'photo_name')

    def image_thumbnail(self, obj):
        product_code = obj.product_id or (obj.product.code if obj.product else None)
        # Передаємо збільшений розмір (наприклад, 140x140 пікселів)
        return get_drive_image_thumbnail(obj.photo_name, product_code, height=140)

    image_thumbnail.short_description = _("Фото з Диска")


class ProductStockInline(admin.TabularInline):
    """Вкладена таблиця для цін та залишків товару по складах"""
    model = ProductStock
    extra = 1
    fields = ('location', 'price', 'balance', 'storage_address', 'is_active')


class ProductComponentInline(admin.TabularInline):
    """Вкладена таблиця для комплектуючих (тара, наліпки, запчастини)"""
    model = ProductComponent
    fk_name = 'parent_code'
    extra = 1
    fields = ('component_code', 'quantity', 'is_boxing', 'is_sticker')


class ProductAnalogueInline(admin.TabularInline):
    """Вкладена таблиця для аналогів товару"""
    model = ProductAnalogue
    fk_name = 'product'
    extra = 1
    fields = ('analogue_code',)


# ==============================================================================
# ОСНОВНИЙ КЛАС КАТАЛОГУ ТОВАРІВ
# ==============================================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Головна адмін-панель товару (аналог інформації з бота)"""
    list_display = ('code', 'name_ua', 'catalog_number', 'category', 'get_stocks_summary', 'is_package', 'is_sticker')
    search_fields = ('code', 'name_ua', 'catalog_number', 'category')
    list_filter = ('category', 'is_package', 'is_sticker')

    inlines = [
        ProductPhotoInline,
        ProductStockInline,
        ProductComponentInline,
        ProductAnalogueInline,
    ]

    fieldsets = (
        (_('Основна інформація'), {
            'fields': ('code', 'name_ua', 'catalog_number', 'category', 'info')
        }),
        (_('Тип товару'), {
            'fields': ('is_package', 'is_sticker')
        }),
        (_('Зовнішні посилання'), {
            'fields': ('url', 'tiktok_url', 'instagram_url'),
            'classes': ('collapse',)
        }),
    )

    def get_stocks_summary(self, obj):
        """Формує зручну зведену інформацію по наявності на складах (як у боті)"""
        stocks = obj.stocks.all()
        if not stocks:
            return "—"

        result = []
        for s in stocks:
            addr = f" (📍 {s.storage_address})" if s.storage_address else " (📍 —)"
            if s.balance > 0:
                result.append(f"<b>{s.location.name}</b>: {s.balance} шт.{addr}")
            else:
                result.append(f"{s.location.name}: <i>відсутній</i>{addr}")

        return mark_safe("<br>".join(result))

    get_stocks_summary.short_description = _("Наявність на складах")


# Реєстрація допоміжних моделей каталогу
admin.site.register(Location)
admin.site.register(ProductComponent)
admin.site.register(ProductAnalogue)