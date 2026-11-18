# shop/admin/counterparties.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _  # <--- ОСЬ ЦЬОГО ІМПОРТУ БРАКУВАЛО
from shop.models import Counterparty, CounterpartyType, CustomerProductRule


class CustomerProductRuleInline(admin.TabularInline):
    model = CustomerProductRule
    extra = 1
    autocomplete_fields = ("product",)
    verbose_name = _("Індивідуальне правило пакування")
    verbose_name_plural = _("⚙️ Індивідуальні правила пакування для товарів")


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "counterparty_type",
        "phone",
        "packaging_type",
        "discount",
        "is_active",
    )
    list_filter = (
        "counterparty_type",
        "is_active",
        "packaging_type",
    )
    search_fields = (
        "code",
        "name",
        "phone",
        "edrpou",
    )
    inlines = [CustomerProductRuleInline]

    fieldsets = (
        ("Основна інформація", {
            "fields": (
                "counterparty_type",
                "name",
                "code",
                "edrpou",
                "phone",
                "is_active",
            )
        }),
        ("Логістика та Пакування", {
            "fields": (
                "shipping_info",
                "packaging_type",
                "packing_note",
                "discount",
                "linked_location",
                "note",
            ),
            "description": "Укажіть стандарт пакування та примітки, які будуть виводитися як попередження для комірника та пакувальника.",
        }),
    )