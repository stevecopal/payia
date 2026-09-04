from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, UserProfile, Role
from transactions.models import Deposit, Withdrawal, PaymentMethod


class PermissionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )
        UserProfile.objects.get_or_create(user=self.user)

    def test_unauthenticated_redirect(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_user_cannot_access_admin(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_idor_protection_deposits(self):
        other_user = User.objects.create_user('other', '+237690123457', password='TestPass123!')
        self.client.force_login(self.user)

        pm = PaymentMethod.objects.create(name='Test', slug='test-idor')
        deposit = Deposit.objects.create(
            user=other_user,
            amount=1000,
            payment_method=pm,
            transaction_id='TEST123',
        )

        response = self.client.get(reverse('deposit_detail', kwargs={'pk': deposit.pk}))
        self.assertEqual(response.status_code, 404)

    def test_idor_protection_withdrawals(self):
        other_user = User.objects.create_user('other', '+237690123457', password='TestPass123!')
        self.client.force_login(self.user)

        pm = PaymentMethod.objects.create(name='Test', slug='test-w')
        withdrawal = Withdrawal.objects.create(
            user=other_user,
            amount=1000,
            fee=0,
            net_amount=1000,
            withdrawal_method=pm,
            withdrawal_number='+237690123457',
        )

        response = self.client.get(reverse('withdrawal_detail', kwargs={'pk': withdrawal.pk}))
        self.assertEqual(response.status_code, 404)

    def test_admin_panel_requires_auth(self):
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_profile_requires_auth(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)

    def test_settings_requires_auth(self):
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 302)

    def test_deposit_list_requires_auth(self):
        response = self.client.get(reverse('deposit_list'))
        self.assertEqual(response.status_code, 302)

    def test_withdrawal_list_requires_auth(self):
        response = self.client.get(reverse('withdrawal_list'))
        self.assertEqual(response.status_code, 302)

    def test_password_change_requires_auth(self):
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_sees_own_deposits(self):
        self.client.force_login(self.user)
        pm = PaymentMethod.objects.create(name='Test', slug='test-own')
        Deposit.objects.create(
            user=self.user,
            amount=1000,
            payment_method=pm,
            transaction_id='OWN123',
        )
        Deposit.objects.create(
            user=User.objects.create_user('other', '+237690123458', password='TestPass123!'),
            amount=2000,
            payment_method=pm,
            transaction_id='OTHER123',
        )
        response = self.client.get(reverse('deposit_list'))
        self.assertEqual(response.status_code, 200)
