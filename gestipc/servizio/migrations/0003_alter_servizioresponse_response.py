# Generated by Django 4.2.3 on 2023-07-30 20:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0002_alter_servizioresponse_response'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servizioresponse',
            name='response',
            field=models.CharField(choices=[('accepted', 'Accettato'), ('refused', 'Rifiutato'), ('tentative', 'Forse')], max_length=10),
        ),
    ]
