import dataclasses

from types import Timestamp
from utils.misc import ts_now

ORACLE_PENALTY_THRESHOLD_COUNT = 5
ORACLE_PENALTY_TS = 1800

@dataclasses.dataclass(init=True, repr=True, eq=False, order=False, unsafe_hash=False, frozen=False)  # noqa: E501
class PenaltyInfo:
    last_penalized_ts: Timestamp
    query_failures_count: int

    def note_failure_or_penalize(self) -> None:
        if self.query_failures_count >= ORACLE_PENALTY_THRESHOLD_COUNT:
            self.last_penalized_ts = ts_now()
            self.query_failures_count = 0
        else:
            self.query_failures_count += 1

class PenalizablePriceOracleMixin:
    def __init__(self) -> None:
        self.penalty_info = PenaltyInfo(last_penalized_ts=Timestamp(0), query_failures_count=0)

    def is_penalized(self) -> bool:
        if self.penalty_info.query_failures_count == ORACLE_PENALTY_THRESHOLD_COUNT:
            self.penalty_info.note_failure_or_penalize()
        return ts_now() - self.penalty_info.last_penalized_ts <= ORACLE_PENALTY_TS

