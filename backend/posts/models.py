from django.conf import settings
from django.db import models


class Post(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=False,
    )

    body = models.CharField(
        max_length=256,
        blank=False
        # TODO: consider adding a min length validator
    )