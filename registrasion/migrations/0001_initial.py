# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-04-25 08:30
from __future__ import unicode_literals

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import registrasion.models.commerce


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Attendee',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_code', models.CharField(db_index=True, max_length=6, unique=True)),
                ('completed_registration', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='AttendeeProfileBase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendee', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Attendee')),
            ],
        ),
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time_last_updated', models.DateTimeField(db_index=True)),
                ('reservation_duration', models.DurationField()),
                ('revision', models.PositiveIntegerField(default=1)),
                ('status', models.IntegerField(choices=[(1, 'Active'), (2, 'Paid'), (3, 'Released')], db_index=True, default=1)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=65, verbose_name='Name')),
                ('description', models.CharField(max_length=255, verbose_name='Description')),
                ('limit_per_user', models.PositiveIntegerField(blank=True, help_text='The total number of items from this category one attendee may purchase.', null=True, verbose_name='Limit per user')),
                ('required', models.BooleanField(help_text='If enabled, a user must select an item from this category.')),
                ('order', models.PositiveIntegerField(db_index=True, verbose_name=b'Display order')),
                ('render_type', models.IntegerField(choices=[(1, 'Radio button'), (2, 'Quantity boxes')], help_text='The registration form will render this category in this style.', verbose_name='Render type')),
            ],
            options={
                'ordering': ('order',),
                'verbose_name': 'inventory - category',
                'verbose_name_plural': 'inventory - categories',
            },
        ),
        migrations.CreateModel(
            name='CreditNoteRefund',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DateTimeField(default=django.utils.timezone.now)),
                ('reference', models.CharField(max_length=255)),
            ],
            bases=(registrasion.models.commerce.CleanOnSave, models.Model),
        ),
        migrations.CreateModel(
            name='DiscountBase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(help_text='A description of this discount. This will be included on invoices where this discount is applied.', max_length=255, verbose_name='Description')),
            ],
        ),
        migrations.CreateModel(
            name='DiscountForCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('percentage', models.DecimalField(decimal_places=1, max_digits=4)),
                ('quantity', models.PositiveIntegerField()),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Category')),
            ],
        ),
        migrations.CreateModel(
            name='DiscountForProduct',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('percentage', models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('quantity', models.PositiveIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='DiscountItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField()),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Cart')),
            ],
            options={
                'ordering': ('product',),
            },
        ),
        migrations.CreateModel(
            name='FlagBase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
                ('condition', models.IntegerField(choices=[(1, 'Disable if false'), (2, 'Enable if true')], default=2, help_text="If there is at least one 'disable if false' flag defined on a product or category, all such flag  conditions must be met. If there is at least one 'enable if true' flag, at least one such condition must be met. If both types of conditions exist on a product, both of these rules apply.")),
            ],
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cart_revision', models.IntegerField(db_index=True, null=True)),
                ('status', models.IntegerField(choices=[(1, 'Unpaid'), (2, 'Paid'), (3, 'Refunded'), (4, 'VOID')], db_index=True)),
                ('recipient', models.CharField(max_length=1024)),
                ('issue_time', models.DateTimeField()),
                ('due_time', models.DateTimeField()),
                ('value', models.DecimalField(decimal_places=2, max_digits=8)),
                ('cart', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='registrasion.Cart')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='LineItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=8)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Invoice')),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='PaymentBase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DateTimeField(default=django.utils.timezone.now)),
                ('reference', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
            ],
            options={
                'ordering': ('time',),
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=65, verbose_name='Name')),
                ('description', models.CharField(blank=True, max_length=255, null=True, verbose_name='Description')),
                ('price', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Price')),
                ('limit_per_user', models.PositiveIntegerField(blank=True, null=True, verbose_name='Limit per user')),
                ('reservation_duration', models.DurationField(default=datetime.timedelta(0, 3600), help_text='The length of time this product will be reserved before it is released for someone else to purchase.', verbose_name='Reservation duration')),
                ('order', models.PositiveIntegerField(db_index=True, verbose_name=b'Display order')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Category', verbose_name='Product category')),
            ],
            options={
                'ordering': ('category__order', 'order'),
                'verbose_name': 'inventory - product',
            },
        ),
        migrations.CreateModel(
            name='ProductItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(db_index=True)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Cart')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Product')),
            ],
            options={
                'ordering': ('product',),
            },
        ),
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient', models.CharField(max_length=64, verbose_name='Recipient')),
                ('code', models.CharField(max_length=16, unique=True, verbose_name='Voucher code')),
                ('limit', models.PositiveIntegerField(verbose_name='Voucher use limit')),
            ],
        ),
        migrations.CreateModel(
            name='CategoryFlag',
            fields=[
                ('flagbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.FlagBase')),
                ('enabling_category', models.ForeignKey(help_text='If a product from this category is purchased, this condition is met.', on_delete=django.db.models.deletion.CASCADE, to='registrasion.Category')),
            ],
            options={
                'verbose_name': 'flag (dependency on product from category)',
                'verbose_name_plural': 'flags (dependency on product from category)',
            },
            bases=('registrasion.flagbase',),
        ),
        migrations.CreateModel(
            name='CreditNote',
            fields=[
                ('paymentbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.PaymentBase')),
            ],
            bases=('registrasion.paymentbase',),
        ),
        migrations.CreateModel(
            name='CreditNoteApplication',
            fields=[
                ('paymentbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.PaymentBase')),
                ('parent', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='registrasion.CreditNote')),
            ],
            bases=(registrasion.models.commerce.CleanOnSave, 'registrasion.paymentbase'),
        ),
        migrations.CreateModel(
            name='IncludedProductDiscount',
            fields=[
                ('discountbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.DiscountBase')),
                ('enabling_products', models.ManyToManyField(help_text='If one of these products are purchased, the discounts below will be enabled.', to='registrasion.Product', verbose_name='Including product')),
            ],
            options={
                'verbose_name': 'discount (product inclusions)',
                'verbose_name_plural': 'discounts (product inclusions)',
            },
            bases=('registrasion.discountbase',),
        ),
        migrations.CreateModel(
            name='ManualCreditNoteRefund',
            fields=[
                ('creditnoterefund_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.CreditNoteRefund')),
                ('entered_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=('registrasion.creditnoterefund',),
        ),
        migrations.CreateModel(
            name='ManualPayment',
            fields=[
                ('paymentbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.PaymentBase')),
                ('entered_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=('registrasion.paymentbase',),
        ),
        migrations.CreateModel(
            name='ProductFlag',
            fields=[
                ('flagbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.FlagBase')),
                ('enabling_products', models.ManyToManyField(help_text='If one of these products are purchased, this condition is met.', to='registrasion.Product')),
            ],
            options={
                'verbose_name': 'flag (dependency on product)',
                'verbose_name_plural': 'flags (dependency on product)',
            },
            bases=('registrasion.flagbase',),
        ),
        migrations.CreateModel(
            name='TimeOrStockLimitDiscount',
            fields=[
                ('discountbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.DiscountBase')),
                ('start_time', models.DateTimeField(blank=True, help_text='This discount will only be available after this time.', null=True, verbose_name='Start time')),
                ('end_time', models.DateTimeField(blank=True, help_text='This discount will only be available before this time.', null=True, verbose_name='End time')),
                ('limit', models.PositiveIntegerField(blank=True, help_text='This discount may only be applied this many times.', null=True, verbose_name='Limit')),
            ],
            options={
                'verbose_name': 'discount (time/stock limit)',
                'verbose_name_plural': 'discounts (time/stock limit)',
            },
            bases=('registrasion.discountbase',),
        ),
        migrations.CreateModel(
            name='TimeOrStockLimitFlag',
            fields=[
                ('flagbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.FlagBase')),
                ('start_time', models.DateTimeField(blank=True, help_text='Products included in this condition will only be available after this time.', null=True)),
                ('end_time', models.DateTimeField(blank=True, help_text='Products included in this condition will only be available before this time.', null=True)),
                ('limit', models.PositiveIntegerField(blank=True, help_text='The number of items under this grouping that can be purchased.', null=True)),
            ],
            options={
                'verbose_name': 'flag (time/stock limit)',
                'verbose_name_plural': 'flags (time/stock limit)',
            },
            bases=('registrasion.flagbase',),
        ),
        migrations.CreateModel(
            name='VoucherDiscount',
            fields=[
                ('discountbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.DiscountBase')),
                ('voucher', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Voucher', verbose_name='Voucher')),
            ],
            options={
                'verbose_name': 'discount (enabled by voucher)',
                'verbose_name_plural': 'discounts (enabled by voucher)',
            },
            bases=('registrasion.discountbase',),
        ),
        migrations.CreateModel(
            name='VoucherFlag',
            fields=[
                ('flagbase_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='registrasion.FlagBase')),
                ('voucher', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Voucher')),
            ],
            options={
                'verbose_name': 'flag (dependency on voucher)',
                'verbose_name_plural': 'flags (dependency on voucher)',
            },
            bases=('registrasion.flagbase',),
        ),
        migrations.AddField(
            model_name='paymentbase',
            name='invoice',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Invoice'),
        ),
        migrations.AddField(
            model_name='lineitem',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='registrasion.Product'),
        ),
        migrations.AddField(
            model_name='flagbase',
            name='categories',
            field=models.ManyToManyField(blank=True, help_text="Categories whose products are affected by this flag's condition.", related_name='flagbase_set', to='registrasion.Category'),
        ),
        migrations.AddField(
            model_name='flagbase',
            name='products',
            field=models.ManyToManyField(blank=True, help_text="Products affected by this flag's condition.", related_name='flagbase_set', to='registrasion.Product'),
        ),
        migrations.AddField(
            model_name='discountitem',
            name='discount',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.DiscountBase'),
        ),
        migrations.AddField(
            model_name='discountitem',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Product'),
        ),
        migrations.AddField(
            model_name='discountforproduct',
            name='discount',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.DiscountBase'),
        ),
        migrations.AddField(
            model_name='discountforproduct',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.Product'),
        ),
        migrations.AddField(
            model_name='discountforcategory',
            name='discount',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='registrasion.DiscountBase'),
        ),
        migrations.AddField(
            model_name='cart',
            name='vouchers',
            field=models.ManyToManyField(blank=True, to='registrasion.Voucher'),
        ),
        migrations.AddField(
            model_name='attendee',
            name='guided_categories_complete',
            field=models.ManyToManyField(to='registrasion.Category'),
        ),
        migrations.AddField(
            model_name='attendee',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='creditnoterefund',
            name='parent',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='registrasion.CreditNote'),
        ),
        migrations.AlterIndexTogether(
            name='cart',
            index_together=set([('status', 'user'), ('status', 'time_last_updated')]),
        ),
    ]
