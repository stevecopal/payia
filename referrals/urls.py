from django.urls import path
from referrals.views.referrals import referral_dashboard, referral_register

urlpatterns = [
    path('', referral_dashboard, name='referrals'),
    path('<str:code>/', referral_register, name='referral_register'),
]
