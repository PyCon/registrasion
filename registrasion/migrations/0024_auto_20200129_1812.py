# Generated by Django 2.2.9 on 2020-01-29 18:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('symposion_schedule', '0001_initial'),
        ('registrasion', '0023_auto_20191122_1506'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='presentation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='symposion_schedule.Presentation', verbose_name='Associated Presentation'),
        ),
        migrations.AlterField(
            model_name='category',
            name='render_type',
            field=models.IntegerField(choices=[(1, 'Radio button'), (2, 'Quantity boxes'), (3, 'Product selector and quantity box'), (4, 'Checkbox button'), (5, 'User Selected Amount'), (7, 'User Selected Amount and quantity box'), (6, 'Checkbox/Quantity Hybrid'), (8, 'Childcare with additional info'), (9, 'YoungCoders with additional info'), (10, 'Presentation')], help_text='The registration form will render this category in this style.', verbose_name='Render type'),
        ),
    ]