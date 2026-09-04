from django.contrib import admin
from .models import PaymentMethod, Deposit, Withdrawal, PaymentEvent

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'requires_proof', 'min_amount', 'max_amount', 'display_order')
    list_filter = ('is_active', 'requires_proof')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'payment_method', 'transaction_id', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__phone_number', 'transaction_id')
    readonly_fields = ('user', 'amount', 'payment_method', 'transaction_id', 'proof', 'ip_address', 'created_at', 'updated_at')

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'fee', 'net_amount', 'withdrawal_method', 'status', 'created_at')
    list_filter = ('status', 'withdrawal_method', 'created_at')
    search_fields = ('user__phone_number', 'withdrawal_number', 'external_reference')

@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'provider', 'event_type', 'processed', 'created_at')
    list_filter = ('provider', 'processed')
    readonly_fields = ('event_id', 'provider', 'event_type', 'payload', 'processed', 'created_at')
