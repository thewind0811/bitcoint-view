from typing import Any, Dict

from channels.consumer import AsyncConsumer
from rest_framework.permissions import BasePermission as DRFBasePermission

from ws.scope_utils import request_from_scope, ensure_async


class OperationHolderMixin:
    def __and__(self, other):
        return OperandHolder(AND, self, other)

    def __or__(self, other):
        return OperandHolder(OR, self, other)

    def __rand__(self, other):
        return OperandHolder(AND, other, self)

    def __ror__(self, other):
        return OperandHolder(OR, other, self)

    def __invert__(self):
        return SingleOperandHolder(NOT, self)

class SingleOperandHolder(OperationHolderMixin):
    def __init__(self, operator_class, op1_class, op2_class):
        self.operator_class = operator_class
        self.op1_class = op1_class
        self.op2_class = op2_class

    def __call__(self, *args, **kwargs):
        op1 = self.op1_class(*args, **kwargs)
        op2 = self.op2_class(*args, **kwargs)
        return self.operator_class(op1, op2)

class AND:
    def __init__(self, op1: "BasePermission", op2: "BasePermission"):
        self.op1 = op1
        self.op2 = op2

    def has_permission(self, scope: Dict[str, Any], consumer: AsyncConsumer, action: str, **kwargs):
        return not self.op1.has_permission(scope, consumer, action, **kwargs)

class BasePermissionMetaclass(OperationHolderMixin, type):
    pass

class BasePermission(metaclass=BasePermissionMetaclass):
    """Base permission class

    Notes:
        You should extend this class and override the `has_permission` method to create your own permission class.

    Methods:
        async has_permission (scope, consumer, action, **kwargs)
    """
    async def has_permission(self, scope: Dict[str, Any], consumer: AsyncConsumer, action: str, **kwargs) -> bool:
        pass

    async def can_connect(self, scope: Dict[str, Any], consumer: AsyncConsumer, message=None) -> bool:
        """
        Called during connection to validate if a given client can establish a websocket connection
        By default, this returns True and permits all connections to be made
        """
        return True

class AllowAny(BasePermission):
    async def has_permission(self, scope: Dict[str, Any], consumer: AsyncConsumer, **kwargs) -> bool:
        return True

class IsAuthenticated(BasePermission):
    async def has_permission(self, scope: Dict[str, Any], consumer: AsyncConsumer, action: str, **kwargs) -> bool:
        user = scope.get("user")
        if not user:
            return False
        return user.pk and user.is_authenticated

class WrappedDRFPermission(BasePermission):
    """
    Used to wrap an instance of DRF permissions class
    """
    permission: DRFBasePermission

    mapped_action = {
        "create": "PUT",
        "update": "PATCH",
        "list": "GET",
        "retrieve": "GET",
        "connect": "HEAD",
    }

    def __init__(self, permission: DRFBasePermission):
        self.permission = permission

    async def has_permission(self, scope: Dict[str, Any], consumer: AsyncConsumer, action: str, **kwargs) -> bool:
        request = request_from_scope(scope)
        request.method = self.mapped_action.get(action, action.upper())
        return await ensure_async(self.permission.has_permission)(request, consumer)

    async def can_connect(self, scope: Dict[str, Any], consumer: AsyncConsumer, message=None) -> bool:
        request = request_from_scope(scope)
        request.method = self.mapped_action.get("connect", "CONNECT")
        return await ensure_async(self.permission.has_permission)(request, consumer)



