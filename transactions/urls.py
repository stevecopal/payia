from django.urls import path
from transactions.views.deposits import deposit_list, deposit_create, deposit_detail
from transactions.views.withdrawals import withdrawal_list, withdrawal_create, withdrawal_detail
from transactions.views.transactions import transaction_list

urlpatterns = [
    path('deposits/', deposit_list, name='deposit_list'),
    path('deposits/create/', deposit_create, name='deposit_create'),
    path('deposits/<int:pk>/', deposit_detail, name='deposit_detail'),

    path('withdrawals/', withdrawal_list, name='withdrawal_list'),
    path('withdrawals/create/', withdrawal_create, name='withdrawal_create'),
    path('withdrawals/<int:pk>/', withdrawal_detail, name='withdrawal_detail'),

    path('history/', transaction_list, name='transaction_list'),
]
