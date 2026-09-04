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
    list_display = ('name', 'ai_model', 'category', 'price', 'duration_days', 'is_active', 'is_featured', 'total_rentals')
    list_filter = ('is_active', 'is_featured', 'ai_model', 'category')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(AiRental)
class AiRentalAdmin(admin.ModelAdmin):
    list_display = ('user', 'offer', 'amount_paid', 'status', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('user__phone_number', 'offer__name')

@admin.register(AiRevenue)
class AiRevenueAdmin(admin.ModelAdmin):
    list_display = ('user', 'offer', 'amount', 'period_start', 'period_end', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__phone_number',)
