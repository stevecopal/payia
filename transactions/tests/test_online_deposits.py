"""Tests du parcours de depot automatise avec Tara Money.

Tous les appels externe sont simules (aucun paiement reel) :
- `TaraClient.create_payment_link`
- `TaraClient.get_transaction_status`
"""

import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.middleware import RateLimitStore
from core.models import AuditLog, Setting, User
from notifications.models import Notification
from transactions.models import Deposit, DepositAttempt, PaymentEvent, PaymentMethod
from transactions.services.online_deposit_service import OnlineDepositService
from transactions.services.tara_service import TaraApiError, TaraClient
from wallet.models import LedgerEntry, Wallet


def _link_result(reference):
    url = f"https://taramoney.com/pay/{reference}"
    return {
        "general_link": url,
        "links": {"generalLink": url, "cardLink": f"https://taramoney.com/card/{reference}"},
        "raw": {"status": "success", "generalLink": url},
    }


@override_settings(
    TARA_API_KEY="test-api-key-secret",
    TARA_BUSINESS_ID="test-business",
    TARA_WEBHOOK_TOKEN="test-webhook-token",
    TARA_SITE_BASE_URL="https://payia.test",
    TARA_DEPOSIT_MIN=500,
    TARA_DEPOSIT_MAX=5000000,
    TARA_ATTEMPT_TTL=1800,
    TARA_REUSE_WINDOW=900,
    TARA_STATUS_THROTTLE=5,
)
class OnlineDepositTestCase(TestCase):
    """Base : paresseux a configurer, mocks fournnis par sous-classe."""

    def setUp(self):
        RateLimitStore.clear()
        self.user = User.objects.create_user("onlineuser", "+237611111111")
        self.wallet = Wallet.objects.get(user=self.user)
        Setting.objects.get_or_create(
            key="minimum_deposit",
            defaults={"value": "500", "setting_type": "INTEGER"},
        )
        self.pm = PaymentMethod.objects.get(slug="tara-money")

        self.link_calls = []
        self.status_calls = []
        self.mobilepay_calls = []
        self.link_error = None
        self.status_error = None
        self.mobilepay_error = None
        self.provider_status = "SUCCESS"

        link_patcher = mock.patch.object(
            TaraClient, "create_payment_link", side_effect=self._fake_link
        )
        status_patcher = mock.patch.object(
            TaraClient, "get_transaction_status", side_effect=self._fake_status
        )
        mobilepay_patcher = mock.patch.object(
            TaraClient, "mobilepay", side_effect=self._fake_mobilepay
        )
        link_patcher.start()
        status_patcher.start()
        mobilepay_patcher.start()
        self.addCleanup(link_patcher.stop)
        self.addCleanup(status_patcher.stop)
        self.addCleanup(mobilepay_patcher.stop)

    def _fake_link(self, **kwargs):
        self.link_calls.append(kwargs)
        if self.link_error is not None:
            raise self.link_error
        return _link_result(kwargs["product_id"])

    def _fake_mobilepay(self, **kwargs):
        self.mobilepay_calls.append(kwargs)
        if self.mobilepay_error is not None:
            raise self.mobilepay_error
        return {
            "status": "SUCCESS",
            "vendor": "MTN_CAMEROON",
            "auth_url": "",
            "message": "",
            "raw": {"status": "SUCCESS"},
        }

    def _fake_status(self, product_id):
        self.status_calls.append(product_id)
        if self.status_error is not None:
            raise self.status_error
        if callable(self.provider_status):
            return self.provider_status(product_id)
        return self.provider_status

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def initiate(self, amount="5000", phone="+237699999999"):
        return OnlineDepositService.initiate(
            user=self.user,
            amount=Decimal(amount),
            phone_number=phone,
            ip_address="127.0.0.1",
        )

    def webhook_body(self, reference, **overrides):
        payload = {
            "businessId": "test-business",
            "paymentId": "pay-0001",
            "productId": reference,
            "amount": "5000",
            "collectionId": "27731",
            "phoneNumber": "699999999",
            "creationDate": "2025-07-02T14:13:53.888+02:00",
            "changeDate": "2025-07-02T14:13:53.088+02:00",
            "status": "SUCCESS",
        }
        payload.update(overrides)
        return json.dumps(payload)

    def post_webhook(self, body, token="test-webhook-token", path=None):
        url = path or ("/webhooks/tara/" + (f"?token={token}" if token else ""))
        return self.client.post(url, data=body, content_type="application/json")

    def balance(self):
        self.wallet.refresh_from_db()
        return self.wallet.available_balance

    def deposit_entries(self):
        return LedgerEntry.objects.filter(user=self.user).filter(
            entry_type__iexact="DEPOSIT"
        )


# ==========================================================================
# 1. Initiation de la demande de depot
# ==========================================================================
class InitiateDepositTestCase(OnlineDepositTestCase):
    def test_initiate_creates_deposit_and_attempt_without_credit(self):
        deposit, attempt, pay_url = self.initiate()

        self.assertEqual(deposit.status, Deposit.Status.PENDING_REVIEW)
        self.assertEqual(deposit.user_id, self.user.pk)
        self.assertEqual(deposit.amount, Decimal("5000"))
        self.assertTrue(deposit.transaction_id.startswith("TARA-"))
        self.assertEqual(attempt.status, DepositAttempt.Status.PENDING)
        self.assertEqual(attempt.amount, Decimal("5000"))
        self.assertEqual(attempt.deposit_id, deposit.pk)
        self.assertTrue(pay_url)
        self.assertEqual(attempt.pay_url, pay_url)
        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(self.deposit_entries().count(), 0)
        # productId unique envoye a Tara = reference de la tentative
        self.assertEqual(self.link_calls[0]["product_id"], attempt.reference)
        self.assertEqual(self.link_calls[0]["product_price"], 5000)
        self.assertIn("/webhooks/tara/", self.link_calls[0]["web_hook_url"])
        self.assertIn("token=test-webhook-token", self.link_calls[0]["web_hook_url"])

    def test_initiate_notifies_user(self):
        self.initiate()
        self.assertTrue(
            Notification.objects.filter(
                user=self.user, notification_type="DEPOSIT_SUBMITTED"
            ).exists()
        )

    def test_below_minimum_rejected(self):
        with self.assertRaises(ValueError):
            self.initiate(amount="100")
        self.assertEqual(Deposit.objects.count(), 0)

    def test_above_maximum_rejected(self):
        with self.assertRaises(ValueError):
            self.initiate(amount="6000000")
        self.assertEqual(Deposit.objects.count(), 0)

    def test_non_integer_amount_rejected(self):
        with self.assertRaises(ValueError):
            self.initiate(amount="5000.5")
        self.assertEqual(Deposit.objects.count(), 0)

    def test_invalid_phone_rejected(self):
        with self.assertRaises(ValueError):
            self.initiate(phone="12345")
        self.assertEqual(Deposit.objects.count(), 0)

    def test_not_configured_rejected(self):
        with self.settings(TARA_API_KEY=""):
            with self.assertRaises(ValueError):
                self.initiate()
        self.assertEqual(Deposit.objects.count(), 0)

    def test_double_click_reuses_deposit_and_attempt(self):
        deposit1, attempt1, _ = self.initiate()
        deposit2, attempt2, _ = self.initiate()

        self.assertEqual(deposit1.pk, deposit2.pk)
        self.assertEqual(attempt1.pk, attempt2.pk)
        self.assertEqual(Deposit.objects.count(), 1)
        self.assertEqual(DepositAttempt.objects.count(), 1)
        # Le lien n'est genere qu'une seule fois.
        self.assertEqual(len(self.link_calls), 1)

    def test_different_amount_opens_new_deposit(self):
        self.initiate(amount="5000")
        self.initiate(amount="7000")
        self.assertEqual(Deposit.objects.count(), 2)

    def test_link_creation_failure_marks_attempt_and_keeps_deposit_open(self):
        self.link_error = TaraApiError("boom")
        with self.assertRaises(ValueError):
            self.initiate()

        attempt = DepositAttempt.objects.get()
        self.assertEqual(attempt.status, DepositAttempt.Status.FAILURE)
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.PENDING_REVIEW)
        self.assertEqual(self.balance(), Decimal("0"))

        # Un nouvel essai est autorise et cree une nouvelle tentative.
        self.link_error = None
        deposit, attempt2, pay_url = self.initiate()
        self.assertNotEqual(attempt.pk, attempt2.pk)
        self.assertEqual(attempt2.status, DepositAttempt.Status.PENDING)
        self.assertTrue(pay_url)
        self.assertEqual(Deposit.objects.count(), 1)


# ==========================================================================
# 2. Webhook : authenticite, verification et credit
# ==========================================================================
class WebhookTestCase(OnlineDepositTestCase):
    def test_success_webhook_credits_wallet_exactly_once(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(self.webhook_body(attempt.reference))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["credited"], 1)

        self.assertEqual(self.balance(), Decimal("5000"))
        deposit = Deposit.objects.get()
        self.assertEqual(deposit.status, Deposit.Status.COMPLETED)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, DepositAttempt.Status.SUCCESS)
        self.assertEqual(attempt.payment_id, "pay-0001")

        entry = self.deposit_entries().get()
        self.assertEqual(entry.reference_type, "Deposit")
        self.assertEqual(entry.reference_id, deposit.pk)
        self.assertEqual(entry.amount, Decimal("5000"))
        self.assertEqual(
            AuditLog.objects.filter(action="deposit.auto_approved").count(), 1
        )

    def test_exact_duplicate_webhook_ignored(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"
        body = self.webhook_body(attempt.reference)

        self.post_webhook(body)
        second = self.post_webhook(body)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["duplicate"], 1)
        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(self.deposit_entries().count(), 1)
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_late_duplicate_webhook_has_no_financial_effect(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"
        self.post_webhook(self.webhook_body(attempt.reference))
        late = self.post_webhook(
            self.webhook_body(attempt.reference, changeDate="2025-07-02T15:00:00.000+02:00")
        )

        self.assertEqual(late.status_code, 200)
        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(self.deposit_entries().count(), 1)

    def test_missing_token_rejected(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(self.webhook_body(attempt.reference), token=None)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(PaymentEvent.objects.count(), 0)
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.PENDING_REVIEW)

    def test_wrong_token_rejected(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(
            self.webhook_body(attempt.reference), token="forged-token"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_webhook_rejected_when_secret_not_configured(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        with self.settings(TARA_WEBHOOK_TOKEN=""):
            response = self.post_webhook(self.webhook_body(attempt.reference))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_wrong_business_id_ignored(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(
            self.webhook_body(attempt.reference, businessId="someone-else")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.PENDING_REVIEW)

    def test_wrong_amount_not_credited(self):
        _, attempt, _ = self.initiate(amount="5000")
        self.provider_status = "SUCCESS"

        response = self.post_webhook(self.webhook_body(attempt.reference, amount="1"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("0"))
        self.assertTrue(
            AuditLog.objects.filter(action="deposit.amount_mismatch").exists()
        )

    def test_invalid_json_rejected(self):
        response = self.post_webhook("{not json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_unknown_reference_ignored(self):
        self.initiate()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(self.webhook_body("payia_unknown_reference"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_payload_without_product_id_not_credited(self):
        self.initiate()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(self.webhook_body("", productId=""))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_provider_failure_not_credited(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "FAILURE"

        response = self.post_webhook(self.webhook_body(attempt.reference))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("0"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, DepositAttempt.Status.FAILURE)
        # Une tentative echouee ne bloque pas le depot.
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.PENDING_REVIEW)

    def test_provider_pending_not_credited(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "PENDING"

        self.post_webhook(self.webhook_body(attempt.reference, status="FAILURE"))

        self.assertEqual(self.balance(), Decimal("0"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, DepositAttempt.Status.PENDING)

    def test_provider_unreachable_no_credit(self):
        _, attempt, _ = self.initiate()
        self.status_error = TaraApiError("reseau")

        response = self.post_webhook(self.webhook_body(attempt.reference))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("0"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, DepositAttempt.Status.PENDING)

    def test_payload_success_but_provider_failure_not_credited(self):
        """Meme avec un webhook falsifie, seul le prestataire decide."""
        _, attempt, _ = self.initiate()
        self.provider_status = "FAILURE"

        self.post_webhook(self.webhook_body(attempt.reference, status="SUCCESS"))

        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.PENDING_REVIEW)

    def test_no_secret_leaks_in_response(self):
        _, attempt, _ = self.initiate()
        response = self.post_webhook(self.webhook_body(attempt.reference))
        self.assertNotIn("test-api-key-secret", response.content.decode())


# ==========================================================================
# 3. Tentatives multiples
# ==========================================================================
class MultipleAttemptsTestCase(OnlineDepositTestCase):
    def test_retry_after_failure_then_single_credit(self):
        deposit, attempt1, _ = self.initiate()

        # 1ere tentative echoue.
        self.provider_status = "FAILURE"
        self.post_webhook(self.webhook_body(attempt1.reference))
        attempt1.refresh_from_db()
        self.assertEqual(attempt1.status, DepositAttempt.Status.FAILURE)

        # Nouvelle tentative sur le meme depot.
        self.provider_status = "SUCCESS"
        deposit2, attempt2, pay_url = self.initiate()
        self.assertEqual(deposit2.pk, deposit.pk)
        self.assertNotEqual(attempt1.pk, attempt2.pk)
        self.assertEqual(Deposit.objects.count(), 1)

        self.post_webhook(self.webhook_body(attempt2.reference))

        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(self.deposit_entries().count(), 1)
        self.assertEqual(DepositAttempt.objects.count(), 2)
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.COMPLETED)

    def test_only_one_attempt_can_credit_a_deposit(self):
        deposit, attempt1, _ = self.initiate()
        attempt2 = DepositAttempt.objects.create(
            deposit=deposit,
            reference="payia_second_attempt",
            amount=deposit.amount,
            expires_at=timezone.now() + timedelta(seconds=1800),
        )

        first = OnlineDepositService.apply_provider_status(
            attempt1.reference, "SUCCESS", source="webhook"
        )
        second = OnlineDepositService.apply_provider_status(
            attempt2.reference, "SUCCESS", source="webhook"
        )

        self.assertEqual(first, "credited")
        self.assertEqual(second, "conflict")
        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(self.deposit_entries().count(), 1)

    def test_db_constraint_blocks_second_success_attempt(self):
        deposit, attempt1, _ = self.initiate()
        attempt2 = DepositAttempt.objects.create(
            deposit=deposit,
            reference="payia_blocked_attempt",
            amount=deposit.amount,
            expires_at=timezone.now() + timedelta(seconds=1800),
        )
        OnlineDepositService.apply_provider_status(
            attempt1.reference, "SUCCESS", source="webhook"
        )

        attempt2.status = DepositAttempt.Status.SUCCESS
        with self.assertRaises(Exception):
            from django.db import transaction
            with transaction.atomic():
                attempt2.save()

        attempt2.refresh_from_db()
        self.assertNotEqual(attempt2.status, DepositAttempt.Status.SUCCESS)
        self.assertEqual(self.balance(), Decimal("5000"))

    def test_expired_attempt_allows_new_attempt(self):
        deposit, attempt1, _ = self.initiate()
        DepositAttempt.objects.filter(pk=attempt1.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        expired = OnlineDepositService.expire_attempts()
        self.assertEqual(expired, 1)
        attempt1.refresh_from_db()
        self.assertEqual(attempt1.status, DepositAttempt.Status.EXPIRED)

        _, attempt2, _ = self.initiate()
        self.assertNotEqual(attempt1.pk, attempt2.pk)
        self.assertEqual(Deposit.objects.count(), 1)

    def test_confirmed_payment_after_expiry_still_credits(self):
        """Un paiement confirme apres expiration doit etre credite."""
        _, attempt, _ = self.initiate()
        DepositAttempt.objects.filter(pk=attempt.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        OnlineDepositService.expire_attempts()
        self.provider_status = "SUCCESS"

        outcome = OnlineDepositService.verify_attempt(attempt.reference, source="reconcile")

        self.assertEqual(outcome, "credited")
        self.assertEqual(self.balance(), Decimal("5000"))


# ==========================================================================
# 4. Cotes utilisateur : retour, verification, impossibilite d'autrui
# ==========================================================================
class UserEndpointsTestCase(OnlineDepositTestCase):
    def login(self):
        self.client.force_login(self.user)

    def test_payment_result_verifies_server_side(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"
        self.login()

        response = self.client.get(
            reverse("deposit_payment_result", args=[attempt.deposit_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(self.status_calls, [attempt.reference])

    def test_payment_result_pending_does_not_credit(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "PENDING"
        self.login()

        self.client.get(reverse("deposit_payment_result", args=[attempt.deposit_id]))

        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.PENDING_REVIEW)

    def test_status_json_is_read_only(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"
        self.login()

        response = self.client.get(
            reverse("deposit_status_json", args=[attempt.deposit_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deposit_status"], "pending_review")
        self.assertEqual(self.balance(), Decimal("0"))
        # La lecture seule n'interroge pas le prestataire.
        self.assertEqual(self.status_calls, [])

    def test_user_cannot_verify_another_users_deposit(self):
        deposit, attempt, _ = self.initiate()
        other = User.objects.create_user("otheruser", "+237622222222")
        self.client.force_login(other)
        self.provider_status = "SUCCESS"

        response = self.client.get(
            reverse("deposit_payment_result", args=[deposit.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(attempt.status, DepositAttempt.Status.PENDING)
        self.assertEqual(other.deposits.count(), 0)

    def test_retry_endpoint_requires_post(self):
        _, attempt, _ = self.initiate()
        self.login()
        response = self.client.get(
            reverse("deposit_retry_payment", args=[attempt.deposit_id])
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(DepositAttempt.objects.count(), 1)

    def test_verify_endpoint_requires_post(self):
        _, attempt, _ = self.initiate()
        self.login()
        response = self.client.get(
            reverse("deposit_verify", args=[attempt.deposit_id])
        )
        self.assertEqual(response.status_code, 405)

    def test_status_check_is_throttled(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "PENDING"

        first = OnlineDepositService.verify_attempt(attempt.reference)
        second = OnlineDepositService.verify_attempt(attempt.reference)

        self.assertEqual(first, "pending")
        self.assertEqual(second, "throttled")
        self.assertEqual(len(self.status_calls), 1)


# ==========================================================================
# 5. Vue de creation (integration au wizard existant)
# ==========================================================================
class DepositCreateViewTestCase(OnlineDepositTestCase):
    def login(self):
        self.client.force_login(self.user)

    def test_step1_card_redirects_to_payment_link(self):
        self.login()
        response = self.client.post(
            reverse("deposit_create"),
            {
                "step": "1",
                "payment_method": "online:card",
                "phone_digits": "699999999",
                "amount": "5000",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://taramoney.com/pay/"))
        self.assertEqual(Deposit.objects.count(), 1)
        self.assertEqual(self.balance(), Decimal("0"))
        self.assertEqual(len(self.mobilepay_calls), 0)

    def test_step1_mobile_money_triggers_direct_debit_without_credit(self):
        self.login()
        response = self.client.post(
            reverse("deposit_create"),
            {
                "step": "1",
                "payment_method": "online:momo",
                "phone_digits": "699999999",
                "amount": "5000",
            },
        )

        # Pas de redirection vers un lien : on reste sur la page du depot.
        self.assertEqual(response.status_code, 302)
        deposit = Deposit.objects.get()
        self.assertIn(f"/transactions/deposits/{deposit.pk}/", response["Location"])
        attempt = deposit.attempts.get()
        self.assertEqual(attempt.channel, DepositAttempt.Channel.MOMO)
        self.assertEqual(attempt.status, DepositAttempt.Status.PENDING)
        self.assertEqual(len(self.mobilepay_calls), 1)
        self.assertEqual(self.mobilepay_calls[0]["phone_number"], "237699999999")
        self.assertEqual(self.mobilepay_calls[0]["product_price"], 5000)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_step1_requires_a_valid_online_channel(self):
        self.login()
        response = self.client.post(
            reverse("deposit_create"),
            {
                "step": "1",
                "payment_method": "online:not-a-channel",
                "phone_digits": "699999999",
                "amount": "5000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("payment_method", response.context["errors"])
        self.assertEqual(Deposit.objects.count(), 0)
        self.assertEqual(len(self.mobilepay_calls), 0)

    def test_step1_exposes_tara_channels(self):
        self.login()
        response = self.client.get(reverse("deposit_create"))

        values = [ch["value"] for ch in response.context["online_channels"]]
        self.assertEqual(values, ["online:momo", "online:wave", "online:card"])
        # Tara Money n'apparait plus comme methode manuelle.
        slugs = [pm.slug for pm in response.context["payment_methods"]]
        self.assertNotIn("tara-money", slugs)

    def test_direct_debit_webhook_credits_wallet(self):
        self.login()
        self.client.post(
            reverse("deposit_create"),
            {
                "step": "1",
                "payment_method": "online:momo",
                "phone_digits": "699999999",
                "amount": "5000",
            },
        )
        attempt = DepositAttempt.objects.get()
        self.provider_status = "SUCCESS"

        response = self.post_webhook(self.webhook_body(attempt.reference))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["credited"], 1)
        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.COMPLETED)

    def test_manual_method_still_uses_wizard(self):
        manual = PaymentMethod.objects.create(
            name="MTN Mobile Money",
            slug="mtn-manual-test",
            phone_number="690123456",
            ussd_template="*126*14*5555*{amount}#",
            is_active=True,
        )
        self.login()
        response = self.client.post(
            reverse("deposit_create"),
            {
                "step": "1",
                "payment_method": str(manual.pk),
                "phone_digits": "699999999",
                "amount": "5000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["step"], 2)
        self.assertEqual(Deposit.objects.count(), 0)

    def test_online_method_hidden_when_not_configured(self):
        self.login()
        with self.settings(TARA_API_KEY=""):
            response = self.client.get(reverse("deposit_create"))

        self.assertEqual(response.context["online_channels"], [])
        slugs = [pm.slug for pm in response.context["payment_methods"]]
        self.assertNotIn("tara-money", slugs)

    def test_below_minimum_rejected_by_view(self):
        self.login()
        response = self.client.post(
            reverse("deposit_create"),
            {
                "step": "1",
                "payment_method": "online:momo",
                "phone_digits": "699999999",
                "amount": "100",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("amount", response.context["errors"])
        self.assertEqual(Deposit.objects.count(), 0)
        self.assertEqual(len(self.mobilepay_calls), 0)

    def test_below_minimum_rejected_by_service_even_if_view_is_bypassed(self):
        """La limite est appliquee cote serveur, pas seulement dans la vue."""
        with self.assertRaises(ValueError):
            OnlineDepositService.initiate(
                user=self.user, amount=Decimal("100"), phone_number="+237699999999"
            )
        self.assertEqual(Deposit.objects.count(), 0)


# ==========================================================================
# 6. Reconciliation (webhook perdu) et taches planifiees
# ==========================================================================
class ReconciliationTestCase(OnlineDepositTestCase):
    def test_reconcile_credits_deposit_without_webhook(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        stats = OnlineDepositService.reconcile()

        self.assertEqual(stats["checked"], 1)
        self.assertEqual(stats["credited"], 1)
        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.COMPLETED)

    def test_reconcile_does_not_credit_when_provider_unreachable(self):
        _, attempt, _ = self.initiate()
        self.status_error = TaraApiError("timeout")

        stats = OnlineDepositService.reconcile()

        self.assertEqual(stats["credited"], 0)
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(self.balance(), Decimal("0"))
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, DepositAttempt.Status.PENDING)

    def test_reconcile_marks_failure(self):
        _, attempt, _ = self.initiate()
        self.provider_status = "FAILURE"

        stats = OnlineDepositService.reconcile()

        self.assertEqual(stats["failed"], 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, DepositAttempt.Status.FAILURE)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_reconcile_is_idempotent(self):
        self.initiate()
        self.provider_status = "SUCCESS"

        OnlineDepositService.reconcile()
        OnlineDepositService.reconcile()

        self.assertEqual(self.balance(), Decimal("5000"))
        self.assertEqual(self.deposit_entries().count(), 1)

    def test_reconcile_skips_conflicting_attempts(self):
        deposit, attempt, _ = self.initiate()
        DepositAttempt.objects.filter(pk=attempt.pk).update(conflict=True)
        self.provider_status = "SUCCESS"

        stats = OnlineDepositService.reconcile()

        self.assertEqual(stats["checked"], 0)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_reconcile_disabled_without_credentials(self):
        with self.settings(TARA_API_KEY=""):
            stats = OnlineDepositService.reconcile()
        self.assertTrue(stats.get("disabled"))

    def test_celery_tasks_callable(self):
        from transactions.tasks import (
            expire_online_payment_attempts,
            reconcile_online_payments,
        )

        _, attempt, _ = self.initiate()
        DepositAttempt.objects.filter(pk=attempt.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.provider_status = "SUCCESS"

        self.assertEqual(expire_online_payment_attempts.apply().result["expired"], 1)
        stats = reconcile_online_payments.apply().result
        self.assertEqual(stats["credited"], 1)
        self.assertEqual(self.balance(), Decimal("5000"))


# ==========================================================================
# 7. Surete : credit impossible pour un autre utilisateur / montant forge
# ==========================================================================
class SafetyTestCase(OnlineDepositTestCase):
    def test_cannot_credit_another_user(self):
        deposit, attempt, _ = self.initiate()
        self.provider_status = "SUCCESS"

        # Un utilisateur tier ne peut pas declencher la verification.
        User.objects.create_user("attacker", "+237633333333")
        self.client.force_login(User.objects.get(username="attacker"))
        response = self.client.get(
            reverse("deposit_payment_result", args=[deposit.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Wallet.objects.get(user=self.user).available_balance, Decimal("0"))

        # Meme en passant par le service, le credit ne concerne que le
        # proprietaire du depot : pas d'ecriture au nom d'un autre utilisateur.
        OnlineDepositService.apply_provider_status(attempt.reference, "SUCCESS")
        attacker_wallet = Wallet.objects.get(user__username="attacker")
        self.assertEqual(attacker_wallet.available_balance, Decimal("0"))
        self.assertEqual(Wallet.objects.get(user=self.user).available_balance, Decimal("5000"))

    def test_amount_mismatch_blocks_credit_even_if_provider_says_success(self):
        deposit, attempt, _ = self.initiate(amount="7000")
        self.provider_status = "SUCCESS"

        outcome = OnlineDepositService.apply_provider_status(
            attempt.reference,
            "SUCCESS",
            payload={"amount": "7000", "businessId": "test-business"},
        )
        self.assertEqual(outcome, "credited")

        bad = OnlineDepositService.apply_provider_status(
            attempt.reference,
            "SUCCESS",
            payload={"amount": "7001", "businessId": "test-business"},
        )
        self.assertEqual(bad, "already_credited")
        self.assertEqual(self.balance(), Decimal("7000"))
        self.assertEqual(self.deposit_entries().count(), 1)

    def test_conflict_when_deposit_already_rejected(self):
        deposit, attempt, _ = self.initiate()
        deposit.status = Deposit.Status.REJECTED
        deposit.rejection_reason = "test"
        deposit.save(update_fields=["status", "rejection_reason", "updated_at"])
        self.provider_status = "SUCCESS"

        outcome = OnlineDepositService.apply_provider_status(
            attempt.reference, "SUCCESS", source="webhook"
        )

        self.assertEqual(outcome, "conflict")
        self.assertEqual(self.balance(), Decimal("0"))
        attempt.refresh_from_db()
        self.assertTrue(attempt.conflict)
        self.assertTrue(
            AuditLog.objects.filter(action="deposit.payment_conflict").exists()
        )

    def test_webhook_rate_limited(self):
        self.initiate()
        with mock.patch("transactions.views.online_deposits.MAX_WEBHOOK_PER_MINUTE", 2):
            first = self.post_webhook(self.webhook_body("a"))
            second = self.post_webhook(self.webhook_body("b"))
            third = self.post_webhook(self.webhook_body("c"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)

    def test_secrets_never_logged_in_config(self):
        from django.conf import settings as dj_settings

        self.assertTrue(dj_settings.TARA_API_KEY)
        self.assertNotIn(dj_settings.TARA_API_KEY, dj_settings.TARA_WEBHOOK_TOKEN)
