from django.contrib import admin
from shop.models import Order, OrderItem, Review, PointTransaction

class OrderItemInline(admin.TabularInline):
    """Позиції всередині замовлення"""
    model = OrderItem
    extra = 0
    readonly_fields = ('price_base', 'price_client')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Управління замовленнями покупців"""
    list_display = ('order_number', 'user', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'delivery_type', 'created_at')
    search_fields = ('order_number', 'user__user_name', 'user__phone')
    inlines = [OrderItemInline]

# Реєстрація відгуків і транзакцій
admin.site.register(Review)
admin.site.register(PointTransaction)