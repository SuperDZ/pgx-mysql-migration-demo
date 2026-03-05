from django.contrib import admin

from .models import Account, BillMonthly, Cdr, Customer, RiskCase, Txn


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_no", "name", "mobile", "status", "amount_total", "created_at")
    search_fields = ("customer_no", "name", "mobile")
    list_filter = ("status", "created_at")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "account_no", "customer", "status", "balance_amount", "opened_at")
    search_fields = ("account_no", "customer__customer_no", "customer__name")
    list_filter = ("status", "opened_at")


@admin.register(Txn)
class TxnAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "txn_no",
        "customer",
        "account",
        "status",
        "core_phase",
        "amount",
        "txn_at",
        "phase_updated_at",
    )
    search_fields = ("txn_no", "customer__customer_no", "account__account_no")
    list_filter = ("status", "core_phase", "txn_at")


@admin.register(Cdr)
class CdrAdmin(admin.ModelAdmin):
    list_display = ("id", "cdr_no", "customer", "account", "status", "charge_amount", "cdr_at")
    search_fields = ("cdr_no", "customer__customer_no", "account__account_no")
    list_filter = ("status", "cdr_at")


@admin.register(BillMonthly)
class BillMonthlyAdmin(admin.ModelAdmin):
    list_display = ("id", "bill_month", "customer", "account", "status", "bill_amount", "generated_at")
    search_fields = ("bill_month", "customer__customer_no", "account__account_no")
    list_filter = ("status", "bill_month", "generated_at")


@admin.register(RiskCase)
class RiskCaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "case_no",
        "customer",
        "account",
        "status",
        "risk_phase",
        "linked_txn_no",
        "risk_amount",
        "detected_at",
    )
    search_fields = ("case_no", "customer__customer_no", "account__account_no")
    list_filter = ("status", "risk_phase", "detected_at")
