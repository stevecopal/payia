"""Automatisation des depots avec Tara Money.

Responsabilites :
- creer une demande de depot + une ou plusieurs tentatives de paiement ;
- generer le lien de paiement et rediriger l'utilisateur ;
- recevoir / relancer les notifications (webhooks) ;
- **verifier toujours cote prestataire** avant tout credit ;
- crediter le portefeuille existant de facon atomique et idempotente ;
- reconcilier les webhooks non recus (Tara ne rejoue jamais un webhook).

Regles non negociables :
- aucune decision financiere ne vient du navigateur (redirection, JS) ;
- un credit n'est effectue que si l'API de statut Tara repond SUCCESS ;
- au plus un credit par `Deposit` (contrainte SQL + verrous).
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from core.middleware import RateLimitStore
from core.models import AuditLog, Setting
from notifications.models import Notification
from transactions.models import Deposit, DepositAttempt, PaymentEvent, PaymentMethod
from transactions.services.deposit_service import DepositService
from transactions.services.tara_service import TaraApiError, TaraClient

logger = logging.getLogger("transactions")
security_logger = logging.getLogger("security")
payments_logger = logging.getLogger("payments")

RECONCILE_INTERVAL = 60
# Anti double-clic : on ne redemande pas un debit direct au prestataire
# avant ce delai sur la meme tentative.
PUSH_DEBOUNCE_SECONDS = 60
# Fenetre de recherche des tentatives a partir d'un webhook sans reference.
PHONE_LOOKUP_HOURS = 24
PHONE_LOOKUP_LIMIT = 3


class OnlineDepositService:
    PROVIDER = "tara"
    PAYMENT_METHOD_SLUG = "tara-money"
    # ------------------------------------------------------------------
    # Moyens de paiement proposes a l'utilisateur (contrat Tara Money)
    # ------------------------------------------------------------------
    CHANNELS = {
        DepositAttempt.Channel.MOMO: {
            "label": "MTN / Orange Mobile Money",
            "description": "Le debit est effectue directement sur votre numero.",
            "network": "",
            "kind": "push",
            "icon": "icons/mobile.jpeg",
        },
        DepositAttempt.Channel.WAVE: {
            "label": "Wave",
            "description": "Le debit est effectue directement sur votre compte Wave.",
            "network": "wave",
            "kind": "push",
            "icon": "icons/wave.png",
        },
        DepositAttempt.Channel.CARD: {
            "label": "Carte bancaire",
            "description": "Vous etes redirige vers la page securisee Tara Money.",
            "network": "",
            "kind": "link",
            "icon": "icons/carte.jpeg",
        },
    }

    # ------------------------------------------------------------------
    # Configuration / limites
    # ------------------------------------------------------------------
    @classmethod
    def available_channels(cls):
        """Moyens de paiement Tara Money proposés dans le formulaire de depot.

        `value` est la valeur transmise par le formulaire (`online:<slug>`),
        ce qui permet de distinguer un moyen Tara Money d'une methode de
        paiement manuelle dans la meme liste de choix.
        """
        return [
            {"slug": slug, "value": f"online:{slug}", "kind": cfg["kind"], **cfg}
            for slug, cfg in cls.CHANNELS.items()
        ]

    @classmethod
    def channel_config(cls, channel):
        config = cls.CHANNELS.get(str(channel or ""))
        if config is None:
            raise ValueError("Moyen de paiement invalide.")
        return config

    @staticmethod
    def provider_phone_number(phone):
        """Forme attendue par l'API Tara : 2376XXXXXXXX."""
        digits = re.sub(r"\D", "", str(phone or ""))
        if len(digits) == 9 and digits.startswith("6"):
            return f"237{digits}"
        return digits

    @staticmethod
    def get_payment_method():
        try:
            return PaymentMethod.objects.get(
                slug=OnlineDepositService.PAYMENT_METHOD_SLUG, is_active=True
            )
        except PaymentMethod.DoesNotExist:
            raise ValueError("Le paiement en ligne n'est pas active sur le site.")

    @classmethod
    def is_available(cls):
        return TaraClient.is_configured() and PaymentMethod.objects.filter(
            slug=OnlineDepositService.PAYMENT_METHOD_SLUG, is_active=True
        ).exists()

    @classmethod
    def filter_available(cls, payment_methods):
        """Exclut le paiement en ligne quand il n'est pas configurable."""
        if TaraClient.is_configured():
            return payment_methods
        return payment_methods.exclude(
            slug=OnlineDepositService.PAYMENT_METHOD_SLUG
        )

    @classmethod
    def get_deposit_limits(cls, payment_method=None):
        min_amount = Setting.get_setting("minimum_deposit", None)
        if min_amount in (None, ""):
            min_amount = settings.TARA_DEPOSIT_MIN
        max_amount = Setting.get_setting("maximum_deposit", None)
        if max_amount in (None, ""):
            max_amount = settings.TARA_DEPOSIT_MAX
        try:
            min_amount = Decimal(str(min_amount))
        except (InvalidOperation, TypeError, ValueError):
            min_amount = Decimal(str(settings.TARA_DEPOSIT_MIN))
        try:
            max_amount = Decimal(str(max_amount))
        except (InvalidOperation, TypeError, ValueError):
            max_amount = Decimal(str(settings.TARA_DEPOSIT_MAX))

        if payment_method is not None:
            if payment_method.min_amount is not None and payment_method.min_amount > min_amount:
                min_amount = payment_method.min_amount
            if payment_method.max_amount is not None and payment_method.max_amount < max_amount:
                max_amount = payment_method.max_amount
        return min_amount, max_amount

    @classmethod
    def validate_amount(cls, amount, payment_method=None):
        """Valide le montant cote serveur (entier XAF, bornes min/max)."""
        if payment_method is None:
            payment_method = cls.get_payment_method()
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Le montant est invalide.")
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Le montant doit etre superieur a 0.")
        if amount != amount.to_integral_value():
            raise ValueError("Le montant doit etre un nombre entier en XAF.")

        min_amount, max_amount = cls.get_deposit_limits(payment_method)
        if amount < min_amount:
            raise ValueError(f"Le montant minimum est {min_amount} XAF.")
        if amount > max_amount:
            raise ValueError(f"Le montant maximum est {max_amount} XAF.")
        return amount

    # ------------------------------------------------------------------
    # Limitation de debit (reutilise RateLimitStore de core.middleware)
    # ------------------------------------------------------------------
    @classmethod
    def allow_request(cls, scope, key, max_requests, window):
        store_key = f"tara:{scope}:{key}"
        if len(RateLimitStore.get_requests(store_key, window)) >= max_requests:
            security_logger.warning("Rate limit Tara (%s) depasse: %s", scope, key)
            return False
        RateLimitStore.add_request(store_key)
        return True

    # ------------------------------------------------------------------
    # URLs
    # ------------------------------------------------------------------
    @staticmethod
    def _site_base():
        return (settings.TARA_SITE_BASE_URL or "").rstrip("/")

    @classmethod
    def webhook_url(cls):
        url = f"{cls._site_base()}/webhooks/tara/"
        token = settings.TARA_WEBHOOK_TOKEN
        if token:
            url = f"{url}?token={token}"
        return url

    @classmethod
    def return_url(cls, deposit):
        return f"{cls._site_base()}/transactions/deposits/{deposit.pk}/payment-result/"

    @classmethod
    def _check_webhook_token(cls, request):
        provided = request.GET.get("token", "") or request.headers.get("X-Tara-Webhook-Token", "")
        expected = settings.TARA_WEBHOOK_TOKEN
        if not expected:
            security_logger.warning(
                "Webhook Tara rejete: TARA_WEBHOOK_TOKEN non configure (aucun credit possible)."
            )
            return False
        if not provided:
            security_logger.warning("Webhook Tara rejete: jeton absent.")
            return False
        if not constant_time_compare(str(provided), str(expected)):
            security_logger.warning("Webhook Tara rejete: jeton invalide.")
            return False
        return True

    # ------------------------------------------------------------------
    # Initiation d'un depot en ligne
    # ------------------------------------------------------------------
    @classmethod
    def initiate(cls, user, amount, phone_number="", channel=DepositAttempt.Channel.CARD,
                 ip_address=None):
        """Cree (ou reutilise) un depot en attente et lance le paiement.

        Deux familles de canaux :
        - `push` (Mobile Money / Wave) : Tara Money demande le debit sur le
          numero, `redirect_url` est alors vide ou l'URL d'authentification ;
        - `link` : redirection vers la page de paiement Tara Money.

        Retourne `(deposit, attempt, redirect_url)`.
        """
        if not TaraClient.is_configured():
            raise ValueError("Le paiement en ligne n'est pas encore disponible.")

        config = cls.channel_config(channel)
        payment_method = cls.get_payment_method()
        amount = cls.validate_amount(amount, payment_method)

        normalized_phone = ""
        if phone_number:
            normalized_phone = DepositService.validate_phone(phone_number)
            if not normalized_phone:
                raise ValueError("Numero de telephone invalide. Format attendu: 6XXXXXXXX.")
        elif config["kind"] == "push":
            raise ValueError("Le numero de telephone a debiter est obligatoire.")

        deposit = cls._get_or_create_deposit(
            user=user,
            amount=amount,
            payment_method=payment_method,
            phone_number=normalized_phone,
            ip_address=ip_address,
        )
        attempt = cls._get_or_create_attempt(deposit, channel)
        redirect_url = cls._launch(deposit, attempt, config)
        return deposit, attempt, redirect_url


    @classmethod
    def _get_or_create_deposit(cls, user, amount, payment_method, phone_number, ip_address):
        reuse_window = timedelta(seconds=max(0, int(settings.TARA_REUSE_WINDOW)))
        with transaction.atomic():
            existing = (
                Deposit.objects.select_for_update()
                .filter(
                    user=user,
                    payment_method=payment_method,
                    amount=amount,
                    status=Deposit.Status.PENDING_REVIEW,
                    created_at__gte=timezone.now() - reuse_window,
                )
                .order_by("-created_at")
                .first()
            )
            if existing is not None:
                # Anti double-clic : on rejoue le depot deja ouvert.
                return existing

            deposit = Deposit.objects.create(
                user=user,
                amount=amount,
                payment_method=payment_method,
                transaction_id=f"TARA-{uuid.uuid4().hex}",
                phone_number=phone_number,
                ip_address=ip_address,
                status=Deposit.Status.PENDING_REVIEW,
            )
            Notification.objects.create(
                user=user,
                notification_type="DEPOSIT_SUBMITTED",
                title="Depot en ligne cree",
                message=(
                    f"Votre demande de depot de {amount} XAF est en cours. "
                    "Finalisez le paiement depuis le lien genere."
                ),
            )
            return deposit

    @classmethod
    def _get_or_create_attempt(cls, deposit, channel=DepositAttempt.Channel.CARD):
        config = cls.channel_config(channel)
        ttl = timedelta(seconds=max(60, int(settings.TARA_ATTEMPT_TTL)))
        for _ in range(3):
            with transaction.atomic():
                active = (
                    DepositAttempt.objects.select_for_update()
                    .filter(
                        deposit=deposit,
                        status=DepositAttempt.Status.PENDING,
                        expires_at__gt=timezone.now(),
                    )
                    .order_by("-created_at")
                    .first()
                )
                if active is not None and active.channel == channel:
                    return active
                try:
                    return DepositAttempt.objects.create(
                        deposit=deposit,
                        reference=f"payia_{uuid.uuid4().hex}",
                        amount=deposit.amount,
                        expires_at=timezone.now() + ttl,
                        channel=channel,
                        network=config.get("network", ""),
                    )
                except IntegrityError:
                    continue
        raise ValueError("Impossible de creer une tentative de paiement. Reessayez.")

    @classmethod
    def _launch(cls, deposit, attempt, config):
        """Declenche le paiement selon le canal choisi. Retourne l'URL."""
        if config["kind"] == "link":
            return cls._ensure_payment_link(deposit, attempt)
        return cls._launch_push(deposit, attempt)

    @classmethod
    def _launch_push(cls, deposit, attempt, force=False):
        """Demande a Tara Money de debiter le numero du payeur.

        L'utilisateur valide ensuite la demande (USSD) sur son telephone.
        Retourne l'URL d'authentification du prestataire (Wave) ou une
        chaine vide : le paiement se poursuit alors sur le telephone.
        """
        if attempt.status != DepositAttempt.Status.PENDING:
            raise ValueError("Cette tentative est cloturee. Lancez un nouveau paiement.")

        now = timezone.now()
        if (
            not force
            and attempt.launched_at
            and (now - attempt.launched_at).total_seconds() < PUSH_DEBOUNCE_SECONDS
        ):
            # Double-clic : la demande est deja partie vers le payeur.
            return attempt.provider_payload.get("auth_url", "") if isinstance(
                attempt.provider_payload, dict
            ) else ""

        provider_phone = cls.provider_phone_number(deposit.phone_number)
        if not provider_phone:
            raise ValueError("Le numero de telephone a debiter est obligatoire.")

        try:
            result = TaraClient.mobilepay(
                product_id=attempt.reference,
                product_name=f"Depot PAYIA #{deposit.pk}",
                product_price=int(deposit.amount),
                phone_number=provider_phone,
                network=attempt.network,
                web_hook_url=cls.webhook_url(),
            )
        except TaraApiError as exc:
            # Etat inconnu : la tentative reste ouverte et verifiable.
            logger.error(
                "Demande de debit Tara en echec (depot=%s, tentative=%s): %s",
                deposit.pk, attempt.reference, str(exc)[:200],
            )
            raise ValueError(
                "Impossible de lancer le paiement pour le moment. "
                "Reessayez dans un instant."
            ) from exc

        if result["status"] != "SUCCESS":
            reason = result["message"] or "Demande refusee par Tara Money."
            attempt.mark_failure(reason=reason, payload=result.get("raw"))
            logger.warning(
                "Debit direct refuse par Tara (tentative=%s, statut=%s): %s",
                attempt.reference, result["status"], reason[:200],
            )
            raise ValueError(f"Le paiement n'a pas pu etre lance : {reason[:150]}")

        attempt.vendor = result["vendor"]
        attempt.launched_at = now
        attempt.provider_payload = {
            "mobilepay": result.get("raw") or {},
            "auth_url": result["auth_url"],
            "vendor": result["vendor"],
        }
        attempt.save(update_fields=[
            "vendor", "launched_at", "provider_payload", "updated_at",
        ])
        payments_logger.info(
            "Debit direct lance (depot=%s, tentative=%s, operateur=%s)",
            deposit.pk, attempt.reference, result["vendor"] or "inconnu",
        )
        return result["auth_url"]

    @classmethod
    def _ensure_payment_link(cls, deposit, attempt):
        if attempt.pay_url:
            return attempt.pay_url
        if attempt.status != DepositAttempt.Status.PENDING:
            raise ValueError("Cette tentative est cloturee. Lancez un nouveau paiement.")

        try:
            result = TaraClient.create_payment_link(
                product_id=attempt.reference,
                product_name=f"Depot PAYIA #{deposit.pk}",
                product_price=int(deposit.amount),
                product_description=f"Recharge du portefeuille PAYIA - demande #{deposit.pk}",
                web_hook_url=cls.webhook_url(),
                return_url=cls.return_url(deposit),
            )
        except TaraApiError as exc:
            attempt.refresh_from_db(fields=["pay_url", "status"])
            if attempt.pay_url:
                return attempt.pay_url
            if attempt.status == DepositAttempt.Status.PENDING:
                attempt.mark_failure(reason=str(exc))
            logger.error(
                "Creation du lien Tara en echec (deposit=%s, tentative=%s): %s",
                deposit.pk, attempt.reference, str(exc)[:200],
            )
            raise ValueError(
                "Impossible de generer le lien de paiement pour le moment. "
                "Reessayez dans un instant."
            ) from exc

        attempt.pay_url = result["general_link"]
        attempt.links = result.get("links", {})
        attempt.save(update_fields=["pay_url", "links", "updated_at"])
        return attempt.pay_url

    @classmethod
    def retry(cls, deposit, user):
        """Nouvelle tentative de paiement pour un depot toujours en attente.

        Le canal de la derniere tentative est conserve : on relance un
        debit direct ou un lien de paiement selon le choix initial.
        """
        if deposit.user_id != user.pk:
            raise ValueError("Ce depot ne vous appartient pas.")
        if deposit.status != Deposit.Status.PENDING_REVIEW:
            raise ValueError("Ce depot n'est plus en attente de paiement.")
        latest = deposit.attempts.order_by("-created_at").first()
        channel = latest.channel if latest is not None else DepositAttempt.Channel.CARD
        attempt = cls._get_or_create_attempt(deposit, channel)
        if attempt.is_push:
            redirect_url = cls._launch_push(deposit, attempt, force=True)
        else:
            redirect_url = cls._ensure_payment_link(deposit, attempt)
        return attempt, redirect_url


    # ------------------------------------------------------------------
    # Verification cote prestataire + credit
    # ------------------------------------------------------------------
    @classmethod
    def verify_attempt(cls, reference, source="user", min_interval=None):
        """Interroge Tara et applique le statut. Retourne le resultat."""
        attempt = DepositAttempt.objects.filter(reference=reference).first()
        if attempt is None:
            return "unknown"

        if min_interval is None:
            min_interval = max(0, int(settings.TARA_STATUS_THROTTLE))
        if min_interval and attempt.last_checked_at:
            elapsed = (timezone.now() - attempt.last_checked_at).total_seconds()
            if elapsed < min_interval:
                return "throttled"

        try:
            provider_status = TaraClient.get_transaction_status(reference)
        except TaraApiError as exc:
            # Verification impossible : AUCUN credit, on reessaiera plus tard.
            logger.warning(
                "Verification Tara impossible (tentative=%s): %s",
                reference, str(exc)[:200],
            )
            attempt.touch_checked()
            return "unverified"

        return cls.apply_provider_status(
            reference, provider_status, source=source, payload=None
        )

    @classmethod
    def apply_provider_status(cls, reference, provider_status, payment_id="",
                              payload=None, source="webhook"):
        """Applique un statut **deja confirme** aupres du prestataire."""
        provider_status = str(provider_status or "").strip().upper()
        attempt = (
            DepositAttempt.objects.select_related(
                "deposit", "deposit__user", "deposit__payment_method"
            )
            .filter(reference=reference)
            .first()
        )
        if attempt is None:
            logger.warning("Statut Tara pour une reference inconnue: %s", str(reference)[:80])
            return "unknown"

        if provider_status == "SUCCESS":
            if attempt.status == DepositAttempt.Status.SUCCESS:
                # Notification repetee ou tardive : sans effet financier.
                return "already_credited"
            return cls._credit_confirmed(attempt, payment_id=payment_id,
                                         payload=payload, source=source)

        if provider_status == "FAILURE":
            if attempt.status == DepositAttempt.Status.SUCCESS or attempt.conflict:
                # Notification tardive/incoherente : aucun effet financier.
                attempt.touch_checked()
                return "ignored"
            attempt.mark_failure(payload=payload)
            logger.info("Tentative Tara echouee: %s", attempt.reference)
            return "failed"

        # PENDING ou statut inconnu : on ne touche a rien.
        attempt.touch_checked()
        return "pending"

    @classmethod
    def _credit_confirmed(cls, attempt, payment_id="", payload=None, source="webhook"):
        """Credit unique et atomique du portefeuille apres confirmation Tara."""
        if payload:
            mismatch = cls._amount_mismatch(attempt.deposit, payload)
            if mismatch:
                cls._log_amount_conflict(attempt.deposit, attempt, mismatch, source)
                return "amount_mismatch"

        try:
            with transaction.atomic():
                attempt = (
                    DepositAttempt.objects.select_for_update()
                    .select_related("deposit")
                    .get(pk=attempt.pk)
                )
                deposit = (
                    Deposit.objects.select_for_update()
                    .select_related("user", "payment_method")
                    .get(pk=attempt.deposit_id)
                )

                if attempt.status == DepositAttempt.Status.SUCCESS:
                    # Idempotence : deja credite.
                    return "already_credited"

                if deposit.status != Deposit.Status.PENDING_REVIEW:
                    # Depot deja rejete/traite par ailleurs : paiement confirme
                    # mais non credite automatiquement -> reconciliation manuelle.
                    cls._mark_conflict(attempt, deposit, source)
                    return "conflict"

                if payload:
                    mismatch = cls._amount_mismatch(deposit, payload)
                    if mismatch:
                        attempt.touch_checked()
                        cls._log_amount_conflict(deposit, attempt, mismatch, source)
                        return "amount_mismatch"

                try:
                    # Savepoint : si une autre tentative a deja credite ce
                    # depot, la contrainte unique echoue sans casser la
                    # transaction englobante.
                    with transaction.atomic():
                        attempt.mark_success(payment_id=payment_id, payload=payload)
                except IntegrityError:
                    cls._mark_conflict(attempt, deposit, source)
                    security_logger.critical(
                        "Double credit evite pour la tentative %s : le depot "
                        "etait deja credite par une autre tentative.",
                        attempt.reference,
                    )
                    return "conflict"

                DepositService.approve_deposit(deposit, admin_user=None, source=source)

                payments_logger.info(
                    "Depot %s credite automatiquement (tentative=%s, source=%s, montant=%s)",
                    deposit.pk, attempt.reference, source, deposit.amount,
                )
                return "credited"
        except IntegrityError:  # pragma: no cover - filet de securite
            cls._mark_conflict_by_pk(attempt.pk, source)
            security_logger.critical(
                "Double credit evite pour la tentative %s : le depot avait deja "
                "ete credite par une autre tentative.", attempt.reference,
            )
            return "conflict"

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------
    @classmethod
    def handle_webhook(cls, request):
        """Traite une notification Tara. Retourne `(http_status, payload)`."""
        if not cls._check_webhook_token(request):
            return 401, {"detail": "unauthorized"}

        try:
            body = request.body
        except Exception:  # pragma: no cover - corps illisible
            body = b""
        try:
            parsed = json.loads(body.decode("utf-8") if body else "")
        except (ValueError, UnicodeDecodeError):
            return 400, {"detail": "invalid_json"}

        elements = parsed if isinstance(parsed, list) else [parsed]
        elements = [el for el in elements if isinstance(el, dict)]
        if not elements:
            return 400, {"detail": "invalid_payload"}

        summary = {"received": len(elements), "processed": 0, "duplicate": 0,
                   "ignored": 0, "credited": 0}
        for element in elements:
            try:
                outcome = cls._process_webhook_element(element)
            except Exception:
                # Aucun credit n'a ete effectue : la reconciliation reprendra.
                logger.exception(
                    "Erreur inattendue lors du traitement d'un webhook Tara."
                )
                outcome = "error"
            if outcome == "duplicate":
                summary["duplicate"] += 1
            elif outcome == "credited":
                summary["processed"] += 1
                summary["credited"] += 1
            elif outcome in ("failed", "pending"):
                summary["processed"] += 1
            else:
                summary["ignored"] += 1
        return 200, summary

    @classmethod
    def _process_webhook_element(cls, element):
        event_id = hashlib.sha256(
            json.dumps(element, sort_keys=True, separators=(",", ":"),
                       default=str).encode("utf-8")
        ).hexdigest()

        try:
            with transaction.atomic():
                event = PaymentEvent.objects.create(
                    event_id=event_id,
                    provider=cls.PROVIDER,
                    event_type="payment",
                    payload=element,
                )
        except IntegrityError:
            # Notification deja recue : sans effet financier.
            return "duplicate"

        business_id = str(element.get("businessId") or "").strip()
        if settings.TARA_BUSINESS_ID and business_id != settings.TARA_BUSINESS_ID:
            security_logger.warning(
                "Webhook Tara ignore: businessId inattendu (%s).", business_id[:50]
            )
            return "ignored_wrong_business"

        reference = str(element.get("productId") or "").strip()
        if not reference:
            # Certaines variantes mobilepay arrivent sans productId ni montant :
            # impossible d'associer la notification a une tentative sans
            # ambiguite. Aucun credit ici : la reconciliation periodique
            # interroge Tara et credite les tentatives reellement confirmees.
            return cls._process_webhook_without_reference(element, event)


        attempt = (
            DepositAttempt.objects.select_related(
                "deposit", "deposit__user", "deposit__payment_method"
            )
            .filter(reference=reference)
            .first()
        )
        if attempt is None:
            logger.warning("Webhook Tara pour une reference inconnue: %s", reference[:80])
            return "ignored_unknown_reference"

        if element.get("amount") not in (None, ""):
            mismatch = cls._amount_mismatch(attempt.deposit, element)
            if mismatch:
                cls._log_amount_conflict(attempt.deposit, attempt, mismatch, "webhook")
                security_logger.warning(
                    "Webhook Tara montant incoherent (tentative=%s).", reference
                )
                return "amount_mismatch"

        try:
            provider_status = TaraClient.get_transaction_status(reference)
        except TaraApiError as exc:
            # Statut non verifiable : aucun credit, la reconciliation reprend.
            logger.warning(
                "Webhook Tara non verifiable (tentative=%s): %s",
                reference, str(exc)[:200],
            )
            event.mark_processed()  # deja enregistre, sans effet financier
            return "unverified"

        outcome = cls.apply_provider_status(
            reference,
            provider_status,
            payment_id=str(element.get("paymentId") or ""),
            payload=element,
            source="webhook",
        )
        if outcome in ("credited", "failed", "pending", "already_credited"):
            event.mark_processed()
        return outcome

    @classmethod
    def _process_webhook_without_reference(cls, element, event):
        """Webhook sans productId : journalise sans jamais crediter directement.

        Le numero debite ne suffit pas a identifier de facon certaine la
        tentative concernee (plusieurs tentatives possibles, montant absent).
        On enregistre la notification puis on laisse la reconciliation
        interroger Tara : le credit n'est applique qu'apres confirmation du
        prestataire sur la reference exacte.
        """
        raw_phone = element.get("phoneNumber") or element.get("phone") or ""
        digits = re.sub(r"\D", "", str(raw_phone))
        phone = digits[-9:] if len(digits) >= 9 else ""
        logger.warning(
            "Webhook Tara sans productId (numero=%s) : aucune association "
            "certaine, credit laisse a la reconciliation.",
            ("*" * 5 + phone[-4:]) if phone else "inconnu",
        )
        event.mark_processed()
        return "ignored_no_reference"

    # ------------------------------------------------------------------
    # Reconciliation / expiration
    # ------------------------------------------------------------------
    @classmethod
    def reconcile(cls, batch=None, lookback_hours=None, interval=RECONCILE_INTERVAL):
        """Verifie aupres de Tara les tentatives sans webhook confirme."""
        if not TaraClient.is_configured():
            return {"checked": 0, "credited": 0, "failed": 0, "errors": 0,
                    "disabled": True}

        batch = batch or int(settings.TARA_RECONCILE_BATCH)
        lookback_hours = lookback_hours or int(settings.TARA_RECONCILE_LOOKBACK_HOURS)
        now = timezone.now()
        cutoff = now - timedelta(hours=lookback_hours)

        qs = (
            DepositAttempt.objects
            .filter(
                status__in=[DepositAttempt.Status.PENDING, DepositAttempt.Status.EXPIRED],
                created_at__gte=cutoff,
                conflict=False,
            )
            .filter(Q(last_checked_at__isnull=True) | Q(last_checked_at__lte=now - timedelta(seconds=interval)))
            .select_related("deposit")
            .order_by(F("last_checked_at").asc(nulls_first=True), "created_at")
        )[:max(1, batch)]

        stats = {"checked": 0, "credited": 0, "failed": 0, "errors": 0}
        for attempt in qs:
            stats["checked"] += 1
            try:
                status = TaraClient.get_transaction_status(attempt.reference)
            except TaraApiError:
                stats["errors"] += 1
                continue
            outcome = cls.apply_provider_status(
                attempt.reference, status, source="reconcile", payload=None
            )
            if outcome == "credited":
                stats["credited"] += 1
            elif outcome == "failed":
                stats["failed"] += 1
        if stats["checked"]:
            logger.info("Reconciliation Tara: %s", stats)
        return stats

    @classmethod
    def expire_attempts(cls, batch=200):
        """Marque expirees les tentatives dont la duree de vie est passee."""
        now = timezone.now()
        expired = list(
            DepositAttempt.objects.filter(
                status=DepositAttempt.Status.PENDING, expires_at__lt=now
            ).values_list("pk", flat=True)[:batch]
        )
        if expired:
            DepositAttempt.objects.filter(pk__in=expired).update(
                status=DepositAttempt.Status.EXPIRED, updated_at=now
            )
            logger.info("%s tentative(s) Tara expiree(s).", len(expired))
        return len(expired)

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------
    @staticmethod
    def _amount_mismatch(deposit, payload):
        raw = payload.get("amount")
        if raw in (None, ""):
            return None
        try:
            received = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return str(raw)
        if received != Decimal(str(deposit.amount)):
            return str(raw)
        return None

    @staticmethod
    def _log_amount_conflict(deposit, attempt, received, source):
        AuditLog.objects.create(
            actor=None,
            action="deposit.amount_mismatch",
            target_type="Deposit",
            target_id=str(deposit.pk),
            description=(
                f"Notification {source} avec montant {received} alors que "
                f"{deposit.amount} XAF attendus (tentative {attempt.reference}). "
                "Aucun credit effectue."
            ),
            metadata={
                "attempt": attempt.reference,
                "source": source,
                "received": received,
                "expected": str(deposit.amount),
            },
        )
        security_logger.warning(
            "Montant incoherent depot=%s attendu=%s recu=%s source=%s",
            deposit.pk, deposit.amount, received, source,
        )

    @staticmethod
    def _mark_conflict(attempt, deposit, source):
        attempt.conflict = True
        attempt.last_checked_at = timezone.now()
        attempt.save(update_fields=["conflict", "last_checked_at", "updated_at"])
        OnlineDepositService._write_conflict_audit(deposit, attempt, source)
        security_logger.critical(
            "Paiement Tara confirme mais non credite (depot=%s, tentative=%s, "
            "statut depot=%s, source=%s).",
            deposit.pk, attempt.reference, deposit.status, source,
        )

    @classmethod
    def _mark_conflict_by_pk(cls, attempt_pk, source):
        attempt = DepositAttempt.objects.select_related("deposit").filter(pk=attempt_pk).first()
        if attempt is None:
            return
        cls._mark_conflict(attempt, attempt.deposit, source)

    @staticmethod
    def _write_conflict_audit(deposit, attempt, source):
        AuditLog.objects.create(
            actor=None,
            action="deposit.payment_conflict",
            target_type="Deposit",
            target_id=str(deposit.pk),
            description=(
                f"Paiement confirme par Tara Money pour la tentative "
                f"{attempt.reference} mais credit automatique impossible "
                f"(source={source}, statut depot={deposit.status}). "
                "Reconciliation manuelle requise."
            ),
            metadata={
                "attempt": attempt.reference,
                "source": source,
                "deposit_status": deposit.status,
                "amount": str(deposit.amount),
            },
        )
