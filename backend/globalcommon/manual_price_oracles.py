import logging
from typing import Optional

from assets.asset import Asset
from backend.logging import BackendLogsAdapter
from crypto.models import PriceHistory
from errors.price import NoPriceForGivenTimestamp
from history.types import HistoricalPriceOracle
from intefaces import CurrentPriceOracleInterface
from types import Timestamp

logger = logging.getLogger(__name__)
log = BackendLogsAdapter(logger)

class ManualPriceOracle:
    def can_query_history(
            self,
            from_asset: Asset,  # pylint: disable=unused-argument
            to_asset: Asset,  # pylint: disable=unused-argument
            timestamp: Timestamp,  # pylint: disable=unused-argument
            seconds: Optional[int] = None,  # pylint: disable=unused-argument
    ) -> bool:
        return True

    @classmethod
    def query_historical_price(
            cls,
            from_asset: Asset, to_asset: Asset,
            timestamp: Timestamp
    ):
        price_entry = PriceHistory(
            from_asset=from_asset,
            to_asset=to_asset,
            timestamp=timestamp,
            max_seconds_distance=3600,
            source_type=HistoricalPriceOracle.MANUAL,
        )

        if price_entry is not None:
            log.debug('Got historical manual price', from_asset=from_asset, to_asset=to_asset, timestamp=timestamp)  # noqa: E501
            return price_entry.price

        raise  NoPriceForGivenTimestamp(
            from_asset=from_asset,
            to_asset=to_asset,
            time=timestamp,
        )

# class ManualCurrentOracle(CurrentPriceOracleInterface):
#     def __init__(self):
#         super().__init__(oracle_name="manual current price oracle")


