# Generated by Django 2.2.2 on 2019-11-12 18:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registrasion', '0017_auto_20191112_1841'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='allow_housing',
            field=models.BooleanField(default=False, verbose_name='Allow Housing Registration'),
        ),
    ]