# Generated by Django 4.2.3 on 2023-08-17 17:35

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(max_length=50, verbose_name='Modello')),
                ('brand', models.CharField(max_length=20, verbose_name='Marca')),
                ('kind', models.CharField(max_length=20, verbose_name='Tipo')),
                ('picture', models.ImageField(blank=True, null=True, upload_to='', verbose_name='Foto')),
                ('conditions', models.PositiveIntegerField(default=5, validators=[django.core.validators.MaxValueValidator(5)], verbose_name='Condizioni')),
                ('notes', models.TextField(verbose_name='Note aggiuntive')),
            ],
        ),
        migrations.CreateModel(
            name='Loans',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('loan_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('return_date', models.DateTimeField(blank=True, null=True)),
                ('fkinventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='warehouse.inventoryitem')),
                ('fkuser', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
