# Generated by Django 5.0.6 on 2024-11-06 04:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0054_alter_group_group_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='CouponConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('coupon_code', models.CharField(blank=True, max_length=12, unique=True)),
                ('type', models.CharField(choices=[('fixed', 'مبلغ ثابت'), ('percentage', 'نسبة مئوية')], max_length=50)),
                ('amount', models.IntegerField()),
                ('expire_in', models.DateField()),
                ('maximum_amount', models.IntegerField()),
                ('free_shipping', models.BooleanField()),
                ('exclude_sale_products', models.BooleanField()),
            ],
        ),
    ]