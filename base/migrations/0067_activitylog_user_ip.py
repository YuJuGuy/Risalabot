# Generated by Django 5.0.6 on 2024-11-16 09:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0066_campaign_track_flow_track'),
    ]

    operations = [
        migrations.AddField(
            model_name='activitylog',
            name='user_ip',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]