from django.urls import path
from core.views.home import (
    home as home_view, about, features, ai_catalog_public,
    referral_page, faq, contact, download, terms, privacy,
)
from core.views.auth import (
    register_view,
    login_view,
    logout_view,
    verify_otp_view,
    password_change_view,
    password_reset_request_view,
    password_reset_confirm_view,
)
from core.views.profile import profile_view, profile_edit, profile_complete, withdrawal_info_view
from core.views.settings_view import settings_view, security_settings

urlpatterns = [
    path('', home_view, name='home'),
    path('about/', about, name='about'),
    path('features/', features, name='features'),
    path('ai/', ai_catalog_public, name='ai_public'),
    path('referral/', referral_page, name='referral_page'),
    path('faq/', faq, name='faq'),
    path('contact/', contact, name='contact'),
    path('download/', download, name='download'),
    path('terms/', terms, name='terms'),
    path('privacy/', privacy, name='privacy'),

    path('auth/register/', register_view, name='register'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/verify-otp/', verify_otp_view, name='verify_otp'),
    path('auth/password-change/', password_change_view, name='password_change'),
    path('auth/password-reset/', password_reset_request_view, name='password_reset_request'),
    path('auth/password-reset/<str:uidb64>/<str:token>/',
         password_reset_confirm_view, name='password_reset_confirm'),

    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit, name='profile_edit'),
    path('profile/complete/', profile_complete, name='profile_complete'),
    path('profile/withdrawal-info/', withdrawal_info_view, name='withdrawal_info'),

    path('settings/', settings_view, name='settings'),
    path('settings/security/', security_settings, name='security_settings'),
]
