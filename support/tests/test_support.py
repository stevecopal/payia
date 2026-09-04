from django.test import TestCase
from core.models import User, UserProfile
from support.models import SupportTicket, SupportMessage
from support.services.support_service import SupportService


class SupportServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone_number='+2250700000016')
        UserProfile.objects.get_or_create(user=self.user)
        self.admin = User.objects.create(phone_number='+2250700000099', is_staff=True)

    def test_create_ticket(self):
        ticket = SupportService.create_ticket(
            user=self.user,
            subject='Test issue',
            category='GENERAL',
            message='I need help',
        )
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.status, 'OPEN')

    def test_create_ticket_with_initial_message(self):
        ticket = SupportService.create_ticket(
            user=self.user,
            subject='Test issue',
            category='GENERAL',
            message='I need help',
        )
        messages = SupportMessage.objects.filter(ticket=ticket)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.first().sender, self.user)

    def test_reply_to_ticket(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        msg, error = SupportService.reply_to_ticket(
            ticket.pk, self.admin, 'We are looking into it',
        )
        self.assertIsNotNone(msg)
        self.assertIsNone(error)

    def test_reply_sets_ticket_status_waiting_user(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        SupportService.reply_to_ticket(
            ticket.pk, self.admin, 'Response',
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'WAITING_USER')

    def test_user_reply_sets_ticket_in_progress(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        SupportService.reply_to_ticket(
            ticket.pk, self.admin, 'Admin response',
        )
        SupportService.reply_to_ticket(
            ticket.pk, self.user, 'User follow-up',
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'IN_PROGRESS')

    def test_close_ticket(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        result = SupportService.close_ticket(ticket.pk, self.user)
        self.assertTrue(result)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'CLOSED')

    def test_close_ticket_by_admin(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        result = SupportService.close_ticket(ticket.pk, self.admin)
        self.assertTrue(result)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'CLOSED')

    def test_user_ticket_list(self):
        SupportService.create_ticket(
            user=self.user, subject='T1',
            category='GENERAL', message='M1',
        )
        SupportService.create_ticket(
            user=self.user, subject='T2',
            category='GENERAL', message='M2',
        )
        tickets = SupportService.get_user_tickets(self.user)
        self.assertEqual(tickets.count(), 2)

    def test_get_all_tickets(self):
        SupportService.create_ticket(
            user=self.user, subject='T1',
            category='GENERAL', message='M1',
        )
        all_tickets = SupportService.get_all_tickets()
        self.assertEqual(all_tickets.count(), 1)

    def test_get_all_tickets_by_status(self):
        t1 = SupportService.create_ticket(
            user=self.user, subject='T1',
            category='GENERAL', message='M1',
        )
        t2 = SupportService.create_ticket(
            user=self.user, subject='T2',
            category='GENERAL', message='M2',
        )
        SupportService.close_ticket(t1.pk, self.user)
        open_tickets = SupportService.get_all_tickets(status='OPEN')
        self.assertEqual(open_tickets.count(), 1)

    def test_nonexistent_ticket_reply(self):
        msg, error = SupportService.reply_to_ticket(
            99999, self.admin, 'Test',
        )
        self.assertIsNone(msg)
        self.assertIsNotNone(error)

    def test_unauthorized_reply_blocked(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        other_user = User.objects.create(phone_number='+2250700000032')
        msg, error = SupportService.reply_to_ticket(
            ticket.pk, other_user, 'Unauthorized reply',
        )
        self.assertIsNone(msg)
        self.assertIsNotNone(error)

    def test_ticket_priority(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Urgent',
            category='TECHNICAL', message='Server down',
            priority='URGENT',
        )
        self.assertEqual(ticket.priority, 'URGENT')

    def test_ticket_categories(self):
        for category in ['GENERAL', 'DEPOSIT', 'WITHDRAWAL', 'AI', 'REFERRAL', 'ACCOUNT', 'TECHNICAL', 'OTHER']:
            ticket = SupportService.create_ticket(
                user=self.user, subject=f'Ticket {category}',
                category=category, message='Test',
            )
            self.assertEqual(ticket.category, category)

    def test_ticket_str(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test Subject',
            category='GENERAL', message='Help',
        )
        self.assertIn('Test Subject', str(ticket))

    def test_support_message_str(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        msg = SupportMessage.objects.filter(ticket=ticket).first()
        self.assertIn(str(ticket.pk), str(msg))

    def test_ticket_assign(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        ticket.assign(self.admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.admin)
        self.assertEqual(ticket.status, 'IN_PROGRESS')

    def test_ticket_set_priority(self):
        ticket = SupportService.create_ticket(
            user=self.user, subject='Test',
            category='GENERAL', message='Help',
        )
        ticket.set_priority('LOW')
        ticket.refresh_from_db()
        self.assertEqual(ticket.priority, 'LOW')
