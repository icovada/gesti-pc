# Generated by Django 4.2.3 on 2023-07-31 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pcroncellobot', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegramchat',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='telegramstate',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='telegramuser',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
