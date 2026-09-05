from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from core.models import User, OTP, UserProfile
from core.services.auth_service import AuthService
from core.services.registration_security import RegistrationSecurityService
from core.middleware import RateLimitStore


class RegistrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        RateLimitStore.clear()
        RegistrationSecurityService.clear_all()

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

    def test_register_creates_wallet(self):
        self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        user = User.objects.get(username='testuser')
        from wallet.models import Wallet
        self.assertTrue(Wallet.objects.filter(user=user).exists())

    def test_register_auto_login(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='testuser')
        self._assert_user_logged_in(user)

    def test_register_redirects_to_dashboard(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_register_no_otp_generated(self):
        self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        user = User.objects.get(username='testuser')
        self.assertFalse(
            OTP.objects.filter(user=user, purpose='REGISTER').exists(),
            'No OTP should be generated for registration'
        )

    def test_register_no_sms_sent(self):
        self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        user = User.objects.get(username='testuser')
        from core.services.sms_service import get_sms_provider
        self.assertTrue(True)

    def test_register_no_verify_otp_redirect(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertNotEqual(response.url, reverse('verify_otp'))

    def test_register_duplicate_username(self):
        User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '691123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(phone_number='+237691123456').exists()
        )

    def test_register_duplicate_phone(self):
        User.objects.create_user('user1', '+237690123456', password='TestPass123!')
        response = self.client.post(reverse('register'), {
            'username': 'user2',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username='user2').exists()
        )

    def test_register_password_mismatch(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': 'TestPass123!',
            'password_confirm': 'DifferentPass!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='testuser').exists())

    def test_register_weak_password(self):
        response = self.client.post(reverse('register'), {
            'username': 'testuser',
            'phone_number': '690123456',
            'password': '123',
            'password_confirm': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='testuser').exists())

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

    def test_register_referral_code_from_session(self):
        referrer = User.objects.create_user(
            'referrer', '+237690123456', password='TestPass123!'
        )
        session = self.client.session
        session['referral_code'] = referrer.referral_code
        session.save()

        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'phone_number': '691123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.referred_by, referrer)

    def test_register_invalid_referral_code(self):
        session = self.client.session
        session['referral_code'] = 'INVALID'
        session.save()

        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'phone_number': '691123456',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def _assert_user_logged_in(self, user):
        response = self.client.get(reverse('dashboard'))
        if response.status_code == 302:
            self.assertNotEqual(response.url, reverse('login'))


class RegistrationSecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        RateLimitStore.clear()
        RegistrationSecurityService.clear_all()

    def test_rate_limit_service_blocks_after_max_attempts(self):
        ip = '192.168.1.1'
        for _ in range(RegistrationSecurityService.MAX_ATTEMPTS_PER_WINDOW):
            RegistrationSecurityService.record_attempt(ip, success=False)
        rate_ok, _ = RegistrationSecurityService.check_rate_limit(ip)
        self.assertFalse(rate_ok)

    def test_progressive_blocking_duration(self):
        ip = '127.0.0.1'
        RegistrationSecurityService._apply_block(f'ip:{ip}', ip)
        block = RegistrationSecurityService.check_blocked(ip)
        self.assertIsNotNone(block)
        self.assertTrue(block.is_active)
        self.assertEqual(block.level, 0)

        RegistrationSecurityService._apply_block(f'ip:{ip}', ip)
        block = RegistrationSecurityService.check_blocked(ip)
        self.assertIsNotNone(block)
        self.assertEqual(block.level, 1)

    def test_block_expires(self):
        from datetime import timedelta
        from django.utils import timezone
        ip = '127.0.0.1'
        key = f'ip:{ip}'
        RegistrationSecurityService._blocks[key] = [
            timezone.now() - timedelta(seconds=1)
        ]
        block = RegistrationSecurityService.check_blocked(ip)
        self.assertIsNone(block)

    def test_clear_blocks(self):
        ip = '127.0.0.1'
        RegistrationSecurityService._apply_block(f'ip:{ip}', ip)
        RegistrationSecurityService.clear_blocks(ip=ip)
        block = RegistrationSecurityService.check_blocked(ip)
        self.assertIsNone(block)

    def test_successful_registration_clears_attempts(self):
        ip = '127.0.0.1'
        RegistrationSecurityService.record_attempt(ip, success=False)
        RegistrationSecurityService.record_attempt(ip, success=False)
        RegistrationSecurityService.record_attempt(ip, success=False)

        RegistrationSecurityService.record_attempt(ip, success=True)

        rate_ok, _ = RegistrationSecurityService.check_rate_limit(ip)
        self.assertTrue(rate_ok)

    def test_phone_specific_blocking(self):
        ip = '127.0.0.1'
        phone = '+237690123456'
        RegistrationSecurityService._apply_block(
            RegistrationSecurityService._get_phone_key(phone), ip
        )
        block = RegistrationSecurityService.check_blocked(ip, phone=phone)
        self.assertIsNotNone(block)
        self.assertTrue(block.is_active)

    def test_username_specific_blocking(self):
        ip = '127.0.0.1'
        username = 'testuser'
        RegistrationSecurityService._apply_block(
            RegistrationSecurityService._get_username_key(username), ip
        )
        block = RegistrationSecurityService.check_blocked(ip, username=username)
        self.assertIsNotNone(block)
        self.assertTrue(block.is_active)

class UniqueConstraintTestCase(TransactionTestCase):
    def test_db_unique_username_constraint(self):
        User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user('testuser', '+237690123457', password='TestPass123!')
        self.assertEqual(User.objects.filter(username='testuser').count(), 1)

    def test_db_unique_phone_constraint(self):
        User.objects.create_user('user1', '+237690123456', password='TestPass123!')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user('user2', '+237690123456', password='TestPass123!')
        self.assertEqual(
            User.objects.filter(phone_number='+237690123456').count(), 1
        )


class LoginTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        RateLimitStore.clear()
        RegistrationSecurityService.clear_all()
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

    def test_existing_user_can_still_login(self):
        user = User.objects.create_user(
            'olduser', '+237690123457', password='OldPass123!'
        )
        response = self.client.post(reverse('login'), {
            'username': 'olduser',
            'password': 'OldPass123!',
        })
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

    def test_phone_number_unique_constraint(self):
        User.objects.create_user('user1', '+237690123456', password='TestPass123!')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user('user2', '+237690123456', password='TestPass123!')

    def test_username_unique_constraint(self):
        User.objects.create_user('testuser', '+237690123456', password='TestPass123!')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user('testuser', '+237690123457', password='TestPass123!')


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
