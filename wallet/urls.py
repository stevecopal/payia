from django.urls import path
from wallet.views.wallet import wallet_view, ledger_view

urlpatterns = [
    path('', wallet_view, name='wallet'),
    path('ledger/', ledger_view, name='ledger'),
]
