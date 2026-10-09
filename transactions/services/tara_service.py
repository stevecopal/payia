"""Client HTTP de l'API Tara Money (cote serveur uniquement).

Contrats utilises (documentation Tara Money) :

- Debit direct Mobile Money : POST {base}/mobilepay
- Creation de lien de paiement : POST {base}/paymentlinks
- Statut d'une transaction      : POST {base}/transactions/status
- Renvoi de webhook             : POST {base}/resend-webhook

Les credentials (apiKey, businessId) ne sont jamais journalises ni renvoyes
dans une reponse applicative. Toute erreur reseau est convertie en
`TaraApiError` afin que l'appelant ne creditte jamais sur une reponse
incertaine.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger("payments")

VALID_TRANSACTION_STATUSES = ("SUCCESS", "FAILURE", "PENDING")


class TaraApiError(Exception):
    """Erreur reseau, HTTP ou format inattendu de l'API Tara Money."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class TaraClient:
    @staticmethod
    def is_configured():
        return bool(settings.TARA_API_KEY and settings.TARA_BUSINESS_ID)

    @staticmethod
    def _base_url():
        return (settings.TARA_API_BASE_URL or "").rstrip("/")

    @classmethod
    def _timeout(cls):
        try:
            return max(1, int(settings.TARA_HTTP_TIMEOUT))
        except (TypeError, ValueError):
            return 15

    @classmethod
    def _post(cls, path, payload, timeout=None):
        """POST JSON vers Tara. Ne journalise jamais la charge utile."""
        if not cls.is_configured():
            raise TaraApiError("Configuration Tara Money manquante (apiKey/businessId).")

        url = f"{cls._base_url()}{path}"
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=timeout or cls._timeout(),
            )
        except requests.Timeout:
            logger.error("Tara API timeout: %s", path)
            raise TaraApiError(f"Timeout vers Tara Money ({path}).")
        except requests.RequestException as exc:
            logger.error("Tara API reseau en echec: %s (%s)", path, exc.__class__.__name__)
            raise TaraApiError(f"Reseau indisponible vers Tara Money ({path}).")

        if response.status_code >= 400:
            logger.error(
                "Tara API HTTP %s sur %s", response.status_code, path
            )
            raise TaraApiError(
                f"Tara Money a repondu HTTP {response.status_code}.",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError:
            logger.error("Tara API reponse non-JSON sur %s", path)
            raise TaraApiError("Reponse invalide de Tara Money.")

        if not isinstance(data, dict):
            logger.error("Tara API reponse inattendue sur %s", path)
            raise TaraApiError("Reponse invalide de Tara Money.")
        return data

    @classmethod
    def create_payment_link(
        cls,
        *,
        product_id,
        product_name,
        product_price,
        product_description,
        web_hook_url,
        return_url="",
        product_picture_url="",
    ):
        """Cree un lien de paiement. Retourne les liens exploitables.

        `product_price` doit etre un entier en FCFA (contrat Tara).
        """
        try:
            price = int(product_price)
        except (TypeError, ValueError):
            raise TaraApiError("Montant non entier pour Tara Money.")
        if price <= 0:
            raise TaraApiError("Montant invalide pour Tara Money.")
        if not web_hook_url:
            raise TaraApiError("webHookUrl obligatoire pour Tara Money.")

        payload = {
            "apiKey": settings.TARA_API_KEY,
            "businessId": settings.TARA_BUSINESS_ID,
            "productId": product_id,
            "productName": str(product_name)[:180],
            "productPrice": price,
            "productDescription": str(product_description)[:500],
            "webHookUrl": web_hook_url,
        }
        if return_url:
            payload["returnUrl"] = return_url
        if product_picture_url:
            payload["productPictureUrl"] = product_picture_url

        data = cls._post("/paymentlinks", payload)

        status = str(data.get("status", "")).lower()
        links = {
            key: str(data.get(key) or "")
            for key in (
                "generalLink", "whatsappLink", "telegramLink",
                "dikaloLink", "cardLink", "smsLink",
            )
            if data.get(key)
        }
        general_link = links.get("generalLink", "")

        if status not in ("success", "ok") or not general_link:
            message = str(data.get("message") or data.get("status") or "echec")
            logger.error("Tara paymentlinks refuse: %s", message[:200])
            raise TaraApiError(f"Creation du lien de paiement refusee ({message[:120]}).")

        return {"links": links, "general_link": general_link, "raw": data}

    @classmethod
    def mobilepay(
        cls,
        *,
        product_id,
        product_name,
        product_price,
        phone_number,
        web_hook_url,
        network="",
    ):
        """Lance un debit direct sur le numero Mobile Money du payeur.

        Contrat Tara Money : POST {base}/mobilepay
        Le payeur valide la demande sur son telephone (USSD). Retourne un
        dict exploitable `{"status", "vendor", "auth_url", "message", "raw"}`.
        Un refus (`status != SUCCESS`) n'est pas une erreur reseau : c'est
        l'appelant qui decide de marquer la tentative en echec.
        """
        try:
            price = int(product_price)
        except (TypeError, ValueError):
            raise TaraApiError("Montant non entier pour Tara Money.")
        if price <= 0:
            raise TaraApiError("Montant invalide pour Tara Money.")
        if not web_hook_url:
            raise TaraApiError("webHookUrl obligatoire pour Tara Money.")
        digits = str(phone_number or "").replace(" ", "").replace("-", "")
        if not digits:
            raise TaraApiError("Numero de telephone obligatoire pour Tara Money.")

        payload = {
            "apiKey": settings.TARA_API_KEY,
            "businessId": settings.TARA_BUSINESS_ID,
            "productId": product_id,
            "productName": str(product_name)[:180],
            "network": str(network or ""),
            "productPrice": price,
            "phoneNumber": digits,
            "webHookUrl": web_hook_url,
        }

        data = cls._post("/mobilepay", payload)

        status = str(data.get("status") or "").strip().upper()
        return {
            "status": status,
            "vendor": str(data.get("vendor") or "")[:50],
            "auth_url": str(data.get("authUrl") or data.get("auth_url") or "")[:500],
            "message": str(data.get("message") or "")[:300],
            "raw": data,
        }

    @classmethod
    def get_transaction_status(cls, product_id):

        """Interroge le statut reel d'une transaction cote prestataire.

        Retourne SUCCESS / FAILURE / PENDING (ou un statut inconnu
        tel que renvoye par Tara, jamais interprete comme un succes).
        """
        if not product_id:
            raise TaraApiError("productId manquant.")

        payload = {
            "apiKey": settings.TARA_API_KEY,
            "businessId": settings.TARA_BUSINESS_ID,
            "productId": product_id,
        }
        data = cls._post("/transactions/status", payload)
        status = str(data.get("status") or "").strip().upper()
        if not status:
            logger.error("Tara transactions/status sans statut pour %s", product_id)
            raise TaraApiError("Statut absent de la reponse Tara Money.")
        return status

    @classmethod
    def resend_webhook(cls, product_id):
        """Declenche le reenvoi du webhook pour un produit (recuperation).

        Utilise uniquement comme mecanisme de secours : Tara Money ne
        rejoue pas automatiquement les webhooks en echec.
        """
        payload = {
            "apiKey": settings.TARA_API_KEY,
            "businessId": settings.TARA_BUSINESS_ID,
            "productId": product_id,
        }
        return cls._post("/resend-webhook", payload)
