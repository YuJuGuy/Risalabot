# Generated by Django 5.0.6 on 2024-10-26 14:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0039_rename_message_count_store_subscription_message_count_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='flow',
            old_name='recipients',
            new_name='messages_sent',
        ),
    ]