# Generated by Django 5.0.6 on 2024-12-05 07:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0091_staticbotstart_condition_alter_staticbot_condition'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staticbotstart',
            name='condition',
            field=models.IntegerField(choices=[(1, 'النص بالضبط'), (2, 'يحتوي على النص'), (3, 'أي النص')], default=3),
        ),
    ]