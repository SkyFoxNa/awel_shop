from django.contrib import admin
from shop.models import ProductNews, Promotion, PromotionItem, UserPromoLog

class PromotionItemInline(admin.TabularInline):
    """Товари, що беруть участь в акції"""
    model = PromotionItem
    extra = 1

@admin.register(ProductNews)
class ProductNewsAdmin(admin.ModelAdmin):
    """Новини та сповіщення товарів"""
    list_display = ('title', 'product', 'is_published', 'published_at', 'views_count')
    list_filter = ('is_published', 'published_at')
    search_fields = ('title', 'content')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    """Маркетингові акції"""
    list_display = ('title', 'promo_type', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active', 'promo_type')
    inlines = [PromotionItemInline]

admin.site.register(UserPromoLog)