from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wallet', '0001_initial'),
        ('ai_services', '0002_aimodel_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='airental',
            name='earning_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='earning amount per period'),
        ),
        migrations.AddField(
            model_name='airental',
            name='next_payment_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='next payment at'),
        ),
        migrations.AddField(
            model_name='airental',
            name='last_payment_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='last payment at'),
        ),
        migrations.AddField(
            model_name='airental',
            name='payment_count',
            field=models.IntegerField(default=0, verbose_name='payment count'),
        ),
        migrations.AddField(
            model_name='airevenue',
            name='payment_reference',
            field=models.CharField(default='LEGACY', max_length=255, unique=True, verbose_name='payment reference'),
        ),
        migrations.AlterField(
            model_name='airevenue',
            name='period_start',
            field=models.DateTimeField(verbose_name='period start'),
        ),
        migrations.AlterField(
            model_name='airevenue',
            name='period_end',
            field=models.DateTimeField(verbose_name='period end'),
        ),
        migrations.AddIndex(
            model_name='airental',
            index=models.Index(fields=['status', 'next_payment_at'], name='rental_status_next_payment_idx'),
        ),
        migrations.AddIndex(
            model_name='airental',
            index=models.Index(fields=['user', 'status'], name='rental_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='airevenue',
            index=models.Index(fields=['payment_reference'], name='revenue_payment_ref_idx'),
        ),
        migrations.AddIndex(
            model_name='airevenue',
            index=models.Index(fields=['rental', 'status'], name='revenue_rental_status_idx'),
        ),
    ]
