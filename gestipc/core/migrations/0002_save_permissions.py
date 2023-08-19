# -*- coding: utf-8 -*-
# pylint: disable=missing-module-docstring,invalid-name,missing-function-docstring,unused-argument,missing-class-docstring
# Generated by Django 4.0.5 on 2022-07-25 16:01

from django.contrib.auth.management import create_permissions
from django.db import migrations

# https://stackoverflow.com/questions/31735042/adding-django-admin-permissions-in-a-migration-permission-matching-query-does-n


def migrate_permissions(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


def fake_rollback(apps, schema_editor):
    pass  # YOLO


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # no going back YOLO
        migrations.RunPython(migrate_permissions, fake_rollback)
    ]