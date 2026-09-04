from django.db import transaction
from support.models import SupportTicket, SupportMessage
from core.models import AuditLog
from notifications.models import Notification


class SupportService:
    @staticmethod
    def create_ticket(user, subject, category, message, priority='MEDIUM', attachment=None):
        with transaction.atomic():
            ticket = SupportTicket.objects.create(
                user=user,
                subject=subject,
                category=category,
                priority=priority,
            )
            SupportMessage.objects.create(
                ticket=ticket,
                sender=user,
                message=message,
                attachment=attachment if attachment else None,
            )
            return ticket

    @staticmethod
    def reply_to_ticket(ticket_id, sender, message, is_internal_note=False, attachment=None):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
        except SupportTicket.DoesNotExist:
            return None, "Ticket introuvable."

        if not is_internal_note:
            if ticket.user != sender and not (sender.is_staff or
                (ticket.assigned_to and ticket.assigned_to == sender)):
                return None, "Non autorisé."

        msg = SupportMessage.objects.create(
            ticket=ticket,
            sender=sender,
            message=message,
            is_internal_note=is_internal_note,
            attachment=attachment if attachment else None,
        )

        ticket.last_reply_at = msg.created_at

        if sender.is_staff and not is_internal_note:
            if ticket.status != 'WAITING_USER':
                ticket.status = 'WAITING_USER'
        elif sender == ticket.user:
            if ticket.status in ['WAITING_USER', 'OPEN']:
                ticket.status = 'IN_PROGRESS'

        ticket.save(update_fields=['last_reply_at', 'status', 'updated_at'])

        if sender.is_staff and not is_internal_note:
            Notification.objects.create(
                user=ticket.user,
                notification_type='SYSTEM_MESSAGE',
                title='Réponse du support',
                message=f'Vous avez une nouvelle réponse pour le ticket "{ticket.subject}".',
                link=f'/support/{ticket.pk}/',
            )

        return msg, None

    @staticmethod
    def close_ticket(ticket_id, user):
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
            if ticket.user == user or user.is_staff:
                ticket.close()
                return True
        except SupportTicket.DoesNotExist:
            pass
        return False

    @staticmethod
    def get_user_tickets(user):
        return SupportTicket.objects.filter(user=user).order_by('-created_at')

    @staticmethod
    def get_all_tickets(status=None, category=None, priority=None):
        qs = SupportTicket.objects.all().select_related('user', 'assigned_to')
        if status:
            qs = qs.filter(status=status)
        if category:
            qs = qs.filter(category=category)
        if priority:
            qs = qs.filter(priority=priority)
        return qs.order_by('-created_at')
