from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0007_remove_forse_risposta'),
    ]

    operations = [
        migrations.AddField(
            model_name='servizio',
            name='data_ora_fine',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
