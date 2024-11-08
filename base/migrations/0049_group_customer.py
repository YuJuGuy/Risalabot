# Generated by Django 5.0.6 on 2024-11-05 20:58

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0048_flow_clicks_store_total_clicks'),
    ]

    operations = [
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.store')),
            ],
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_name', models.CharField(max_length=255)),
                ('customer_email', models.CharField(max_length=255)),
                ('customer_phone', models.CharField(max_length=255)),
                ('customer_location', models.CharField(max_length=255)),
                ('customer_updated_at', models.DateTimeField()),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.store')),
                ('customer_groups', models.ManyToManyField(related_name='customers', to='base.group')),
            ],
        ),
    ]
