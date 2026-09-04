from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Q
from analytics.models import AnalyticsEvent
from core.models import User
from transactions.models import Deposit, Withdrawal
from ai_services.models import AiRental


class AnalyticsService:
    @staticmethod
    def track_event(event_type, user=None, request=None, metadata=None):
        kwargs = {'event_type': event_type}
        if user and user.is_authenticated:
            kwargs['user'] = user
        if request:
            kwargs['ip_address'] = request.META.get('REMOTE_ADDR', '')
            kwargs['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            kwargs['session_id'] = request.session.session_key or ''
        if metadata:
            kwargs['metadata'] = metadata
        return AnalyticsEvent.objects.create(**kwargs)

    @staticmethod
    def get_dashboard_stats(days=30):
        now = timezone.now()
        start = now - timedelta(days=days)

        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'new_users': User.objects.filter(date_joined__gte=start).count(),
            'total_deposits': Deposit.objects.filter(status='completed').aggregate(
                total=Sum('amount'))['total'] or 0,
            'total_withdrawals': Withdrawal.objects.filter(status='completed').aggregate(
                total=Sum('amount'))['total'] or 0,
            'pending_deposits': Deposit.objects.filter(status='pending_review').count(),
            'pending_withdrawals': Withdrawal.objects.filter(
                status__in=['pending', 'under_review']).count(),
            'active_rentals': AiRental.objects.filter(status='ACTIVE').count(),
            'total_rentals': AiRental.objects.count(),
        }
        return stats

    @staticmethod
    def get_daily_registrations(days=30):
        now = timezone.now()
        start = now - timedelta(days=days)
        return AnalyticsEvent.objects.filter(
            event_type='REGISTRATION',
            created_at__gte=start
        ).extra(
            select={'day': "date(created_at)"}
        ).values('day').annotate(count=Count('id')).order_by('day')

    @staticmethod
    def get_daily_deposits(days=30):
        now = timezone.now()
        start = now - timedelta(days=days)
        return Deposit.objects.filter(
            created_at__gte=start,
            status='completed'
        ).extra(
            select={'day': "date(created_at)"}
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('day')

    @staticmethod
    def get_conversion_rate(days=30):
        now = timezone.now()
        start = now - timedelta(days=days)
        total_users = User.objects.filter(date_joined__gte=start).count()
        depositors = Deposit.objects.filter(
            created_at__gte=start, status='completed'
        ).values('user').distinct().count()

        if total_users == 0:
            return 0
        return round((depositors / total_users) * 100, 2)

    @staticmethod
    def export_csv(queryset, filename):
        import csv
        from io import StringIO
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        return response
