from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0008_servizio_data_ora_fine'),
    ]

    operations = [
        migrations.AddField(
            model_name='servizio',
            name='end_reminder_sent',
            field=models.BooleanField(default=False),
        ),
    ]
