# Generated by Django 5.0.6 on 2024-10-26 14:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0041_flow_purchases'),
    ]

    operations = [
        migrations.AddField(
            model_name='flow',
            name='store',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='flows', to='base.store'),
        ),
    ]
