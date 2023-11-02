from django.db import models

# Create your models here.
class AssetType(models.Model):
    type = models.CharField(max_length=1, null=False, primary_key=True)
    seq = models.IntegerField(unique=True)

    class Meta:
        db_table = "asset_types"

class Asset(models.Model):
    identifier = models.CharField(max_length=255, primary_key=True, null=False)
    name = models.TextField(null=True, blank=True)
    type = models.ForeignKey(AssetType, on_delete=models.CASCADE, related_name="asset_type", db_column="type")

    class Meta:
        db_table = "assets"

class CommonAssetDetail(models.Model):
    identifier = models.ForeignKey(Asset, db_column="identifier", on_delete=models.CASCADE,
                                   related_name="asset_detail_identifier", primary_key=True)
    symbol = models.CharField(max_length=50)
    coingecko = models.CharField(max_length=255)
    cryptocompare = models.CharField(max_length=255)
    forked = models.ForeignKey(Asset, db_column="forked", related_name="asset_detail_forked",
                               on_delete=models.SET_NULL, null=True,
                               blank=True)
    started = models.IntegerField()
    swapped_for = models.ForeignKey(Asset, db_column="swapped_for", null=True, blank=True, on_delete =
    models.SET_NULL, related_name="asset_detail_swapped_for")

    class Meta:
        db_table = "common_asset_details"

# class UserOwnedAsset()
#
#     class Meta:
#         db_table = "user_owned_assets"
#


