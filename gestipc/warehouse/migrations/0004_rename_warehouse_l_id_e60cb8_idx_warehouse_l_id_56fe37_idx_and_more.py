# Generated by Django 4.2.3 on 2023-08-26 20:20

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0003_create_default_user_groups'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='loan',
            new_name='warehouse_l_id_56fe37_idx',
            old_name='warehouse_l_id_e60cb8_idx',
        ),
        migrations.RenameIndex(
            model_name='loan',
            new_name='warehouse_l_fkinven_4a06fe_idx',
            old_name='warehouse_l_fkinven_fcd1fb_idx',
        ),
    ]
