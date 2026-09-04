from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile, Role, Permission, OTP, AuditLog, Setting


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = (
        'username', 'phone_number', 'first_name', 'last_name',
        'account_status', 'is_active', 'kyc_status', 'date_joined',
    )
    list_filter = (
        'account_status', 'is_active', 'is_suspended',
        'kyc_status', 'is_staff', 'date_joined',
    )
    search_fields = ('username', 'phone_number', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('referral_code', 'date_joined', 'last_login')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Informations personnelles'), {
            'fields': ('first_name', 'last_name', 'phone_number'),
        }),
        (_('Parrainage'), {
            'fields': ('referral_code', 'referred_by'),
        }),
        (_('Statut'), {
            'fields': (
                'is_active', 'account_status', 'is_suspended',
                'suspension_reason', 'kyc_status', 'risk_score',
            ),
        }),
        (_('Permissions'), {
            'fields': ('is_staff', 'is_superuser', 'role', 'groups', 'user_permissions'),
        }),
        (_('Dates'), {
            'fields': ('last_login', 'date_joined', 'last_login_ip'),
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'phone_number', 'first_name', 'last_name',
                'password1', 'password2',
            ),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'first_name', 'last_name', 'country',
        'is_profile_complete', 'preferred_currency',
    )
    list_filter = ('is_profile_complete', 'country', 'preferred_currency')
    search_fields = ('user__username', 'user__phone_number', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('permissions',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'name', 'category', 'created_at')
    list_filter = ('category',)
    search_fields = ('codename', 'name')


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'purpose', 'is_used', 'attempts', 'expires_at', 'created_at',
    )
    list_filter = ('purpose', 'is_used')
    search_fields = ('user__username', 'user__phone_number')
    readonly_fields = ('code', 'created_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'actor', 'action', 'target_type', 'target_id', 'created_at',
    )
    list_filter = ('action', 'created_at')
    search_fields = ('actor__username', 'actor__phone_number', 'action', 'description')
    readonly_fields = (
        'actor', 'action', 'target_type', 'target_id',
        'description', 'ip_address', 'user_agent', 'metadata', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'setting_type', 'is_active', 'updated_at')
    list_filter = ('setting_type', 'is_active')
    search_fields = ('key', 'description')
