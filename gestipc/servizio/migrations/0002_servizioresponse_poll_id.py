# Generated by Django 4.2.3 on 2023-08-26 20:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='servizioresponse',
            name='poll_id',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
