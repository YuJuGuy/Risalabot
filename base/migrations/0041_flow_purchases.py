# Generated by Django 5.0.6 on 2024-10-26 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0040_rename_recipients_flow_messages_sent'),
    ]

    operations = [
        migrations.AddField(
            model_name='flow',
            name='purchases',
            field=models.IntegerField(default=0),
        ),
    ]
