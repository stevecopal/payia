from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, UserProfile, Role
from core.middleware import RateLimitStore
from core.services.registration_security import RegistrationSecurityService


class SecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        RateLimitStore.clear()
        RegistrationSecurityService.clear_all()

    def test_csrf_protection_register(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 403)

    def test_csrf_protection_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 403)

    def test_404_page_loads(self):
        response = self.client.get('/nonexistent-page/')
        self.assertEqual(response.status_code, 404)

    def test_admin_requires_staff(self):
        user = User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        self.client.force_login(user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_admin_panel_accessible_by_admin_role(self):
        role = Role.objects.create(name='Admin', slug='admin')
        user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!', role=role
        )
        self.client.force_login(user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_superadmin_accessible_by_superuser(self):
        user = User.objects.create_superuser(
            'admin', '+237690123456', password='AdminPass123!'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_superuser_login_redirects_to_admin(self):
        user = User.objects.create_superuser(
            'admin', '+237690123456', password='AdminPass123!'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_superuser_dashboard_url_redirects_to_admin(self):
        user = User.objects.create_superuser(
            'admin', '+237690123456', password='AdminPass123!'
        )
        self.client.force_login(user)
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, reverse('admin_dashboard'), fetch_redirect_response=False)

    def test_regular_user_cannot_access_admin(self):
        user = User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        self.client.force_login(user)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_suspended_user_blocked(self):
        user = User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        user.suspend('Suspicious activity')
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_middleware_sets_security_headers(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_admin_user_detail_requires_admin(self):
        user = User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        target = User.objects.create_user('target', '+237690123457', password='TestPass123!')
        self.client.force_login(user)
        response = self.client.get(
            reverse('admin_user_detail', kwargs={'pk': target.pk}),
        )
        self.assertEqual(response.status_code, 302)

    def test_logout_requires_post(self):
        user = User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        self.client.force_login(user)
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_password_not_in_logs(self):
        user = User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        client = Client()
        client.force_login(user)
        response = client.post(reverse('password_change'), {
            'current_password': 'TestPass123!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!',
        })
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewPass456!'))


class RegistrationSecurityMiddlewareTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        RateLimitStore.clear()
        RegistrationSecurityService.clear_all()

    def test_middleware_blocks_registration_when_blocked(self):
        ip = '127.0.0.1'
        RegistrationSecurityService._apply_block(
            RegistrationSecurityService._get_ip_key(ip), ip
        )

        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 403)

    def test_middleware_allows_registration_when_not_blocked(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)

    def test_registration_integrity_error_handled(self):
        User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username='testuser').count(), 1)
