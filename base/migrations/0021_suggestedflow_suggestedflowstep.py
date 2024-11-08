# Generated by Django 5.0.6 on 2024-10-05 16:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0020_flow_reciepients_flow_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuggestedFlow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('img', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='SuggestedFlowStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField()),
                ('action_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.flowactiontypes')),
                ('suggested_flow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='base.suggestedflow')),
            ],
        ),
    ]
