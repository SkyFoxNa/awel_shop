from django.contrib import admin
from shop.models import User, Role, UserRole, DeliveryAddress

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Управління клієнтами бота"""
    list_display = ('user_id', 'user_name', 'phone', 'discount_pct', 'total_spent', 'is_active', 'is_locked')
    search_fields = ('user_id', 'user_name', 'phone', 'barcode', 'full_name_1c')
    list_filter = ('is_active', 'is_locked', 'created_at')
    readonly_fields = ('created_at',)

# Реєстрація пов'язаних моделей користувачів
admin.site.register(Role)
admin.site.register(UserRole)
admin.site.register(DeliveryAddress)