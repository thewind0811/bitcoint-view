from typing import Type

from django.db.models import Model


class _GenericModelObserver:
    def __init__(self, func, **kwargs):
        self.func = func
        self._group_names = None
        self._serializer = None

    def bind_to_model(self, model_cls: Type[Model], name: str) -> ModelObserver:
