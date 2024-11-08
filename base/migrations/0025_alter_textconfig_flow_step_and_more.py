# Generated by Django 5.0.6 on 2024-10-05 18:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0024_alter_textconfig_flow_step_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='textconfig',
            name='flow_step',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='text_config', to='base.flowstep'),
        ),
        migrations.AlterField(
            model_name='timedelayconfig',
            name='flow_step',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='time_delay_config', to='base.flowstep'),
        ),
    ]
