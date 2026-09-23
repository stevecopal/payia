from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import PaymentMethod, Deposit, Withdrawal, PaymentEvent


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'requires_proof', 'min_amount', 'max_amount', 'display_order')
    list_filter = ('is_active', 'requires_proof')
    search_fields = ('name', 'slug', 'reception_name')
    prepopulated_fields = {'slug': ('name',)}
    fields = (
        'name', 'slug', 'description', 'is_active',
        'phone_number', 'reception_name', 'ussd_template', 'instructions',
        'requires_proof', 'requires_transaction_id',
        'min_amount', 'max_amount', 'fee_percentage', 'fee_fixed',
        'icon', 'display_order',
    )

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'payment_method', 'transaction_id', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__phone_number', 'transaction_id')
    readonly_fields = ('user', 'amount', 'payment_method', 'transaction_id', 'proof', 'ip_address', 'created_at', 'updated_at')
    fields = (
        'user', 'amount', 'payment_method', 'transaction_id',
        'phone_number', 'reception_number', 'ussd_code', 'proof',
        'status', 'admin_note', 'rejection_reason',
        'reviewed_by', 'reviewed_at', 'completed_at',
        'ip_address',
    )

    def has_change_permission(self, request, obj=None):
        return True

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'approve_deposits' not in actions:
            actions['approve_deposits'] = (
                self._approve_deposits, 'approve_deposits',
                _('Approuver les dépôts sélectionnés')
            )
        if 'reject_deposits' not in actions:
            actions['reject_deposits'] = (
                self._reject_deposits, 'reject_deposits',
                _('Rejeter les dépôts sélectionnés')
            )
        return actions

    def _approve_deposits(self, request, queryset):
        count = 0
        for deposit in queryset:
            try:
                deposit.approve(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, _('{} dépôt(s) approuvé(s).').format(count))

    def _reject_deposits(self, request, queryset):
        count = 0
        for deposit in queryset:
            try:
                deposit.reject(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, _('{} dépôt(s) rejeté(s).').format(count))

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'fee', 'net_amount', 'withdrawal_method', 'status', 'created_at')
    list_filter = ('status', 'withdrawal_method', 'created_at')
    search_fields = ('user__phone_number', 'withdrawal_number', 'external_reference')
    readonly_fields = ('user', 'amount', 'fee', 'net_amount', 'withdrawal_method', 'withdrawal_number', 'withdrawal_account_name', 'external_reference', 'ip_address', 'created_at', 'updated_at')
    fields = (
        'status', 'admin_note', 'rejection_reason',
        'reviewed_by', 'reviewed_at', 'processed_at', 'completed_at',
    )

    def has_change_permission(self, request, obj=None):
        return True

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'approve_withdrawals' not in actions:
            actions['approve_withdrawals'] = (
                self._approve_withdrawals, 'approve_withdrawals',
                _('Approuver les retraits sélectionnés')
            )
        if 'reject_withdrawals' not in actions:
            actions['reject_withdrawals'] = (
                self._reject_withdrawals, 'reject_withdrawals',
                _('Rejeter les retraits sélectionnés')
            )
        if 'complete_withdrawals' not in actions:
            actions['complete_withdrawals'] = (
                self._complete_withdrawals, 'complete_withdrawals',
                _('Marquer comme complété')
            )
        return actions

    def _approve_withdrawals(self, request, queryset):
        count = 0
        for w in queryset:
            try:
                w.approve(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, _('{} retrait(s) approuvé(s).').format(count))

    def _reject_withdrawals(self, request, queryset):
        count = 0
        for w in queryset:
            try:
                w.reject(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, _('{} retrait(s) rejeté(s).').format(count))

    def _complete_withdrawals(self, request, queryset):
        count = 0
        for w in queryset:
            try:
                w.complete(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, _('{} retrait(s) marqués comme complétés.').format(count))

@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'provider', 'event_type', 'processed', 'created_at')
    list_filter = ('provider', 'processed')
    search_fields = ('event_id', 'provider', 'event_type')
    readonly_fields = ('event_id', 'provider', 'event_type', 'payload', 'processed', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
