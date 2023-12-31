# Generated by Django 4.2.3 on 2023-08-17 17:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tg_bot', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalEquipmentType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(max_length=25, verbose_name='Tipo')),
            ],
        ),
        migrations.CreateModel(
            name='TelegramLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('security_code', models.UUIDField(default=uuid.uuid4)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('telegram_user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='tg_bot.telegramuser')),
            ],
        ),
        migrations.CreateModel(
            name='PersonalEquipmentAssignmentDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('size', models.CharField(blank=True, max_length=10, verbose_name='Taglia')),
                ('modello', models.CharField(blank=True, max_length=20, verbose_name='Modello')),
                ('fkequipmentkind', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='hr.personalequipmenttype')),
                ('fkuser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='personalequipmentassignmentdetail',
            constraint=models.UniqueConstraint(fields=('fkuser', 'fkequipmentkind'), name='one_piece_of_equipment_each', violation_error_message='Questo volontario ha già un oggetto di questo tipo'),
        ),
    ]
