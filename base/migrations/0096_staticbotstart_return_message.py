# Generated by Django 5.0.6 on 2024-12-05 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0095_alter_staticbotlog_store'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticbotstart',
            name='return_message',
            field=models.TextField(blank=True, null=True),
        ),
    ]
