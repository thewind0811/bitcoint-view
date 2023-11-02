from django.db import models

from crypto.models import Asset


class PriceHistorySourceType(models.Model):
    type = models.CharField(primary_key=True, null=False, blank=False, max_length=1)
    seq = models.IntegerField(unique=True)

    class Meta:
        db_table = 'price_history_source_types'

class PriceHistory(models.Model):
    from_asset = models.ForeignKey(Asset, related_name="price_history_from_identifier", null=False, blank=False, on_delete=models.CASCADE)
    to_asset = models.ForeignKey(Asset, related_name="price_history_to_identifier", null=False, blank=False, on_delete=models.CASCADE)
    source_type = models.ForeignKey(PriceHistorySourceType, related_name="price_history_source_types", on_delete=models.CASCADE,
                                    null=False, blank=False)
    timestamp = models.IntegerField(null=False, blank=False)
    price = models.TextField(null=False, blank=False)

    class Meta:
        db_table = 'price_history'

