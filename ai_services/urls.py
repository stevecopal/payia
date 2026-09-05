from django.urls import path
from ai_services.views.ai import (
    ai_catalog, ai_offer_detail, ai_rent, ai_my_rentals, ai_rental_detail,
    ai_rental_sync,
)

urlpatterns = [
    path('my-rentals/', ai_my_rentals, name='ai_my_rentals'),
    path('my-rentals/<int:pk>/', ai_rental_detail, name='ai_rental_detail'),
    path('my-rentals/<int:pk>/sync/', ai_rental_sync, name='ai_rental_sync'),
    path('', ai_catalog, name='ai_catalog'),
    path('<slug:slug>/', ai_offer_detail, name='ai_offer_detail'),
    path('<slug:slug>/rent/', ai_rent, name='ai_rent'),
]
