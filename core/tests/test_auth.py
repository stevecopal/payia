from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, OTP, UserProfile
from core.services.auth_service import AuthService
from core.middleware import RateLimitStore


class RegistrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        RateLimitStore.clear()

    def test_register_page_loads(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_register_valid(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_register_creates_profile(self):
        self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        user = User.objects.get(username='testuser')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_register_duplicate_username(self):
        User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '691123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_duplicate_phone(self):
        User.objects.create_user('user1', '+237690123456', password='TestPass123!')
        response = self.client.post(reverse('register'), {
            'username': 'user2',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_password_mismatch(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'DifferentPass!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_weak_password(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': '123',
            'password_confirm': '123',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_invalid_phone_not_cameroon(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '790123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_phone_does_not_start_with_6(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '790123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_short_username(self):
        response = self.client.post(reverse('register'), {
            'username': 'ab',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_invalid_username_chars(self):
        response = self.client.post(reverse('register'), {
            'username': 'test user!',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_register_redirects_if_authenticated(self):
        user = User.objects.create_user(
            'existing', '+237690123456', password='TestPass123!'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 302)


class LoginTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        RateLimitStore.clear()
        self.user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_valid(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_wrong_password(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'WrongPass!',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_nonexistent_user(self):
        response = self.client.post(reverse('login'), {
            'username': 'nonexistent',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_disabled_account(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_suspended_account(self):
        self.user.suspend('Test suspension')
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_error_message_generic(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'WrongPass!',
        })
        self.assertNotContains(response, 'existe')

    def test_login_redirects_if_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)


class LogoutTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )
        self.client.force_login(self.user)

    def test_logout_post(self):
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_logout_get_redirects(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)


class PasswordChangeTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )
        self.client.force_login(self.user)

    def test_password_change_page_loads(self):
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 200)

    def test_password_change_valid(self):
        response = self.client.post(reverse('password_change'), {
            'current_password': 'TestPass123!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))

    def test_password_change_wrong_current(self):
        response = self.client.post(reverse('password_change'), {
            'current_password': 'WrongPass!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!',
        })
        self.assertEqual(response.status_code, 200)

    def test_password_change_mismatch(self):
        response = self.client.post(reverse('password_change'), {
            'current_password': 'TestPass123!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'DifferentPass!',
        })
        self.assertEqual(response.status_code, 200)

    def test_password_change_weak_new(self):
        response = self.client.post(reverse('password_change'), {
            'current_password': 'TestPass123!',
            'new_password': '123',
            'new_password_confirm': '123',
        })
        self.assertEqual(response.status_code, 200)

    def test_old_password_no_longer_works(self):
        self.client.post(reverse('password_change'), {
            'current_password': 'TestPass123!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!',
        })
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('TestPass123!'))

    def test_password_change_requires_auth(self):
        self.client.logout()
        response = self.client.get(reverse('password_change'))
        self.assertEqual(response.status_code, 302)


class PasswordResetTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )

    def test_password_reset_request_page_loads(self):
        response = self.client.get(reverse('password_reset_request'))
        self.assertEqual(response.status_code, 200)

    def test_password_reset_request_valid(self):
        response = self.client.post(reverse('password_reset_request'), {
            'username': 'testuser',
        })
        self.assertEqual(response.status_code, 302)

    def test_password_reset_request_nonexistent_user(self):
        response = self.client.post(reverse('password_reset_request'), {
            'username': 'nonexistent',
        })
        self.assertEqual(response.status_code, 200)

    def test_password_reset_confirm_flow(self):
        uid, token = AuthService.generate_password_reset_token(self.user)
        response = self.client.get(
            reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        )
        self.assertEqual(response.status_code, 200)

    def test_password_reset_confirm_valid(self):
        uid, token = AuthService.generate_password_reset_token(self.user)
        response = self.client.post(
            reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token}),
            {
                'new_password': 'ResetPass789!',
                'new_password_confirm': 'ResetPass789!',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ResetPass789!'))

    def test_password_reset_token_invalid(self):
        response = self.client.get(
            reverse('password_reset_confirm', kwargs={'uidb64': 'invalid', 'token': 'invalid'})
        )
        self.assertEqual(response.status_code, 302)


class UserModelTestCase(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )
        self.assertIsNotNone(user.referral_code)
        self.assertTrue(user.check_password('TestPass123!'))

    def test_create_user_without_password(self):
        user = User.objects.create_user('testuser', '+237690123456')
        self.assertFalse(user.has_usable_password())

    def test_user_full_name(self):
        user = User.objects.create_user(
            'testuser', '+237690123456',
            password='TestPass123!',
            first_name='Jean',
            last_name='Dupont',
        )
        self.assertEqual(user.full_name, 'Jean Dupont')

    def test_user_display_name_fallback(self):
        user = User.objects.create_user('testuser', '+237690123456')
        self.assertEqual(user.display_name, 'testuser')

    def test_referral_code_uniqueness(self):
        user1 = User.objects.create_user('user1', '+237690123456')
        user2 = User.objects.create_user('user2', '+237690123457')
        self.assertNotEqual(user1.referral_code, user2.referral_code)

    def test_user_suspend(self):
        user = User.objects.create_user('testuser', '+237690123456')
        user.suspend('Test reason')
        user.refresh_from_db()
        self.assertTrue(user.is_suspended)
        self.assertFalse(user.is_active)
        self.assertEqual(user.account_status, 'SUSPENDED')

    def test_user_unsuspend(self):
        user = User.objects.create_user('testuser', '+237690123456')
        user.suspend('Test')
        user.unsuspend()
        user.refresh_from_db()
        self.assertFalse(user.is_suspended)
        self.assertTrue(user.is_active)
        self.assertEqual(user.account_status, 'ACTIVE')

    def test_user_block(self):
        user = User.objects.create_user('testuser', '+237690123456')
        user.block('Violation')
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(user.account_status, 'BLOCKED')

    def test_user_str(self):
        user = User.objects.create_user('testuser', '+237690123456')
        self.assertEqual(str(user), 'testuser')

    def test_is_account_active(self):
        user = User.objects.create_user('testuser', '+237690123456')
        self.assertTrue(user.is_account_active)

    def test_is_account_active_suspended(self):
        user = User.objects.create_user('testuser', '+237690123456')
        user.suspend('Test')
        self.assertFalse(user.is_account_active)

    def test_password_never_stored_in_plaintext(self):
        user = User.objects.create_user(
            'testuser', '+237690123456', password='TestPass123!'
        )
        self.assertNotEqual(user.password, 'TestPass123!')
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            'admin', '+237690123456', password='AdminPass123!'
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)


class PhoneValidatorTestCase(TestCase):
    def test_valid_cameroon_phone(self):
        from core.validators import normalize_phone_number, validate_cameroun_phone_number
        normalized = normalize_phone_number('690123456')
        self.assertEqual(normalized, '+237690123456')
        validate_cameroun_phone_number(normalized)

    def test_valid_with_prefix(self):
        from core.validators import normalize_phone_number
        normalized = normalize_phone_number('+237690123456')
        self.assertEqual(normalized, '+237690123456')

    def test_valid_with_spaces(self):
        from core.validators import normalize_phone_number
        normalized = normalize_phone_number('690 123 456')
        self.assertEqual(normalized, '+237690123456')

    def test_invalid_not_starting_with_6(self):
        from core.validators import validate_cameroun_phone_number
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_cameroun_phone_number('+237790123456')

    def test_invalid_too_short(self):
        from core.validators import validate_cameroun_phone_number
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_cameroun_phone_number('+2376901234')

    def test_invalid_too_long(self):
        from core.validators import validate_cameroun_phone_number
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_cameroun_phone_number('+2376901234567')

    def test_invalid_country_code(self):
        from core.validators import normalize_phone_number, validate_cameroun_phone_number
        from django.core.exceptions import ValidationError
        normalized = normalize_phone_number('+225690123456')
        with self.assertRaises(ValidationError):
            validate_cameroun_phone_number(normalized)
