from django.contrib import admin
from .models import Wallet, LedgerEntry

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'available_balance', 'pending_balance', 'total_deposited', 'total_withdrawn', 'is_active')
    search_fields = ('user__phone_number', 'user__first_name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'entry_type', 'amount', 'balance_before', 'balance_after', 'created_at')
    list_filter = ('entry_type', 'created_at')
    search_fields = ('user__phone_number', 'description')
    readonly_fields = ('user', 'wallet', 'entry_type', 'amount', 'balance_before', 'balance_after', 'reference_type', 'reference_id', 'description', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
