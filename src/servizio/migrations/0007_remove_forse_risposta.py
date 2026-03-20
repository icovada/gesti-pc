# Generated migration to remove 'forse' choice from VolontarioServizioMap.risposta

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0006_add_checklist_message_id_to_timbratura'),
    ]

    operations = [
        migrations.AlterField(
            model_name='volontarioserviziomap',
            name='risposta',
            field=models.CharField(
                blank=True,
                choices=[('si', 'Sì'), ('no', 'No')],
                max_length=10,
                null=True,
            ),
        ),
    ]
