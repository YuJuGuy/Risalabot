# Generated by Django 5.0.6 on 2024-12-05 07:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0092_alter_staticbotstart_condition'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staticbot',
            name='condition',
            field=models.IntegerField(choices=[(1, 'النص بالضبط'), (2, 'يحتوي على النص')], default=1),
        ),
    ]
