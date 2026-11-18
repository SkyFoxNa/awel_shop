# shop/admin/incoming.py
import re
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from shop.models import IncomingOrder, IncomingOrderItem, CounterpartyType, Counterparty


class IncomingOrderItemInline(admin.TabularInline):
    model = IncomingOrderItem
    extra = 1
    autocomplete_fields = ("product",)  # Дозволяє шукати товар або скористатися кнопкою "+" для створення нового
    fields = (
        "product",
        "quantity",
        "purchase_price",
        "storage_cell",
    )
    verbose_name = _("Позиція приходу")
    verbose_name_plural = _("📦 ТОВАРИ В ПРИХІДНОМУ ОРДЕРІ")


@admin.register(IncomingOrder)
class IncomingOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "order_date",
        "supplier",
        "location",
        "status",
        "created_by",
        "is_from_email",
        "created_at",
    )
    list_filter = (
        "status",
        "location",
        "is_from_email",
        "supplier",
    )
    search_fields = (
        "order_number",
        "supplier__name",
        "supplier__code",
    )
    inlines = [IncomingOrderItemInline]
    readonly_fields = (
        "created_at",
        "processed_at",
        "created_by",
        "is_from_email",
    )

    # Обмежуємо вибір постачальників у випадаючому списку тільки тими, у кого тип SUPPLIER
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "supplier":
            kwargs["queryset"] = Counterparty.objects.filter(
                counterparty_type=CounterpartyType.SUPPLIER,
                is_active=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        """Автоматична генерація наступного номера у форматі ПН-0000001"""
        last_order = IncomingOrder.objects.filter(order_number__startswith="ПН-").order_by("-id").first()
        next_num = 1
        if last_order:
            digits = re.findall(r'\d+', last_order.order_number)
            if digits:
                next_num = int(digits[-1]) + 1

        generated_number = f"ПН-{next_num:07d}"
        return {
            "order_number": generated_number,
            "order_date": timezone.now().date(),
        }

    def save_model(self, request, obj, form, change):
        """Автоматично фіксуємо користувача, який створив прихідний ордер"""
        if not change and not obj.created_by_id:
            # Якщо у вас в системі є мапінг між адмінкою Django та таблицею User (наприклад за email чи tg id),
            # тут можна прив'язати request.user. Спробуємо знайти або залишити поточного.
            from shop.models import User
            # Спроба зв'язати поточного адміна з таблицею User за email
            if request.user.is_authenticated and request.user.email:
                user_obj = User.objects.filter(email=request.user.email).first()
                if user_obj:
                    obj.created_by = user_obj
        super().save_model(request, obj, form, change)