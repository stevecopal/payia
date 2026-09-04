from django.contrib import admin
from .models import Referral, Commission

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred_user', 'referral_level', 'is_active', 'created_at')
    list_filter = ('referral_level', 'is_active')
    search_fields = ('referrer__phone_number', 'referred_user__phone_number')

@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'source_user', 'referral_level', 'percentage', 'amount', 'status', 'created_at')
    list_filter = ('status', 'referral_level')
    search_fields = ('user__phone_number', 'source_user__phone_number')
