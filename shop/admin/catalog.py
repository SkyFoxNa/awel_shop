# shop/admin/catalog.py

from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from shop.models import (
    Product,
    ProductPhoto,
    ProductStock,
    ProductComponent,
    ProductAnalogue,
    Location,
)

from .utils import get_drive_image_thumbnail


# ==============================================================================
# ФОТО ТОВАРУ
# ==============================================================================

class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 0
    classes = ("product-photos-inline",)
    fields = ("image_thumbnail", "photo_name")
    readonly_fields = ("image_thumbnail",)
    ordering = ("display_order", "photo_name")

    verbose_name = _("Фото товару")
    verbose_name_plural = _("📸 ФОТО ТОВАРУ")

    @admin.display(description=_("Фото з Диска"))
    def image_thumbnail(self, obj):
        product_code = obj.product_id or (obj.product.code if obj.product else None)
        return get_drive_image_thumbnail(
            obj.photo_name,
            product_code,
            height=240,
        )


# ==============================================================================
# ЗАЛИШКИ ТА ЦІНИ (ЗІ СПАКОВАНИМ ТОВАРОМ)
# ==============================================================================

class ProductStockForm(forms.ModelForm):
    class Meta:
        model = ProductStock
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        balance = cleaned_data.get("balance") or 0
        packaged_balance = cleaned_data.get("packaged_balance") or 0

        if balance < packaged_balance:
            cleaned_data["balance"] = packaged_balance
            self.data = self.data.copy()
            prefix = self.prefix
            self.data[f"{prefix}-balance"] = packaged_balance
            self.auto_adjusted = True
            self.old_balance = balance
            self.new_balance = packaged_balance

        return cleaned_data


class ProductStockInline(admin.TabularInline):
    model = ProductStock
    form = ProductStockForm
    extra = 1
    classes = ("product-stocks-inline",)
    fields = (
        "location",
        "price",
        "balance",
        "packaged_balance",
        "storage_address",
        "is_active",
    )

    verbose_name = _("Залишок та ціну")
    verbose_name_plural = _("📊 ЗАЛИШКИ ТА ЦІНИ ПО СКЛАДАХ")

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for form_inline in formset.forms:
            if not form_inline.cleaned_data or form_inline.cleaned_data.get("DELETE"):
                continue

            instance = form_inline.instance
            balance = form_inline.cleaned_data.get("balance", 0)
            packaged_balance = form_inline.cleaned_data.get("packaged_balance", 0)

            if balance < packaged_balance or getattr(form_inline, "auto_adjusted", False):
                instance.balance = packaged_balance
                location_name = instance.location.name if instance.location else "Склад"

                messages.warning(
                    request,
                    f"⚠️ Увага ({location_name}): Загальний залишок не може бути меншим за спакований! "
                    f"Загальну кількість було автоматично збільшено з {getattr(form_inline, 'old_balance', balance)} шт. "
                    f"до {packaged_balance} шт."
                )

            instance.save()

        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()


# ==============================================================================
# БАЗОВИЙ INLINE ДЛЯ КОМПЛЕКТУЮЧИХ (ПОВЕРНУТО АВТОДОПОВНЕННЯ)
# ==============================================================================

class BaseComponentInline(admin.TabularInline):
    extra = 1
    autocomplete_fields = ("component_code",)  # <-- ПОВЕРНУТО ШВИДКИЙ ПОШУК SELECT2

    readonly_fields = (
        "component_thumbnail",
        "component_name_display",
        "component_balance",
        "component_storage",
    )

    fields = (
        "component_thumbnail",
        "component_code",
        "component_name_display",
        "quantity",
        "component_balance",
        "component_storage",
    )

    def get_component_obj(self, obj):
        if not obj.component_code:
            return None
        if isinstance(obj.component_code, Product):
            return obj.component_code
        return Product.objects.filter(code=obj.component_code).first()

    @admin.display(description=_("Фото"))
    def component_thumbnail(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"

        first_photo = (
            comp_product.photos
            .order_by("display_order", "photo_name")
            .first()
        )
        photo_name = first_photo.photo_name if first_photo else None

        return get_drive_image_thumbnail(
            photo_name,
            comp_product.code,
            height=100,
        )

    @admin.display(description=_("Назва товару / Посилання"))
    def component_name_display(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"

        url = reverse(
            "admin:shop_product_change",
            args=[comp_product.pk],
        )

        return format_html(
            '<a href="{}" target="_blank"><b>{}</b><br><small>Код: {}</small></a>',
            url,
            comp_product.name_ua,
            comp_product.code,
        )

    @admin.display(description=_("Загальний залишок"))
    def component_balance(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"

        total_balance = sum(stock.balance for stock in comp_product.stocks.all())
        return f"{total_balance} шт."

    @admin.display(description=_("Склад 1 (Адреса)"))
    def component_storage(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"

        stock = comp_product.stocks.filter(location_id=1).first()
        if stock and stock.storage_address:
            return stock.storage_address

        return "—"


# ==============================================================================
# ТОВАР КОМПЛЕКТУ
# ==============================================================================

class ProductComponentInline(BaseComponentInline):
    model = ProductComponent
    fk_name = "parent_code"
    classes = ("product-components-inline",)

    verbose_name = _("Товар комплекту")
    verbose_name_plural = _("⚙️ ТОВАР КОМПЛЕКТУ")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            is_boxing=False,
            is_sticker=False,
        )


# ==============================================================================
# ТАРА КОМПЛЕКТУ
# ==============================================================================

class ProductBoxingInline(BaseComponentInline):
    model = ProductComponent
    fk_name = "parent_code"
    classes = ("product-boxing-inline",)

    verbose_name = _("Тару")
    verbose_name_plural = _("📦 ТАРА КОМПЛЕКТУ")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_boxing=True)


# ==============================================================================
# НАЛІПКИ КОМПЛЕКТУ
# ==============================================================================

class ProductStickerInline(BaseComponentInline):
    model = ProductComponent
    fk_name = "parent_code"
    classes = ("product-sticker-inline",)

    verbose_name = _("Наліпку")
    verbose_name_plural = _("🏷 НАЛІПКА КОМПЛЕКТУ (Враховує вже надруковані)")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_sticker=True)


# ==============================================================================
# АНАЛОГИ ТОВАРІВ
# ==============================================================================

class ProductAnalogueInline(admin.TabularInline):
    model = ProductAnalogue
    fk_name = "product"
    extra = 1
    classes = ("product-analogues-inline",)
    fields = ("analogue_code",)

    verbose_name = _("Аналог")
    verbose_name_plural = _("🔄 АНАЛОГИ ТОВАРІВ")


# ==============================================================================
# ОСНОВНИЙ КАТАЛОГ ТОВАРІВ
# ==============================================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    ordering = ("code",)

    list_display = (
        "code",
        "name_ua",
        "catalog_number",
        "category",
        "get_stocks_summary",
        "printed_stickers_count",
        "is_package",
        "is_sticker",
        "is_boxing",
    )

    search_fields = (
        "code",
        "name_ua",
        "catalog_number",
        "category",
    )

    list_filter = (
        "category",
        "is_package",
        "is_sticker",
        "is_boxing",
    )

    search_help_text = _("Пошук за кодом або назвою")

    inlines = [
        ProductPhotoInline,
        ProductStockInline,
        ProductComponentInline,
        ProductBoxingInline,
        ProductStickerInline,
        ProductAnalogueInline,
    ]

    fieldsets = (
        (_("2. Основна інформація"), {
            "fields": (
                "name_ua",
                "info",
                "code",
                "catalog_number",
                "category",
            ),
            "classes": ("product-main-info",),
        }),
        (_("7. Тип та властивості (Включно з наліпками)"), {
            "fields": (
                "is_package",
                "is_sticker",
                "is_boxing",
                "printed_stickers_count",
            ),
            "classes": ("product-type-properties",),
        }),
        (_("8. Зовнішні посилання"), {
            "fields": (
                "url",
                "tiktok_url",
                "instagram_url",
            ),
            "classes": (
                "product-external-links",
                "collapse",
            ),
        }),
    )

    @property
    def media(self):
        return super().media + forms.Media(
            css={
                "all": ("admin/css/custom_order.css",),
            }
        )

    @admin.display(description=_("Наявність на складах (Загальний / Спакований)"))
    def get_stocks_summary(self, obj):
        stocks = list(obj.stocks.all())
        if not stocks:
            return "—"

        result = []
        for stock in stocks:
            address = stock.storage_address or "—"
            result.append(
                format_html(
                    "<b>{}</b>: заг. <b>{} шт.</b> (спак. <b>{} шт.</b>) | 📍 {}",
                    stock.location.name,
                    stock.balance,
                    stock.packaged_balance,
                    address
                )
            )

        return mark_safe("<br>".join(result))


# ==============================================================================
# РЕЄСТРАЦІЯ ДОПОМІЖНИХ МОДЕЛЕЙ
# ==============================================================================

admin.site.register(Location)
admin.site.register(ProductComponent)
admin.site.register(ProductAnalogue)