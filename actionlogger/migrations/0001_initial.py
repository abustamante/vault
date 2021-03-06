# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Audit',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('user', models.CharField(max_length=30)),
                ('action', models.CharField(max_length=30)),
                ('item', models.CharField(max_length=30)),
                ('through', models.CharField(default=b'vault', max_length=30)),
                ('created_at', models.DateField(auto_now=True)),
            ],
            options={
                'db_table': 'vault_audit',
            },
            bases=(models.Model,),
        ),
    ]
