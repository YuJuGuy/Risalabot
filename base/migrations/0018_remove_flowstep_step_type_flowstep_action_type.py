# Generated by Django 5.0.6 on 2024-09-30 16:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0017_flowactiontypes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='flowstep',
            name='step_type',
        ),
        migrations.AddField(
            model_name='flowstep',
            name='action_type',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='base.flowactiontypes'),
        ),
    ]
