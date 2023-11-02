import logging
from collections.abc import Iterable, Sequence
from functools import wraps
from http import HTTPStatus
from json.decoder import JSONDecodeError
from typing import Any, Callable, NamedTuple, Optional, Union, cast
from urllib.parse import urlparse

import gevent
import requests
from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import BlockNotFound, SubstrateRequestException
from websocket import WebSocketException