# Generated by Django 2.2.2 on 2019-10-28 20:14

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('registrasion', '0007_auto_20190827_1935'),
    ]

    operations = [
        migrations.AddField(
            model_name='lineitem',
            name='additional_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='additional_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
