from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import IntegrityError
from datetime import timedelta
import csv
import re

from core.models import User, UserProfile, AuditLog, Setting, Role
from core.permissions import admin_required
from transactions.models import Deposit, Withdrawal, PaymentMethod
from transactions.services.deposit_service import DepositService
from transactions.services.withdrawal_service import WithdrawalService
from wallet.models import Wallet, LedgerEntry
from ai_services.models import AiModel, AiCategory, AiOffer, AiRental, AiRevenue
from referrals.models import Referral, Commission
from referrals.services.referral_service import ReferralService
from notifications.models import Notification, Message
from notifications.services.notification_service import NotificationService
from support.models import SupportTicket, SupportMessage
from support.services.support_service import SupportService
from analytics.services.analytics_service import AnalyticsService


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text.strip('-')


@admin_required
def admin_dashboard(request):
    stats = AnalyticsService.get_dashboard_stats(days=30)
    return render(request, 'admin/dashboard.html', {'stats': stats})


@admin_required
def admin_users(request):
    users = User.objects.all().select_related('profile', 'role').order_by('-date_joined')

    q = request.GET.get('q', '')
    if q:
        users = users.filter(
            Q(phone_number__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )

    status = request.GET.get('status', '')
    if status == 'active':
        users = users.filter(is_active=True, is_suspended=False)
    elif status == 'suspended':
        users = users.filter(is_suspended=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)

    paginator = Paginator(users, 20)
    page = request.GET.get('page', 1)
    users = paginator.get_page(page)

    return render(request, 'admin/users.html', {'users': users, 'q': q, 'status': status})


@admin_required
def admin_user_detail(request, pk):
    user = get_object_or_404(User.objects.select_related('profile', 'role'), pk=pk)
    wallet = Wallet.objects.filter(user=user).first()
    deposits = Deposit.objects.filter(user=user).order_by('-created_at')[:10]
    withdrawals = Withdrawal.objects.filter(user=user).order_by('-created_at')[:10]
    rentals = AiRental.objects.filter(user=user).select_related('offer').order_by('-created_at')[:10]
    referrals = Referral.objects.filter(referrer=user).select_related('referred_user')[:20]
    audit_logs = AuditLog.objects.filter(actor=user).order_by('-created_at')[:20]

    return render(request, 'admin/user_detail.html', {
        'target_user': user,
        'wallet': wallet,
        'deposits': deposits,
        'withdrawals': withdrawals,
        'rentals': rentals,
        'referrals': referrals,
        'audit_logs': audit_logs,
    })


@admin_required
def admin_user_toggle_suspend(request, pk):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=pk)
        reason = request.POST.get('reason', '')
        if user.is_suspended:
            user.is_suspended = False
            user.suspension_reason = ''
            user.is_active = True
            user.save(update_fields=['is_suspended', 'suspension_reason', 'is_active'])
            messages.success(request, _('Utilisateur réactivé.'))
        else:
            user.is_suspended = True
            user.suspension_reason = reason
            user.is_active = False
            user.save(update_fields=['is_suspended', 'suspension_reason', 'is_active'])
            messages.warning(request, _('Utilisateur suspendu.'))

        AuditLog.objects.create(
            actor=request.user,
            action='user.suspended' if user.is_suspended else 'user.unsuspended',
            target_type='User',
            target_id=str(pk),
            description=f'{"Suspension" if user.is_suspended else "Réactivation"} de {user.phone_number}. Raison: {reason}',
        )
    return redirect('admin_user_detail', pk=pk)


@admin_required
def admin_deposits(request):
    deposits = Deposit.objects.all().select_related('user', 'payment_method', 'reviewed_by').order_by('-created_at')

    status = request.GET.get('status', '')
    status_lower = status.lower()
    if status_lower:
        deposits = deposits.filter(status=status_lower)

    q = request.GET.get('q', '')
    if q:
        deposits = deposits.filter(
            Q(user__phone_number__icontains=q) |
            Q(transaction_id__icontains=q)
        )

    paginator = Paginator(deposits, 20)
    page = request.GET.get('page', 1)
    deposits = paginator.get_page(page)

    return render(request, 'admin/deposits.html', {
        'deposits': deposits,
        'current_status': status_lower,
        'q': q,
    })


@admin_required
def admin_deposit_detail(request, pk):
    deposit = get_object_or_404(
        Deposit.objects.select_related('user', 'payment_method', 'reviewed_by'),
        pk=pk
    )
    return render(request, 'admin/deposit_detail.html', {'deposit': deposit})


@admin_required
def admin_deposit_approve(request, pk):
    if request.method == 'POST':
        deposit = get_object_or_404(Deposit, pk=pk)
        try:
            DepositService.approve_deposit(deposit, request.user)
            messages.success(request, _('Dépôt approuvé et crédité.'))
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('admin_deposit_detail', pk=pk)


@admin_required
def admin_deposit_reject(request, pk):
    if request.method == 'POST':
        deposit = get_object_or_404(Deposit, pk=pk)
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, _('Une raison de rejet est obligatoire.'))
            return redirect('admin_deposit_detail', pk=pk)
        try:
            DepositService.reject_deposit(deposit, request.user, reason)
            messages.success(request, _('Dépôt refusé.'))
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('admin_deposit_detail', pk=pk)


@admin_required
def admin_withdrawals(request):
    withdrawals = Withdrawal.objects.all().select_related('user', 'withdrawal_method', 'reviewed_by').order_by('-created_at')

    status = request.GET.get('status', '')
    status_lower = status.lower()
    if status_lower:
        withdrawals = withdrawals.filter(status=status_lower)

    q = request.GET.get('q', '')
    if q:
        withdrawals = withdrawals.filter(
            Q(user__phone_number__icontains=q) |
            Q(withdrawal_number__icontains=q)
        )

    paginator = Paginator(withdrawals, 20)
    page = request.GET.get('page', 1)
    withdrawals = paginator.get_page(page)

    return render(request, 'admin/withdrawals.html', {
        'withdrawals': withdrawals,
        'current_status': status_lower,
        'q': q,
    })


@admin_required
def admin_withdrawal_detail(request, pk):
    withdrawal = get_object_or_404(
        Withdrawal.objects.select_related('user', 'withdrawal_method', 'reviewed_by'),
        pk=pk
    )
    return render(request, 'admin/withdrawal_detail.html', {'withdrawal': withdrawal})


@admin_required
def admin_withdrawal_approve(request, pk):
    if request.method == 'POST':
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        ext_ref = request.POST.get('external_reference', '')
        try:
            WithdrawalService.approve_withdrawal(withdrawal, request.user, ext_ref)
            messages.success(request, _('Retrait approuvé.'))
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('admin_withdrawal_detail', pk=pk)


@admin_required
def admin_withdrawal_reject(request, pk):
    if request.method == 'POST':
        withdrawal = get_object_or_404(Withdrawal, pk=pk)
        reason = request.POST.get('reason', '')
        if not reason:
            messages.error(request, _('Une raison de rejet est obligatoire.'))
            return redirect('admin_withdrawal_detail', pk=pk)
        try:
            WithdrawalService.reject_withdrawal(withdrawal, request.user, reason)
            messages.success(request, _('Retrait refusé.'))
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('admin_withdrawal_detail', pk=pk)


@admin_required
def admin_ai_models(request):
    ai_models = AiModel.objects.all().order_by('-created_at')
    return render(request, 'admin/ai_models.html', {'models': ai_models})


@admin_required
def admin_ai_model_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        version = request.POST.get('version', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = 'is_active' in request.POST
        image = request.FILES.get('image')

        if not name or not version:
            messages.error(request, _('Le nom et la version sont obligatoires.'))
            return redirect('admin_ai_models')

        slug = _slugify(name)
        if AiModel.objects.filter(slug=slug).exists():
            messages.error(request, _('Un modèle avec ce nom existe déjà.'))
            return redirect('admin_ai_models')

        model = AiModel.objects.create(
            name=name,
            slug=slug,
            version=version,
            description=description,
            is_active=is_active,
            image=image,
        )
        AuditLog.objects.create(
            actor=request.user,
            action='ai_model.created',
            target_type='AiModel',
            target_id=str(model.pk),
            description=f'Modèle IA créé: {name} v{version}',
        )
        messages.success(request, _('Modèle IA créé avec succès.'))
    return redirect('admin_ai_models')


@admin_required
def admin_ai_model_edit(request, pk):
    if request.method == 'POST':
        model = get_object_or_404(AiModel, pk=pk)
        model.name = request.POST.get('name', model.name).strip()
        model.version = request.POST.get('version', model.version).strip()
        model.description = request.POST.get('description', '').strip()
        model.is_active = 'is_active' in request.POST
        if 'image' in request.FILES:
            model.image = request.FILES['image']
        elif request.POST.get('remove_image'):
            model.image = ''
        model.save()
        AuditLog.objects.create(
            actor=request.user,
            action='ai_model.updated',
            target_type='AiModel',
            target_id=str(pk),
            description=f'Modèle IA modifié: {model.name}',
        )
        messages.success(request, _('Modèle IA mis à jour.'))
    return redirect('admin_ai_models')


@admin_required
def admin_ai_model_delete(request, pk):
    if request.method == 'POST':
        model = get_object_or_404(AiModel, pk=pk)
        name = model.name
        model.delete()
        AuditLog.objects.create(
            actor=request.user,
            action='ai_model.deleted',
            target_type='AiModel',
            target_id=str(pk),
            description=f'Modèle IA supprimé: {name}',
        )
        messages.success(request, _('Modèle IA supprimé.'))
    return redirect('admin_ai_models')


@admin_required
def admin_ai_offers(request):
    offers = AiOffer.objects.all().select_related('ai_model', 'category').order_by('-created_at')
    ai_models = AiModel.objects.filter(is_active=True)
    ai_categories = AiCategory.objects.filter(is_active=True)
    return render(request, 'admin/ai_offers.html', {
        'offers': offers,
        'ai_models': ai_models,
        'ai_categories': ai_categories,
    })


@admin_required
def admin_ai_offer_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        ai_model_id = request.POST.get('ai_model')
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '0')
        duration_days = request.POST.get('duration_days', '30')
        revenue_frequency = request.POST.get('revenue_frequency', 'daily')
        revenue_type = request.POST.get('revenue_type', 'fixed')
        revenue_value = request.POST.get('revenue_value', '0')
        is_active = 'is_active' in request.POST
        is_featured = 'is_featured' in request.POST

        if not name or not ai_model_id:
            messages.error(request, _('Le nom et le modèle sont obligatoires.'))
            return redirect('admin_ai_offers')

        slug = _slugify(name)
        if AiOffer.objects.filter(slug=slug).exists():
            messages.error(request, _('Une offre avec ce nom existe déjà.'))
            return redirect('admin_ai_offers')

        ai_model = get_object_or_404(AiModel, pk=ai_model_id)
        category = get_object_or_404(AiCategory, pk=category_id) if category_id else None

        offer = AiOffer.objects.create(
            name=name,
            slug=slug,
            ai_model=ai_model,
            category=category,
            description=description,
            image=request.FILES.get('image'),
            price=price,
            duration_days=duration_days,
            revenue_frequency=revenue_frequency,
            revenue_type=revenue_type,
            revenue_value=revenue_value,
            is_active=is_active,
            is_featured=is_featured,
        )
        AuditLog.objects.create(
            actor=request.user,
            action='ai_offer.created',
            target_type='AiOffer',
            target_id=str(offer.pk),
            description=f'Offre IA créée: {name} ({price} XAF, {duration_days}j)',
        )
        messages.success(request, _('Offre IA créée avec succès.'))
    return redirect('admin_ai_offers')


@admin_required
def admin_ai_offer_edit(request, pk):
    if request.method == 'POST':
        offer = get_object_or_404(AiOffer, pk=pk)
        offer.name = request.POST.get('name', offer.name).strip()
        offer.description = request.POST.get('description', '').strip()
        offer.price = request.POST.get('price', offer.price)
        offer.duration_days = request.POST.get('duration_days', offer.duration_days)
        offer.revenue_frequency = request.POST.get('revenue_frequency', offer.revenue_frequency)
        offer.revenue_type = request.POST.get('revenue_type', offer.revenue_type)
        offer.revenue_value = request.POST.get('revenue_value', offer.revenue_value)
        offer.is_active = 'is_active' in request.POST
        offer.is_featured = 'is_featured' in request.POST

        if 'image' in request.FILES:
            offer.image = request.FILES['image']
        elif request.POST.get('remove_image'):
            offer.image = ''

        ai_model_id = request.POST.get('ai_model')
        if ai_model_id:
            offer.ai_model = get_object_or_404(AiModel, pk=ai_model_id)

        category_id = request.POST.get('category')
        offer.category = get_object_or_404(AiCategory, pk=category_id) if category_id else None

        offer.save()
        AuditLog.objects.create(
            actor=request.user,
            action='ai_offer.updated',
            target_type='AiOffer',
            target_id=str(pk),
            description=f'Offre IA modifiée: {offer.name}',
        )
        messages.success(request, _('Offre IA mise à jour.'))
    return redirect('admin_ai_offers')


@admin_required
def admin_ai_offer_delete(request, pk):
    if request.method == 'POST':
        offer = get_object_or_404(AiOffer, pk=pk)
        name = offer.name
        offer.delete()
        AuditLog.objects.create(
            actor=request.user,
            action='ai_offer.deleted',
            target_type='AiOffer',
            target_id=str(pk),
            description=f'Offre IA supprimée: {name}',
        )
        messages.success(request, _('Offre IA supprimée.'))
    return redirect('admin_ai_offers')


@admin_required
def admin_notifications(request):
    notifications_list = Notification.objects.all().select_related('user').order_by('-created_at')[:100]
    return render(request, 'admin/notifications.html', {'notifications_list': notifications_list})


@admin_required
def admin_notification_create(request):
    if request.method == 'POST':
        recipient_type = request.POST.get('recipient_type', 'all')
        notification_type = request.POST.get('notification_type', 'SYSTEM_MESSAGE')
        title = request.POST.get('title', '').strip()
        message_text = request.POST.get('message', '').strip()

        if not title or not message_text:
            messages.error(request, _('Le titre et le message sont obligatoires.'))
            return redirect('admin_notifications')

        if recipient_type == 'user':
            phone = request.POST.get('recipient_phone', '').strip()
            phone = re.sub(r'[\s\-]', '', phone)
            if phone.startswith('237'):
                phone = '+' + phone
            elif phone.startswith('6'):
                phone = '+237' + phone
            try:
                user = User.objects.get(phone_number=phone)
                Notification.objects.create(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    message=message_text,
                )
                messages.success(request, _('Notification envoyée à {}.'.format(phone)))
            except User.DoesNotExist:
                messages.error(request, _('Utilisateur non trouvé: {}'.format(phone)))
        else:
            users = User.objects.filter(is_active=True)
            count = 0
            for user in users:
                Notification.objects.create(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    message=message_text,
                )
                count += 1
            messages.success(request, _('Notification envoyée à {} utilisateurs.'.format(count)))

        AuditLog.objects.create(
            actor=request.user,
            action='notification.created',
            target_type='Notification',
            target_id='0',
            description=f'Notification "{title}" envoyée à {"tous les utilisateurs" if recipient_type == "all" else "un utilisateur spécifique"}',
        )
    return redirect('admin_notifications')


@admin_required
def admin_messages(request):
    messages_list = Message.objects.all().select_related('sender', 'recipient').order_by('-created_at')[:100]
    return render(request, 'admin/messages.html', {'messages_list': messages_list})


@admin_required
def admin_commissions(request):
    commissions = Commission.objects.all().select_related('user', 'source_user').order_by('-created_at')
    return render(request, 'admin/commissions.html', {'commissions': commissions})


@admin_required
def admin_referrals(request):
    referrals = Referral.objects.all().select_related('referrer', 'referred_user').order_by('-created_at')

    stats = {
        'total_referrals': Referral.objects.count(),
        'level_1': Referral.objects.filter(referral_level=1).count(),
        'level_2': Referral.objects.filter(referral_level=2).count(),
        'level_3': Referral.objects.filter(referral_level=3).count(),
        'level_4': Referral.objects.filter(referral_level=4).count(),
        'level_5': Referral.objects.filter(referral_level=5).count(),
        'total_commissions': Commission.objects.aggregate(total=Sum('amount'))['total'] or 0,
    }

    paginator = Paginator(referrals, 20)
    page = request.GET.get('page', 1)
    referrals = paginator.get_page(page)

    return render(request, 'admin/referrals.html', {'referrals': referrals, 'stats': stats})


@admin_required
def admin_support(request):
    tickets = SupportService.get_all_tickets()
    status = request.GET.get('status')
    if status:
        tickets = tickets.filter(status=status)

    paginator = Paginator(tickets, 20)
    page = request.GET.get('page', 1)
    tickets = paginator.get_page(page)

    return render(request, 'admin/support.html', {'tickets': tickets, 'current_status': status})


@admin_required
def admin_support_ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket.objects.select_related('user', 'assigned_to'), pk=pk)
    ticket_messages = ticket.messages.all().select_related('sender')

    if request.method == 'POST':
        form_type = request.POST.get('form_type', '')
        if form_type == 'reply':
            SupportService.reply_to_ticket(
                ticket_id=ticket.pk,
                sender=request.user,
                message=request.POST.get('message', ''),
                is_internal_note='is_internal_note' in request.POST,
            )
            messages.success(request, _('Réponse envoyée.'))
        elif form_type == 'assign':
            assignee_id = request.POST.get('assignee_id')
            if assignee_id:
                try:
                    assignee = User.objects.get(pk=assignee_id)
                    ticket.assign(assignee)
                    messages.success(request, _('Ticket assigné.'))
                except User.DoesNotExist:
                    pass
        elif form_type == 'status':
            new_status = request.POST.get('new_status')
            if new_status:
                ticket.status = new_status
                ticket.save(update_fields=['status', 'updated_at'])
                messages.success(request, _('Statut mis à jour.'))
        return redirect('admin_support_ticket_detail', pk=pk)

    return render(request, 'admin/support_detail.html', {
        'ticket': ticket,
        'ticket_messages': ticket_messages,
    })


@admin_required
def admin_statistics(request):
    stats = AnalyticsService.get_dashboard_stats(days=30)
    daily_deposits = AnalyticsService.get_daily_deposits(days=30)
    daily_registrations = AnalyticsService.get_daily_registrations(days=30)
    conversion_rate = AnalyticsService.get_conversion_rate(days=30)

    max_deposit = max([d['total'] for d in daily_deposits], default=1) if daily_deposits else 1
    max_registration = max([d['count'] for d in daily_registrations], default=1) if daily_registrations else 1
    stats['max_deposit'] = max_deposit
    stats['max_registration'] = max_registration

    return render(request, 'admin/statistics.html', {
        'stats': stats,
        'daily_deposits': daily_deposits,
        'daily_registrations': daily_registrations,
        'conversion_rate': conversion_rate,
    })


@admin_required
def admin_audit(request):
    logs = AuditLog.objects.all().select_related('actor').order_by('-created_at')

    q = request.GET.get('q', '')
    if q:
        logs = logs.filter(
            Q(action__icontains=q) |
            Q(description__icontains=q) |
            Q(actor__phone_number__icontains=q)
        )

    paginator = Paginator(logs, 30)
    page = request.GET.get('page', 1)
    logs = paginator.get_page(page)

    return render(request, 'admin/audit.html', {'logs': logs, 'q': q})


@admin_required
def admin_settings(request):
    settings_qs = Setting.objects.all().order_by('key')

    if request.method == 'POST':
        commission_keys = [f'level_{i}_percentage' for i in range(1, 6)]
        commission_values = {}
        has_commission_change = False

        for setting in settings_qs:
            field_name = f'setting_{setting.key}'
            value = request.POST.get(field_name, '')
            if value != setting.value:
                has_commission_change = True
                old_value = setting.value
                setting.value = value
                setting.save(update_fields=['value', 'updated_at'])
                AuditLog.objects.create(
                    actor=request.user,
                    action='setting.changed',
                    target_type='Setting',
                    target_id=str(setting.pk),
                    description=f'Paramètre {setting.key} modifié: {old_value} -> {value}',
                )
                if setting.key in commission_keys:
                    commission_values[setting.key] = value

        if has_commission_change:
            from decimal import Decimal, InvalidOperation
            total = Decimal('0')
            for key in commission_keys:
                try:
                    val = commission_values.get(key)
                    if val is None:
                        val = Setting.objects.get(key=key).value
                    total += Decimal(str(val))
                except (Setting.DoesNotExist, InvalidOperation, ValueError):
                    pass

            try:
                max_setting = Setting.objects.get(key='max_total_commission_percentage')
                max_total = Decimal(max_setting.value)
            except (Setting.DoesNotExist, InvalidOperation):
                max_total = Decimal('90')

            if total > max_total:
                messages.warning(
                    request,
                    f'Paramètres sauvegardés. ATTENTION: Le total des commissions ({total}%) '
                    f'dépasse la limite ({max_total}%). Les nouveaux dépôts pourront générer '
                    f'des commissions jusqu\'à cette limite.'
                )
            else:
                messages.success(request, _('Paramètres sauvegardés.'))
        else:
            messages.success(request, _('Paramètres sauvegardés.'))

        return redirect('admin_settings')

    return render(request, 'admin/settings.html', {'settings': settings_qs})


@admin_required
def admin_export_deposits(request):
    deposits = Deposit.objects.all().select_related('user', 'payment_method').order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="deposits_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Utilisateur', 'Montant', 'Méthode', 'Transaction ID', 'Statut', 'Date'])
    for d in deposits:
        writer.writerow([
            d.pk, d.user.phone_number, d.amount,
            d.payment_method.name, d.transaction_id,
            d.status, d.created_at.strftime('%d/%m/%Y %H:%M'),
        ])

    return response


@admin_required
def admin_export_withdrawals(request):
    withdrawals = Withdrawal.objects.all().select_related('user', 'withdrawal_method').order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="withdrawals_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Utilisateur', 'Montant', 'Frais', 'Net', 'Méthode', 'Statut', 'Date'])
    for w in withdrawals:
        writer.writerow([
            w.pk, w.user.phone_number, w.amount, w.fee, w.net_amount,
            w.withdrawal_method.name, w.status,
            w.created_at.strftime('%d/%m/%Y %H:%M'),
        ])

    return response


@admin_required
def admin_payment_methods(request):
    methods = PaymentMethod.objects.all().order_by('display_order', 'name')
    return render(request, 'admin/payment_methods.html', {'methods': methods})


@admin_required
def admin_payment_method_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        reception_name = request.POST.get('reception_name', '').strip()
        ussd_template = request.POST.get('ussd_template', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = 'is_active' in request.POST
        min_amount = request.POST.get('min_amount', '').strip()
        max_amount = request.POST.get('max_amount', '').strip()
        instructions = request.POST.get('instructions', '').strip()

        if not name:
            messages.error(request, _('Le nom est obligatoire.'))
            return redirect('admin_payment_method_create')

        from django.utils.text import slugify as slug_func
        slug = slug_func(name)
        if PaymentMethod.objects.filter(slug=slug).exists():
            slug = f"{slug}-{PaymentMethod.objects.count() + 1}"

        from decimal import Decimal, InvalidOperation
        min_val = None
        max_val = None
        try:
            if min_amount:
                min_val = Decimal(min_amount)
        except InvalidOperation:
            pass
        try:
            if max_amount:
                max_val = Decimal(max_amount)
        except InvalidOperation:
            pass

        method = PaymentMethod.objects.create(
            name=name,
            slug=slug,
            phone_number=phone_number,
            reception_name=reception_name,
            ussd_template=ussd_template,
            description=description,
            is_active=is_active,
            min_amount=min_val,
            max_amount=max_val,
            instructions=instructions,
        )

        AuditLog.objects.create(
            actor=request.user,
            action='payment_method.created',
            target_type='PaymentMethod',
            target_id=str(method.pk),
            description=f'Méthode de paiement "{name}" créée.',
        )

        messages.success(request, _('Méthode de paiement créée.'))
        return redirect('admin_payment_methods')

    return render(request, 'admin/payment_method_form.html', {'method': None})


@admin_required
def admin_payment_method_edit(request, pk):
    method = get_object_or_404(PaymentMethod, pk=pk)

    if request.method == 'POST':
        method.name = request.POST.get('name', '').strip()
        method.phone_number = request.POST.get('phone_number', '').strip()
        method.reception_name = request.POST.get('reception_name', '').strip()
        method.ussd_template = request.POST.get('ussd_template', '').strip()
        method.description = request.POST.get('description', '').strip()
        method.is_active = 'is_active' in request.POST
        method.instructions = request.POST.get('instructions', '').strip()

        if not method.name:
            messages.error(request, _('Le nom est obligatoire.'))
            return redirect('admin_payment_method_edit', pk=pk)

        from decimal import Decimal, InvalidOperation
        try:
            min_amount = request.POST.get('min_amount', '').strip()
            method.min_amount = Decimal(min_amount) if min_amount else None
        except InvalidOperation:
            pass
        try:
            max_amount = request.POST.get('max_amount', '').strip()
            method.max_amount = Decimal(max_amount) if max_amount else None
        except InvalidOperation:
            pass

        method.save()

        AuditLog.objects.create(
            actor=request.user,
            action='payment_method.updated',
            target_type='PaymentMethod',
            target_id=str(method.pk),
            description=f'Méthode de paiement "{method.name}" modifiée.',
        )

        messages.success(request, _('Méthode de paiement mise à jour.'))
        return redirect('admin_payment_methods')

    return render(request, 'admin/payment_method_form.html', {'method': method})


@admin_required
def admin_payment_method_delete(request, pk):
    if request.method == 'POST':
        method = get_object_or_404(PaymentMethod, pk=pk)
        name = method.name

        has_deposits = Deposit.objects.filter(payment_method=method).exists()
        if has_deposits:
            method.is_active = False
            method.save(update_fields=['is_active'])
            messages.warning(request, _('Méthode désactivée (des dépôts existent).'))
        else:
            method.delete()
            messages.success(request, _('Méthode de paiement supprimée.'))

        AuditLog.objects.create(
            actor=request.user,
            action='payment_method.deleted',
            target_type='PaymentMethod',
            target_id=str(pk),
            description=f'Méthode de paiement "{name}" supprimée.',
        )

    return redirect('admin_payment_methods')
