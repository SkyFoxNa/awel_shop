# shop/admin/catalog.py
from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.urls import reverse
from shop.models import (
    Product, ProductPhoto, ProductStock,
    ProductComponent, ProductAnalogue, Location
)
from .utils import get_drive_image_thumbnail


# ==============================================================================
# ФОРМИ З ЖИВИМ ПОШУКОМ ТА ФІЛЬТРАЦІЄЮ ТОВАРІВ (SELECT2)
# ==============================================================================

class ComponentForm(forms.ModelForm):
    """Форма для звичайних товарів комплекту (без тари і наліпок)"""

    class Meta:
        model = ProductComponent
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'component_code' in self.fields:
            self.fields['component_code'].queryset = Product.objects.filter(is_boxing=False, is_sticker=False).order_by(
                'code')


class BoxingForm(forms.ModelForm):
    """Форма для тари (тільки is_boxing=True)"""

    class Meta:
        model = ProductComponent
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'component_code' in self.fields:
            self.fields['component_code'].queryset = Product.objects.filter(is_boxing=True).order_by('code')


class StickerForm(forms.ModelForm):
    """Форма для наліпок (тільки is_sticker=True)"""

    class Meta:
        model = ProductComponent
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'component_code' in self.fields:
            self.fields['component_code'].queryset = Product.objects.filter(is_sticker=True).order_by('code')


# ==============================================================================
# ВКЛАДЕНІ ТАБЛИЦІ (INLINES) ДЛЯ КАТАЛОГУ
# ==============================================================================

class ProductPhotoInline(admin.TabularInline):
    """1. Фото товарів"""
    model = ProductPhoto
    extra = 0
    fields = ('image_thumbnail', 'photo_name')
    readonly_fields = ('image_thumbnail',)
    ordering = ('display_order', 'photo_name')
    verbose_name = _("Фото товару")
    verbose_name_plural = _("📸 ФОТО ТОВАРУ")

    def image_thumbnail(self, obj):
        product_code = obj.product_id or (obj.product.code if obj.product else None)
        return get_drive_image_thumbnail(obj.photo_name, product_code, height=140)

    image_thumbnail.short_description = _("Фото з Диска")


class ProductStockInline(admin.TabularInline):
    """3. Залишки та ціни по складах"""
    model = ProductStock
    extra = 1
    fields = ('location', 'price', 'balance', 'storage_address', 'is_active')
    verbose_name = _("Залишок та ціну")
    verbose_name_plural = _("📊 ЗАЛИШКИ ТА ЦІНИ ПО СКЛАДАХ")


class BaseComponentInline(admin.TabularInline):
    """Базовий клас для комплектуючих"""
    extra = 1
    # Вмикаємо вбудований у Django живий пошук (Select2) оскільки component_code тепер ForeignKey
    autocomplete_fields = ('component_code',)

    readonly_fields = ('component_thumbnail', 'component_name_display', 'component_balance', 'component_storage')

    def get_component_obj(self, obj):
        if not obj.component_code:
            return None
        if isinstance(obj.component_code, Product):
            return obj.component_code
        return Product.objects.filter(code=obj.component_code).first()

    def component_thumbnail(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"
        first_photo = comp_product.photos.order_by('display_order', 'photo_name').first()
        photo_name = first_photo.photo_name if first_photo else None
        return get_drive_image_thumbnail(photo_name, comp_product.code, height=80)

    component_thumbnail.short_description = _("Фото")

    def component_name_display(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return str(obj.component_code)

        url = reverse('admin:shop_product_change', args=[comp_product.pk])
        return mark_safe(
            f'<a href="{url}" target="_blank"><b>{comp_product.name_ua}</b><br><small>Код: {comp_product.code}</small></a>'
        )

    component_name_display.short_description = _("Назва товару / Посилання")

    def component_balance(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"
        total_balance = sum(s.balance for s in comp_product.stocks.all())
        return f"{total_balance} шт."

    component_balance.short_description = _("Загальний залишок")

    def component_storage(self, obj):
        comp_product = self.get_component_obj(obj)
        if not comp_product:
            return "—"
        stock_loc1 = comp_product.stocks.filter(location_id=1).first()
        if stock_loc1 and stock_loc1.storage_address:
            return stock_loc1.storage_address
        return "—"

    component_storage.short_description = _("Склад 1 (Адреса)")


class ProductComponentInline(BaseComponentInline):
    """4. ⚙️ ТОВАР КОМПЛЕКТУ (без поміток is_boxing та is_sticker)"""
    model = ProductComponent
    form = ComponentForm
    fk_name = 'parent_code'
    verbose_name = _("Товар комплекту")
    verbose_name_plural = _("⚙️ ТОВАР КОМПЛЕКТУ")
    fields = ('component_thumbnail', 'component_code', 'component_name_display', 'quantity', 'component_balance',
              'component_storage')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_boxing=False, is_sticker=False)


class ProductBoxingInline(BaseComponentInline):
    """5. 📦 ТАРА (тільки is_boxing=True)"""
    model = ProductComponent
    form = BoxingForm
    fk_name = 'parent_code'
    verbose_name = _("Тару")
    verbose_name_plural = _("📦 ТАРА КОМПЛЕКТУ")
    fields = ('component_thumbnail', 'component_code', 'component_name_display', 'quantity', 'component_balance',
              'component_storage')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_boxing=True)

    def save_new(self, form, commit=True):
        form.instance.is_boxing = True
        return super().save_new(form, commit)


class ProductStickerInline(BaseComponentInline):
    """6. 🏷 НАЛІПКА (тільки is_sticker=True)"""
    model = ProductComponent
    form = StickerForm
    fk_name = 'parent_code'
    verbose_name = _("Наліпку")
    verbose_name_plural = _("🏷 НАЛІПКА КОМПЛЕКТУ")
    fields = ('component_thumbnail', 'component_code', 'component_name_display', 'quantity', 'component_balance',
              'component_storage')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_sticker=True)

    def save_new(self, form, commit=True):
        form.instance.is_sticker = True
        return super().save_new(form, commit)


class ProductAnalogueInline(admin.TabularInline):
    """9. Аналоги товарів"""
    model = ProductAnalogue
    fk_name = 'product'
    extra = 1
    fields = ('analogue_code',)
    verbose_name = _("Аналог")
    verbose_name_plural = _("🔄 АНАЛОГИ ТОВАРІВ")


# ==============================================================================
# ОСНОВНИЙ КЛАС КАТАЛОГУ ТОВАРІВ
# ==============================================================================

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_ua', 'catalog_number', 'category', 'get_stocks_summary', 'is_package', 'is_sticker',
                    'is_boxing')
    search_fields = ('code', 'name_ua', 'catalog_number', 'category')
    list_filter = ('category', 'is_package', 'is_sticker', 'is_boxing')
    search_help_text = _("Пошук за кодом або назвою")

    inlines = [
        ProductPhotoInline,  # 1. Фото
        ProductStockInline,  # 3. Залишки та ціни
        ProductComponentInline,  # 4. ⚙️ ТОВАР КОМПЛЕКТУ
        ProductBoxingInline,  # 5. 📦 ТАРА
        ProductStickerInline,  # 6. 🏷 НАЛІПКА
        ProductAnalogueInline,  # 9. Аналоги
    ]

    fieldsets = (
        (_('2. Основна інформація'), {
            'fields': ('name_ua', 'info', 'code', 'catalog_number', 'category')
        }),
        (_('7. Тип та властивості'), {
            'fields': ('is_package', 'is_sticker', 'is_boxing')
        }),
        (_('8. Зовнішні посилання'), {
            'fields': ('url', 'tiktok_url', 'instagram_url'),
            'classes': ('collapse',)
        }),
    )

    @property
    def media(self):
        super_media = super().media
        js = [
            'admin/js/vendor/jquery/jquery.min.js',
            'admin/js/product_order.js',
        ]
        return super_media + forms.Media(js=js)

    class Media:
        css = {
            'all': ('admin/css/custom_order.css',)
        }

    def get_stocks_summary(self, obj):
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