# Generated by Django 5.0.6 on 2024-11-27 09:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('base', '0071_alter_abandonedcart_flow_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonthlyPayments',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('amount', models.CharField(max_length=255)),
                ('subscribtion', models.CharField(max_length=255)),
                ('reference_number', models.CharField(max_length=100, unique=True)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.store')),
            ],
        ),
    ]