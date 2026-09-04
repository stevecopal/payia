from notifications.models import Notification, Message


class NotificationService:
    @staticmethod
    def get_unread_count(user):
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def get_notifications(user, unread_only=False):
        qs = Notification.objects.filter(user=user)
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs.order_by('-created_at')

    @staticmethod
    def mark_read(notification_id, user):
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_read()
            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_read(user):
        return Notification.objects.filter(user=user, is_read=False).update(is_read=True)

    @staticmethod
    def send_message(sender, recipient, subject, body, message_type='INDIVIDUAL'):
        return Message.objects.create(
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            message_type=message_type,
        )

    @staticmethod
    def get_user_messages(user):
        return Message.objects.filter(recipient=user).order_by('-created_at')

    @staticmethod
    def broadcast_message(sender, subject, body, filter_type='all'):
        from core.models import User
        users = User.objects.filter(is_active=True)

        if filter_type == 'ai_users':
            from ai_services.models import AiRental
            user_ids = AiRental.objects.filter(status='ACTIVE').values_list('user_id', flat=True).distinct()
            users = users.filter(id__in=user_ids)
        elif filter_type == 'referrals':
            from referrals.models import Referral
            user_ids = Referral.objects.filter(referral_level=1, is_active=True).values_list('referrer_id', flat=True).distinct()
            users = users.filter(id__in=user_ids)

        messages = []
        for user in users:
            msg = Message.objects.create(
                sender=sender,
                recipient=user,
                subject=subject,
                body=body,
                message_type='GROUP',
                group_filter=filter_type,
            )
            messages.append(msg)

        return messages
