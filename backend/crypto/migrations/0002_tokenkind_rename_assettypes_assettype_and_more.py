# Generated by Django 4.2.6 on 2023-10-31 10:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crypto', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TokenKind',
            fields=[
                ('token_kind', models.CharField(max_length=1, primary_key=True, serialize=False)),
                ('seq', models.IntegerField(unique=True)),
            ],
            options={
                'db_table': 'token_kinds',
            },
        ),
        migrations.RenameModel(
            old_name='AssetTypes',
            new_name='AssetType',
        ),
        migrations.AlterField(
            model_name='commonassetdetail',
            name='forked',
            field=models.ForeignKey(blank=True, db_column='forked', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asset_detail_forked', to='crypto.assets'),
        ),
        migrations.RenameModel(
            old_name='Assets',
            new_name='Asset',
        ),
        migrations.CreateModel(
            name='EvmToken',
            fields=[
                ('identifier', models.ForeignKey(db_column='identifier', on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='evm_token_identifier', serialize=False, to='crypto.asset')),
                ('chain', models.IntegerField()),
                ('address', models.CharField(max_length=42)),
                ('decimals', models.IntegerField()),
                ('protocol', models.TextField()),
                ('token_kind', models.ForeignKey(db_column='token_kind', on_delete=django.db.models.deletion.CASCADE, related_name='evm_token_kind', to='crypto.tokenkind')),
            ],
            options={
                'db_table': 'evm_tokens',
            },
        ),
    ]