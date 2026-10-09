from django.urls import path
from transactions.views.deposits import deposit_list, deposit_create, deposit_detail
from transactions.views.online_deposits import (
    deposit_payment_result,
    deposit_status_json,
    deposit_verify,
    deposit_retry_payment,
)
from transactions.views.withdrawals import withdrawal_list, withdrawal_create, withdrawal_detail
from transactions.views.transactions import transaction_list

urlpatterns = [
    path('deposits/', deposit_list, name='deposit_list'),
    path('deposits/create/', deposit_create, name='deposit_create'),
    path('deposits/<int:pk>/', deposit_detail, name='deposit_detail'),

    # Paiement en ligne (Tara Money)
    path('deposits/<int:pk>/payment-result/', deposit_payment_result, name='deposit_payment_result'),
    path('deposits/<int:pk>/status/', deposit_status_json, name='deposit_status_json'),
    path('deposits/<int:pk>/verify/', deposit_verify, name='deposit_verify'),
    path('deposits/<int:pk>/retry-payment/', deposit_retry_payment, name='deposit_retry_payment'),

    path('withdrawals/', withdrawal_list, name='withdrawal_list'),
    path('withdrawals/create/', withdrawal_create, name='withdrawal_create'),
    path('withdrawals/<int:pk>/', withdrawal_detail, name='withdrawal_detail'),

    path('history/', transaction_list, name='transaction_list'),
]
