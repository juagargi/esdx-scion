# Generated by Django 4.0.3 on 2022-05-21 16:03

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import re
import util.conversion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AS',
            fields=[
                ('iaid', models.CharField(max_length=255, primary_key=True, serialize=False, validators=[util.conversion._ia_validator], verbose_name='The IA id like 1-ff00:1:1')),
                ('certificate_pem', models.TextField()),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'verbose_name': 'AS in the IXP',
            },
        ),
        migrations.CreateModel(
            name='Broker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('certificate_pem', models.TextField()),
                ('key_pem', models.TextField()),
            ],
            options={
                'verbose_name': 'Broker is the IXP',
            },
        ),
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('iaid', models.CharField(max_length=255, validators=[util.conversion._ia_validator], verbose_name='The IA id like 1-ff00:1:1')),
                ('iscore', models.BooleanField()),
                ('signature', models.TextField()),
                ('notbefore', models.DateTimeField()),
                ('notafter', models.DateTimeField()),
                ('reachable_paths', models.TextField()),
                ('qos_class', models.IntegerField()),
                ('price_per_nanounit', models.IntegerField()),
                ('bw_profile', models.TextField(validators=[django.core.validators.RegexValidator(re.compile('^\\d+(?:,\\d+)*\\Z'), code='invalid', message=None)])),
            ],
            options={
                'verbose_name': 'Bandwidth Offer by AS',
            },
        ),
        migrations.CreateModel(
            name='PurchaseOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signature', models.TextField()),
                ('bw_profile', models.TextField(validators=[django.core.validators.RegexValidator(re.compile('^\\d+(?:,\\d+)*\\Z'), code='invalid', message=None)])),
                ('starting_on', models.DateTimeField()),
                ('buyer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='market.as')),
                ('offer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='purchase_order', to='market.offer')),
            ],
            options={
                'verbose_name': 'Signed Purchase Order',
            },
        ),
        migrations.CreateModel(
            name='Contract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField()),
                ('signature_broker', models.TextField()),
                ('purchase_order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='contract', to='market.purchaseorder')),
            ],
            options={
                'verbose_name': 'Contract',
            },
        ),
    ]
