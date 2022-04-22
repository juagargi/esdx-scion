# Generated by Django 4.0.3 on 2022-04-22 09:31

import django.core.validators
from django.db import migrations, models
import re


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('iaid', models.BigIntegerField()),
                ('iscore', models.BooleanField()),
                ('signature', models.BinaryField()),
                ('notbefore', models.DateTimeField()),
                ('notafter', models.DateTimeField()),
                ('reachable_paths', models.TextField()),
                ('qos_class', models.IntegerField()),
                ('bw_profile', models.TextField(validators=[django.core.validators.RegexValidator(re.compile('^\\d+(?:,\\d+)*\\Z'), code='invalid', message=None)])),
                ('price_per_nanounit', models.IntegerField()),
            ],
            options={
                'verbose_name': 'Bandwidth Offer by AS',
            },
        ),
    ]