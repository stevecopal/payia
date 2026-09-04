import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

CAMEROON_PHONE_REGEX = re.compile(r'^\+2376\d{8}$')


def validate_cameroun_phone_number(value):
    normalized = normalize_phone_number(value)
    if not CAMEROON_PHONE_REGEX.match(normalized):
        raise ValidationError(
            _('Numéro de téléphone camerounais invalide. '
              'Le format attendu est +237 6XX XXX XXX.')
        )
    return normalized


def normalize_phone_number(value):
    cleaned = re.sub(r'[\s\-\(\)\.]+', '', str(value).strip())
    if cleaned.startswith('237') and not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    if not cleaned.startswith('+237'):
        if cleaned.startswith('6') and len(cleaned) == 9:
            cleaned = '+237' + cleaned
        elif cleaned.startswith('6') and len(cleaned) == 8:
            cleaned = '+2376' + cleaned
    return cleaned


def validate_phone_number(value):
    pattern = re.compile(r'^\+?[0-9]{10,15}$')
    if not pattern.match(value):
        raise ValidationError(_('Numéro de téléphone invalide.'))


def validate_file_size(value):
    max_size = 5 * 1024 * 1024
    if value.size > max_size:
        raise ValidationError(_('Le fichier ne doit pas dépasser 5Mo.'))


def validate_image_extension(value):
    allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
    ext = value.name.split('.')[-1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            _('Format de fichier non autorisé. Utilisez JPG, JPEG, PNG ou WEBP.')
        )


def validate_proof_file(value):
    validate_file_size(value)
    validate_image_extension(value)
