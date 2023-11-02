import logging
import traceback
from typing import Any, Callable, Optional

import gevent

from errors.misc import GreenletKilledError
from logging import RotkehlchenLogsAdapter
from user_messages import MessagesAggregator

logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)