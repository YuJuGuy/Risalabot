# Generated by Django 5.0.6 on 2024-12-05 11:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0096_staticbotstart_return_message'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staticbotstart',
            name='return_message',
            field=models.TextField(default='أثم'),
            preserve_default=False,
        ),
    ]
