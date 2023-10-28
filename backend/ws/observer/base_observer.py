import hashlib
from copy import deepcopy
from typing import Optional, Any, Dict, Iterable, Generator, Callable

from ws.consumers import AsyncAPIConsumer
from ws.observer.utils import ObjPartial


class BaseObserver:
    def __init__(self, func, partition: str ="*"):
        self.func = func
        self._serializer = None
        self._group_names_for_signal = None
        self._group_names_for_consumer  = None

        self._stable_observer_id = (
            f"{partition}-"
            f"{self.__class__.__name__}-"
            f"{self.func.__module__}."
            f"{self.func.__name__}"
        )

    async def __call__(
        self, message, consumer: Optional[AsyncAPIConsumer] = None, **kwargs
    ):
        message = deepcopy(message)
        message_body = message.pop("body", {})
        message_type = message.pop("type")
        group = message.get("group")
        if consumer is not None:
            requests = consumer._observer_group_to_request_id[self._stable_observer_id][
                group
            ]
            return await self.func(
                consumer,
                message_body,
                observer=self,
                message_type=message_type,
                subscribing_request_ids=list(requests),
                **message,
                **kwargs
            )
        return await self.func(
            consumer,
            message_body,
            observer=self,
            message_type=message_type,
            subscribing_request_ids=[],
            **message,
            **kwargs,
        )

    def __get__(self, parent, objtype):
        if parent is None:
            return self
        return ObjPartial(self, consumer=parent)

    def serialize(self, signal, *args, **kwargs) -> Dict[str, Any]:
        message_body = {}
        if self._serializer:
            message_body = self._serializer(self, signal, *args, **kwargs)

        message = dict(type=self.func.__name__.replace("_", "."), body=message_body)
        return message

    def serializer(self, func):
        """
        .. note::
            Should be used as a method decorator eg: `@observered_handler.serilizer`
        The method that this wraps is evaluated jsust after the observer is triggered before the result is sent over
        the channel layer. That means you *DO NOT* have access to user or other request information.

        The result of this method is what is sent over the channel layer.
        If you need to modify that with user specific information then you need to do that in observer handler method.

        .. code-block:: python

            class MyConsumer(GenericAsyncAPIConsumer):
                queryset = User.objects.all()
                serializer_class = UserSerializer

                @model_observer(Comment)
                async def comment_activity(self, message, observer=None, subscribing_request_ids=[], **kwargs):
                    ...

                @comment_activity.serializer
                def comment_activity(self, instance: Comment, action, **kwargs):
                    return CommentSerializer(instance).data

        The advantage of doing serialization at this point is that it happens only once even if 1000s of consumers are
        subscribed to the event.
        """
        self._serializer = func
        return self

    async def subscribe(self, consumer: AsyncAPIConsumer, *args, request_id=None, **kwargs) -> Iterable[str]:
        groups = list(self._group_names_for_consumer(*args, consumer=consumer, **kwargs))
        for group_name in groups:
            if (
                group_name
                in consumer._observer_group_to_request_id[self._stable_observer_id]
            ):
                # unsubscribe all requests to this group
                if request_id is None:
                    consumer._observer_group_to_request_id[
                        self._stable_observer_id
                    ].pop(group_name)
                else:
                    consumer._observer_group_to_request_id[self._stable_observer_id][
                        group_name
                    ].remove(request_id)

            if (
                len(consumer._observer_group_to_request_id[self._stable_observer_id][group_name]) > 0
            ):
                await consumer.remove_group(group_name)
        return groups

    def group_names_for_consumer(self, consumer: AsyncAPIConsumer, *args, **kwargs) -> Generator[str, None, None]:
        if self._group_names_for_consumer:
            for group in self._group_names_for_consumer(
                self, *args, consumer=consumer, **kwargs
            ):
                yield self.clean_group_name(
                    "{}-{}".format(self._stable_observer_id, group)
                )
            return
        for group in self.group_names(*args, **kwargs):
            yield self.clean_group_name(group)

    def group_names_for_signal(self, *args, **kwargs) -> Generator[str, None, None]:
        if self._group_names_for_signal:
            for group in self._group_names_for_signal(self, *args, **kwargs):
                yield self.clean_group_name(
                    "{}-{}".format(self._stable_observer_id, group)
                )
            return
        for group in self.group_names(*args, **kwargs):
            yield self.clean_group_name(group)

    def group_names(self, *args, **kwargs):
        raise NotImplementedError

    def groups_for_consumer(self, func: Callable[["BaseObserver", AsyncAPIConsumer], Generator[str, None, None],]):
        """
        .. note::
            Should be used as a method decorator eg: `@observed_handler.groups_for_consumer`


        The decorated method is used when :meth:`subscribe` and :meth:`unsubscribe` are called to enumerate the
        corresponding groups to un/subscribe to.

        The `args` and `kwargs` providing to :meth:`subscribe` and :meth:`unsubscribe` are passed here to enable this.

        .. code-block:: python

                @classroom_change_handler.groups_for_consumer
                def classroom_change_handler(self, school=None, classroom=None, **kwargs):
                    # This is called when you subscribe/unsubscribe
                    if school is not None:
                        yield f'-school__{school.pk}'
                    if classroom is not None:
                        yield f'-pk__{classroom.pk}'

                @action()
                async def subscribe_to_classrooms_in_school(self, school_pk, request_id, **kwargs):
                    # check user has permission to do this
                    await self.classroom_change_handler.subscribe(school=school, request_id=request_id)

                @action()
                async def subscribe_to_classroom(self, classroom_pk, request_id, **kwargs):
                    # check user has permission to do this
                    await self.classroom_change_handler.subscribe(classroom=classroom, request_id=request_id)

        It is important that a corresponding :meth:`groups_for_signal` method is provided that enumerates the groups
        that each event is sent to.
        """
        self._group_names_for_consumer = func
        return self

    def groups_for_signal(self, func: Callable[..., Generator[str, None, None]]):
        """
        .. note::
            Should be used as a method decorator eg: `@observered.groups_for_signal`

        THe decorated method is used when :meth:`subscribe` and :meth:`unsubscribe` are
        passed here to enable this

        .. code-block:: python
            @classroom_change_handler.groups_for_consumer
                def classroom_change_handler(self, school=None, classroom=None, **kwargs):
                    # This is called when you subscribe/unsubscribe
                    if school is not None:
                        yield f'-school__{school.pk}'
                    if classroom is not None:
                        yield f'-pk__{classroom.pk}'

                @action()
                async def subscribe_to_classrooms_in_school(self, school_pk, request_id, **kwargs):
                    # check user has permission to do this
                    await self.classroom_change_handler.subscribe(school=school, request_id=request_id)

                @action()
                async def subscribe_to_classroom(self, classroom_pk, request_id, **kwargs):
                    # check user has permission to do this
                    await self.classroom_change_handler.subscribe(classroom=classroom, request_id=request_id)

        It is important that a corresponding :meth:`groups_for_signal` method is provided that enumerates the groups
        that each event is sent to.
        """
        self._group_names_for_consumer = func
        return self

    def groups_for_signal(self, func: Callable[..., Generator[str, None, None]]):
        """
        .. note::
            Should be used as a method decorator eg: `@observed_handler.groups_for_signal`


        The decorated method is used whenever an event happens that the observer is observing
        (even if nothing is subscribed).

        The role of this method is to enumerate the groups that the event should be sent over.

        .. code-block:: python

            @classroom_change_handler.groups_for_signal
            def classroom_change_handler(self, instance: models.Classroom, **kwargs):
                yield f'-school__{instance.school_id}'
                yield f'-pk__{instance.pk}'

        It is important that a corresponding :meth:`groups_for_consumer` method is provided to enable the consumers to
        correctly select which groups to subscribe to.
        """
        self._group_names_for_signal = func
        return self

    def groups(self, func):
        self._group_names_for_consumer = func
        self._group_names_for_signal = func
        return self

    def clean_group_name(self, name):
        # Some channel layers have a max group name length
        return f"DCRF-{hashlib.sha256(name.encode()).hexdigest()}"