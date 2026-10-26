# from django.contrib import admin
# from .models import (
#     Role, User, UserRole, DeliveryAddress, Location,
#     Product, ProductPhoto, ProductStock, ProductComponent, ProductAnalogue,
#     Review, PointTransaction, Order, OrderItem,
#     ProductNews, Promotion, PromotionItem, UserPromoLog
# )
#
# # ==============================================================================
# # INLINES (Вкладені блоки)
# # ==============================================================================
#
# class ProductPhotoInline(admin.TabularInline):
#     model = ProductPhoto
#     extra = 1
#
# class ProductStockInline(admin.TabularInline):
#     model = ProductStock
#     extra = 1
#
# class OrderItemInline(admin.TabularInline):
#     model = OrderItem
#     extra = 0
#     readonly_fields = ('price_base', 'price_client')
#
# class PromotionItemInline(admin.TabularInline):
#     model = PromotionItem
#     extra = 1
#
# # ==============================================================================
# # ADMIN CLASSES
# # ==============================================================================
#
# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('code', 'name_ua', 'catalog_number', 'category', 'is_package', 'is_sticker')
#     search_fields = ('code', 'name_ua', 'catalog_number', 'category')
#     list_filter = ('category', 'is_package', 'is_sticker')
#     inlines = [ProductPhotoInline, ProductStockInline]
#
# @admin.register(User)
# class UserAdmin(admin.ModelAdmin):
#     list_display = ('user_id', 'user_name', 'phone', 'discount_pct', 'total_spent', 'is_active', 'is_locked')
#     search_fields = ('user_id', 'user_name', 'phone', 'barcode', 'full_name_1c')
#     list_filter = ('is_active', 'is_locked', 'created_at')
#     readonly_fields = ('created_at',)
#
# @admin.register(Order)
# class OrderAdmin(admin.ModelAdmin):
#     list_display = ('order_number', 'user', 'status', 'total_amount', 'created_at')
#     list_filter = ('status', 'delivery_type', 'created_at')
#     search_fields = ('order_number', 'user__user_name', 'user__phone')
#     inlines = [OrderItemInline]
#
# @admin.register(ProductNews)
# class ProductNewsAdmin(admin.ModelAdmin):
#     list_display = ('title', 'product', 'is_published', 'published_at', 'views_count')
#     list_filter = ('is_published', 'published_at')
#     search_fields = ('title', 'content')
#
# @admin.register(Promotion)
# class PromotionAdmin(admin.ModelAdmin):
#     list_display = ('title', 'promo_type', 'is_active', 'start_date', 'end_date')
#     list_filter = ('is_active', 'promo_type')
#     inlines = [PromotionItemInline]
#
# # Реєстрація інших допоміжних моделей
# admin.site.register(Role)
# admin.site.register(Location)
# admin.site.register(DeliveryAddress)
# admin.site.register(Review)
# admin.site.register(PointTransaction)
# admin.site.register(ProductComponent)
# admin.site.register(ProductAnalogue)
