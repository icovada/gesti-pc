# Generated by Django 4.2.3 on 2023-08-26 20:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0002_servizioresponse_poll_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='servizioresponse',
            name='poll_id',
        ),
        migrations.AddField(
            model_name='servizio',
            name='poll_id',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
