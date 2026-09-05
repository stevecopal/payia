from django.contrib import admin
from .models import AiModel, AiCategory, AiOffer, AiRental, AiRevenue


@admin.register(AiModel)
class AiModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AiCategory)
class AiCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AiOffer)
class AiOfferAdmin(admin.ModelAdmin):
    list_display = ('name', 'ai_model', 'category', 'price', 'duration_days', 'revenue_frequency', 'revenue_value', 'is_active', 'is_featured', 'total_rentals')
    list_filter = ('is_active', 'is_featured', 'revenue_frequency', 'ai_model', 'category')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AiRental)
class AiRentalAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'offer', 'amount_paid', 'earning_amount', 'status',
        'start_date', 'end_date', 'next_payment_at', 'last_payment_at',
        'payment_count', 'total_revenue_earned',
    )
    list_filter = ('status', 'offer__revenue_frequency')
    search_fields = ('user__phone_number', 'offer__name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AiRevenue)
class AiRevenueAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'offer', 'rental', 'amount', 'payment_reference',
        'period_start', 'period_end', 'status', 'credited_at', 'created_at',
    )
    list_filter = ('status',)
    search_fields = ('user__phone_number', 'payment_reference')
    readonly_fields = ('created_at',)
