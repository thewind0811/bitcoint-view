from django.db import models

from .asset import Asset

class TokenKind(models.Model):
    token_kind = models.CharField(max_length=1, primary_key=True, null=False, blank=False)
    seq = models.IntegerField(null=False, blank=False, unique=True)

    class Meta:
        db_table = "token_kinds"

class EvmToken(models.Model):
    identifier = models.ForeignKey(Asset, on_delete=models.CASCADE, primary_key=True,
                                   null=False, blank=False, related_name="evm_token_identifier", db_column="identifier")
    token_kind = models.ForeignKey(TokenKind, on_delete=models.CASCADE, null=False, blank=False,
                                   related_name="evm_token_kind", db_column="token_kind")
    chain = models.IntegerField(null=False, blank=False)
    address = models.CharField(null=False, blank=False, max_length=42)
    decimals = models.IntegerField()
    protocol = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "evm_tokens"

