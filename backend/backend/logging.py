import argparse
import logging.config
import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import gevent

from greenlets.utils import get_greenlet_name
from utils.misc import is_production, timestamp_to_date, ts_now

PYWSGI_RE = re.compile(r'\[(.*)\] ')

TRACE = logging.DEBUG - 5

def add_logging_level(
    level_name: str,
    level_num: int,
    method_name: Optional[str] = None,
) -> None:
    if not method_name:
        method_name = level_name.lower()

    if hasattr(logging, level_name):
        raise AttributeError(f'{level_name} already defined in logging module')
    if hasattr(logging, method_name):
        raise AttributeError(f'{method_name} already defined in logging module')
    if hasattr(logging.getLoggerClass(), method_name):
        raise AttributeError(f'{method_name} already defined in logger class')

    def log_for_level(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(level_num):
            self._log(level_num, message, args, **kwargs)  # pylint:disable=protected-access

    def log_to_root(message: str, *args: Any, **kwargs: Any) -> None:
        logging.log(level_num, message, *args, **kwargs)

    logging.addLevelName(level_num, level_name)
    setattr(logging, level_name, level_num)
    setattr(logging.getLoggerClass(), method_name, log_for_level)
    setattr(logging, method_name, log_to_root)


if TYPE_CHECKING:
    class BackendLogger(logging.Logger):
        def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
            ...

class BackendLogsAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger):
        super().__init__(logger, extra={})

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple(str, dict):
        msg = str(msg)
        greenlet = gevent.getcurrent()
        greenlet_name = get_greenlet_name(greenlet)
        msg = greenlet_name + ': ' + msg + ','.join(f' {a[0]}={a[1]}' for a in kwargs.items())
        return msg, {}

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
       self.log(TRACE, msg, args, **kwargs)

class PywsgiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = PYWSGI_RE.sub('', record.msg)
        return True

def configure_logging(args: argparse.Namespace) -> None:
    loglevel = args.loglevel.upper()
    formatters = {
        'default': {
            'format': '[%(asctime)s] %(levelname)s %(name)s %(message)s',
            'datefmt': '%d/%m/%Y %H:%M:%S %Z',
        },
    }

    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'level': loglevel,
            'formatter': 'default',
        },
    }

    if args.max_logfiles_num < 0:
        backups_num = 0
    else:
        backups_num = args.max_logfiles_num - 1

    if args.logtarget == 'file':
        given_filepath = Path(args.logfile)
        filepath = given_filepath
        if not is_production():
            date = timestamp_to_date(
                ts=ts_now(),
                formatstr= '%Y%m%d_%H%M%S',
                treat_as_local=True
            )
            filepath = filepath.parent | f'{date}_{given_filepath.name}'

        selected_handlers = ['file']
        single_log_max_bytes = int(
            (args.max_size_in_mb_all_logs * 1024 * 1000) / args.max_logfiles_num,
        )
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': filepath,
            'mode': 'a',
            'maxBytes': single_log_max_bytes,
            'backupCount': backups_num,
            'level': loglevel,
            'formatter': 'default',
            'encoding': 'utf-8',
        }
    else:
        selected_handlers = ['console']

    filters = {
        'pywsgi': {
            '()': PywsgiFilter
        }
    }

    loggers: dict[str, Any] = {
        '': {  # root logger
            'level': loglevel,
            'handlers': selected_handlers,
        },
        # 'backend.api.server.pywsgi': {
        #     'level': loglevel,
        #     'handlers': selected_handlers,
        #     'filters': ['pywsgi'],
        #     'propagate': False,
        # },
    }
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'filters': filters,  # type: ignore [typeddict-item]
        'formatters': formatters,  # type: ignore [typeddict-item]
        'handlers': handlers,
        'loggers': loggers,
    })

    if not args.logfromothermodules:
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.CRITICAL)
        logging.getLogger('substrateinterface.base').setLevel(logging.CRITICAL)
        logging.getLogger('eth_hash').setLevel(logging.CRITICAL)
        logging.getLogger('vcr').setLevel(logging.CRITICAL)