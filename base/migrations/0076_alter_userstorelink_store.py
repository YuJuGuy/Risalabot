# Generated by Django 5.0.6 on 2024-12-01 10:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0075_alter_userstorelink_store'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userstorelink',
            name='store',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='base.store'),
        ),
    ]