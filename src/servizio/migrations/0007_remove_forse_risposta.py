from django.db import migrations


def convert_forse_to_no(apps, schema_editor):
    VolontarioServizioMap = apps.get_model('servizio', 'VolontarioServizioMap')
    VolontarioServizioMap.objects.filter(risposta='forse').update(risposta='no')


class Migration(migrations.Migration):

    dependencies = [
        ('servizio', '0006_add_checklist_message_id_to_timbratura'),
    ]

    operations = [
        migrations.RunPython(convert_forse_to_no, migrations.RunPython.noop),
    ]
