import time
import logging
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('security')


class RegistrationBlock:
    def __init__(self, key, blocked_until, level, reason):
        self.key = key
        self.blocked_until = blocked_until
        self.level = level
        self.reason = reason

    @property
    def is_active(self):
        return timezone.now() < self.blocked_until

    @property
    def remaining_seconds(self):
        now = timezone.now()
        if now >= self.blocked_until:
            return 0
        return int((self.blocked_until - now).total_seconds())

    @property
    def remaining_display(self):
        seconds = self.remaining_seconds
        if seconds < 60:
            return _('%(seconds)s seconde(s)') % {'seconds': seconds}
        minutes = seconds // 60
        if minutes < 60:
            return _('%(minutes)s minute(s)') % {'minutes': minutes}
        hours = minutes // 60
        return _('%(hours)s heure(s)') % {'hours': hours}


class RegistrationSecurityService:
    BLOCK_DURATIONS = [
        timedelta(minutes=15),
        timedelta(minutes=30),
        timedelta(hours=1),
        timedelta(hours=4),
        timedelta(hours=12),
        timedelta(hours=24),
    ]

    MAX_ATTEMPTS_PER_WINDOW = 5
    ATTEMPT_WINDOW_SECONDS = 3600

    _blocks = defaultdict(list)
    _attempt_counts = defaultdict(list)

    @classmethod
    def _get_block_key(cls, ip, phone=None, username=None):
        parts = [f'ip:{ip}']
        if phone:
            parts.append(f'phone:{phone}')
        if username:
            parts.append(f'username:{username.lower()}')
        return '|'.join(parts)

    @classmethod
    def _get_ip_key(cls, ip):
        return f'ip:{ip}'

    @classmethod
    def _get_phone_key(cls, phone):
        return f'phone:{phone}'

    @classmethod
    def _get_username_key(cls, username):
        return f'username:{username.lower()}'

    @classmethod
    def check_blocked(cls, ip, phone=None, username=None):
        now = timezone.now()
        keys_to_check = [cls._get_ip_key(ip)]
        if phone:
            keys_to_check.append(cls._get_phone_key(phone))
        if username:
            keys_to_check.append(cls._get_username_key(username))

        worst_block = None
        for key in keys_to_check:
            blocks = cls._blocks[key]
            cls._blocks[key] = [b for b in blocks if b > now]
            for block_time in cls._blocks[key]:
                level = cls._get_block_level(key, block_time)
                remaining = block_time - now
                if worst_block is None or remaining > (worst_block.blocked_until - now):
                    worst_block = RegistrationBlock(
                        key=key,
                        blocked_until=block_time,
                        level=level,
                        reason=cls._get_block_reason(level),
                    )
        return worst_block

    @classmethod
    def _get_block_level(cls, key, block_time):
        blocks = cls._blocks.get(key, [])
        for i, bt in enumerate(blocks):
            if bt == block_time:
                return min(i, len(cls.BLOCK_DURATIONS) - 1)
        return 0

    @classmethod
    def _get_block_reason(cls, level):
        reasons = [
            _('Nombre maximum de tentatives atteint. Réessayez dans 15 minutes.'),
            _('Comportement suspect détecté. Blocage de 30 minutes.'),
            _('Trop de tentatives répétées. Blocage de 1 heure.'),
            _('Activité abuseuse confirmée. Blocage prolongé.'),
            _('Violation grave des conditions d\'utilisation. Blocage de 12 heures.'),
            _('Blocage définitif en attente de révision admin.'),
        ]
        return reasons[min(level, len(reasons) - 1)]

    @classmethod
    def check_rate_limit(cls, ip, phone=None, username=None):
        now = time.time()
        keys = [cls._get_ip_key(ip)]
        if phone:
            keys.append(cls._get_phone_key(phone))
        if username:
            keys.append(cls._get_username_key(username))

        for key in keys:
            attempts = cls._attempt_counts.get(key, [])
            recent = [t for t in attempts if now - t < cls.ATTEMPT_WINDOW_SECONDS]
            cls._attempt_counts[key] = recent
            if len(recent) >= cls.MAX_ATTEMPTS_PER_WINDOW:
                return False, key
        return True, None

    @classmethod
    def record_attempt(cls, ip, phone=None, username=None, success=False):
        now = time.time()
        keys = [cls._get_ip_key(ip)]
        if phone:
            keys.append(cls._get_phone_key(phone))
        if username:
            keys.append(cls._get_username_key(username))

        for key in keys:
            if success:
                cls._attempt_counts.pop(key, None)
                cls._blocks.pop(key, None)
            else:
                cls._attempt_counts[key].append(now)
                attempts = [t for t in cls._attempt_counts[key]
                            if now - t < cls.ATTEMPT_WINDOW_SECONDS]
                cls._attempt_counts[key] = attempts

                if len(attempts) >= cls.MAX_ATTEMPTS_PER_WINDOW:
                    cls._apply_block(key, ip)

    @classmethod
    def _apply_block(cls, key, ip):
        now = timezone.now()
        existing_blocks = cls._blocks.get(key, [])
        existing_blocks = [b for b in existing_blocks if b > now]
        level = len(existing_blocks)
        if level < len(cls.BLOCK_DURATIONS):
            duration = cls.BLOCK_DURATIONS[level]
        else:
            duration = cls.BLOCK_DURATIONS[-1] * (level - len(cls.BLOCK_DURATIONS) + 2)

        blocked_until = now + duration
        existing_blocks.append(blocked_until)
        cls._blocks[key] = existing_blocks

        logger.warning(
            f'Registration block applied: key={key}, level={level}, '
            f'duration={duration}, blocked_until={blocked_until}, ip={ip}'
        )

        return RegistrationBlock(
            key=key,
            blocked_until=blocked_until,
            level=level,
            reason=cls._get_block_reason(level),
        )

    @classmethod
    def clear_blocks(cls, ip=None, phone=None, username=None):
        if ip:
            cls._blocks.pop(cls._get_ip_key(ip), None)
            cls._attempt_counts.pop(cls._get_ip_key(ip), None)
        if phone:
            cls._blocks.pop(cls._get_phone_key(phone), None)
            cls._attempt_counts.pop(cls._get_phone_key(phone), None)
        if username:
            cls._blocks.pop(cls._get_username_key(username), None)
            cls._attempt_counts.pop(cls._get_username_key(username), None)

    @classmethod
    def get_stats(cls):
        now = timezone.now()
        now_time = time.time()
        active_blocks = {}
        for key, blocks in cls._blocks.items():
            valid_blocks = [b for b in blocks if b > now]
            if valid_blocks:
                active_blocks[key] = {
                    'count': len(valid_blocks),
                    'latest': max(valid_blocks),
                    'level': min(len(valid_blocks) - 1, len(cls.BLOCK_DURATIONS) - 1),
                }

        active_attempts = {}
        for key, attempts in cls._attempt_counts.items():
            recent = [t for t in attempts if now_time - t < cls.ATTEMPT_WINDOW_SECONDS]
            if recent:
                active_attempts[key] = len(recent)

        return {
            'active_blocks': active_blocks,
            'active_attempts': active_attempts,
        }

    @classmethod
    def clear_all(cls):
        cls._blocks.clear()
        cls._attempt_counts.clear()
