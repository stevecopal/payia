from django.test import TestCase
from core.models import User, UserProfile
from notifications.models import Notification, Message
from notifications.services.notification_service import NotificationService


class NotificationServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone_number='+2250700000015')
        UserProfile.objects.get_or_create(user=self.user)

    def test_create_notification(self):
        Notification.objects.create(
            user=self.user,
            notification_type='SYSTEM_MESSAGE',
            title='Test',
            message='Test message',
        )
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_unread_count(self):
        Notification.objects.create(
            user=self.user, notification_type='SYSTEM_MESSAGE',
            title='Test', message='Msg',
        )
        Notification.objects.create(
            user=self.user, notification_type='SYSTEM_MESSAGE',
            title='Test2', message='Msg2', is_read=True,
        )
        self.assertEqual(NotificationService.get_unread_count(self.user), 1)

    def test_mark_read(self):
        n = Notification.objects.create(
            user=self.user, notification_type='SYSTEM_MESSAGE',
            title='Test', message='Msg',
        )
        result = NotificationService.mark_read(n.pk, self.user)
        self.assertTrue(result)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_read_nonexistent(self):
        result = NotificationService.mark_read(99999, self.user)
        self.assertFalse(result)

    def test_mark_all_read(self):
        for i in range(5):
            Notification.objects.create(
                user=self.user, notification_type='SYSTEM_MESSAGE',
                title='Test', message='Msg',
            )
        NotificationService.mark_all_read(self.user)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0,
        )

    def test_send_message(self):
        msg = NotificationService.send_message(None, self.user, 'Subject', 'Body')
        self.assertIsNotNone(msg)
        self.assertEqual(Message.objects.filter(recipient=self.user).count(), 1)

    def test_get_notifications(self):
        for i in range(3):
            Notification.objects.create(
                user=self.user, notification_type='SYSTEM_MESSAGE',
                title=f'Test{i}', message=f'Msg{i}',
            )
        notifications = NotificationService.get_notifications(self.user)
        self.assertEqual(notifications.count(), 3)

    def test_get_notifications_unread_only(self):
        Notification.objects.create(
            user=self.user, notification_type='SYSTEM_MESSAGE',
            title='Read', message='Read', is_read=True,
        )
        Notification.objects.create(
            user=self.user, notification_type='SYSTEM_MESSAGE',
            title='Unread', message='Unread',
        )
        notifications = NotificationService.get_notifications(self.user, unread_only=True)
        self.assertEqual(notifications.count(), 1)

    def test_get_user_messages(self):
        Message.objects.create(
            sender=None, recipient=self.user,
            subject='S1', body='B1',
        )
        Message.objects.create(
            sender=None, recipient=self.user,
            subject='S2', body='B2',
        )
        messages = NotificationService.get_user_messages(self.user)
        self.assertEqual(messages.count(), 2)

    def test_notification_str(self):
        n = Notification.objects.create(
            user=self.user, notification_type='DEPOSIT_APPROVED',
            title='Depot approuve', message='Votre depot a ete approuve.',
        )
        self.assertIn(self.user.phone_number, str(n))

    def test_message_str(self):
        msg = Message.objects.create(
            sender=None, recipient=self.user,
            subject='Welcome', body='Welcome to PAYIA',
        )
        self.assertIn('Welcome', str(msg))
        self.assertIn(self.user.phone_number, str(msg))

    def test_notification_mark_read_sets_read_at(self):
        n = Notification.objects.create(
            user=self.user, notification_type='SYSTEM_MESSAGE',
            title='Test', message='Msg',
        )
        self.assertIsNone(n.read_at)
        n.mark_read()
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)

    def test_broadcast_message(self):
        User.objects.create(phone_number='+2250700000031')
        msgs = NotificationService.broadcast_message(
            sender=None, subject='Broadcast', body='Hello all',
        )
        self.assertGreaterEqual(len(msgs), 1)

    def test_notification_types_choices(self):
        valid_types = [
            'DEPOSIT_SUBMITTED', 'DEPOSIT_APPROVED', 'DEPOSIT_REJECTED',
            'WITHDRAWAL_REQUESTED', 'WITHDRAWAL_APPROVED', 'WITHDRAWAL_REJECTED',
            'AI_ACTIVATED', 'AI_EXPIRED', 'COMMISSION_RECEIVED',
            'NEW_REFERRAL', 'SECURITY_ALERT', 'SYSTEM_MESSAGE',
        ]
        for ntype in valid_types:
            n = Notification.objects.create(
                user=self.user, notification_type=ntype,
                title='Test', message='Msg',
            )
            self.assertEqual(n.notification_type, ntype)
