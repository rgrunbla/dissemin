# Generated by Django 2.2.4 on 2019-09-06 13:52

import django.db.models.deletion

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('deposit', '0017_abstract_required'),
    ]

    operations = [
        migrations.AddField(
            model_name='depositrecord',
            name='license',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='deposit.License'),
        ),
        migrations.AddField(
            model_name='repository',
            name='letter_declaration',
            field=models.CharField(blank=True, max_length=256),
        ),
    ]