from django.db import models

class GeneralCache(models.Model):
    key = models.CharField(max_length=255, null=False, blank=False, primary_key=True)
    value = models.CharField(max_length=255, null=False, blank=False, db_index=True)
    last_queried_ts = models.IntegerField(null=False, blank=False)

    class Meta:
        db_table = 'general_cache'

class UniqueCache(models.Model):
    key = models.CharField(max_length=255, null=False, blank=False, primary_key=True)
    value = models.CharField(max_length=255, null=False, blank=False)
    last_queried_ts = models.IntegerField(null=False, blank=False)

    class Meta:
        db_table = 'unique_cache'


# class ContactAbi(models.Model):
#     value = models.TextField(null=False, blank=False)
#     name = models.TextField()
#
#     class Meta:
#         db_table = 'contact_abi'

