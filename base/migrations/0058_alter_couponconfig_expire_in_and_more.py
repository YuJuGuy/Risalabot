# Generated by Django 5.0.6 on 2024-11-06 04:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0057_alter_couponconfig_flow_step_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='couponconfig',
            name='expire_in',
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name='suggestedcouponconfig',
            name='expire_in',
            field=models.IntegerField(),
        ),
    ]