import json
import logging
from collections import deque
from typing import TYPE_CHECKING, Any, Optional, Union

from api.websockets.typedefs import WsMessageType
from backend.logging import BackendLogsAdapter

if TYPE_CHECKING:
    from api.websockets.notifier import Notifier

logger = logging.getLogger(__name__)
log = BackendLogsAdapter(logger)

ERROR_MESSAGE_TYPES = {WsMessageType.LEGACY, WsMessageType.BALANCE_SNAPSHOT_ERROR}

class MessagesAggregator:
    """
    This class is passed around where needed and aggregates messages for the user
    """

    def __init__(self) -> None:
        self.warnings: deque = deque()
        self.errors: deque = deque()
        self.notifier: Optional[Notifier] = None

    def _append_warning(self, msg: str) -> None:
        self.warnings.appendleft(msg)

    def add_warning(self, msg: str) -> None:
        log.warning(msg)
        if self.notifier is not None:
            data = {'verbosity': 'warning', 'value': msg}
            self.notifier.broadcast(
                message_type=WsMessageType.LEGACY,
                to_send_data=data,
                failure_callback=self._append_warning,
                failure_callback_args={'msg': msg},
            )
            return

        self.warnings.appendleft(msg)

    def _append_error(self, msg: str) -> None:
        self.errors.appendleft(msg)

    def add_error(self, msg: str) -> None:
        log.error(msg)
        if self.notifier is not None:
            data = {'verbosity': 'error', 'value': msg}
            self.notifier.broadcast(
                message_type=WsMessageType.LEGACY,
                to_send_data=data,
                failure_callback=self._append_error,
                failure_callback_args={'msg': msg},
            )
            return
        self.errors.appendleft(msg)

    def add_message(
            self,
            message_type: WsMessageType,
            data: Union[dict[str, Any], list[Any]],
    ) -> None:
        """Sends a websocket message

        Specify its type and data.

        `wait_on_send` is used to determine if the message should be sent asynchronously
        by spawning a greenlet or if it should just do it synchronously.
        """
        fallback_msg = json.dumps({'type': str(message_type), 'data': data})  # kind of silly to repeat it here. Same code in broadcast  # noqa: E501

        if self.notifier is not None:
            self.notifier.broadcast(
                message_type=message_type,
                to_send_data=data,
                failure_callback=self._append_error,
                failure_callback_args={'msg': fallback_msg},
            )

        elif message_type in ERROR_MESSAGE_TYPES:  # Fallback to polling for error messages
            self.errors.appendleft(fallback_msg)

    def consume_errors(self) -> list[str]:
        result = []
        while len(self.errors) != 0:
            result.append(self.errors.pop())
        return result