import logging

logger = logging.getLogger('core')


class SmsProvider:
    def send(self, phone_number, message):
        raise NotImplementedError

    def send_otp(self, phone_number, code):
        message = f"Votre code de vérification PAYIA est: {code}. Valable 5 minutes."
        return self.send(phone_number, message)


class ConsoleSmsProvider(SmsProvider):
    def send(self, phone_number, message):
        logger.info(f"[SMS] To: {phone_number} | Message: {message}")
        print(f"[SMS] To: {phone_number} | Message: {message}")
        return True


class MockSmsProvider(SmsProvider):
    def send(self, phone_number, message):
        logger.info(f"[SMS-MOCK] To: {phone_number} | Message: {message}")
        return True


def get_sms_provider():
    from django.conf import settings
    provider_name = getattr(settings, 'SMS_PROVIDER', 'console')
    providers = {
        'console': ConsoleSmsProvider,
        'mock': MockSmsProvider,
    }
    provider_class = providers.get(provider_name, ConsoleSmsProvider)
    return provider_class()
