import logging
from collections.abc import Sequence
from contextlib import suppress
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from assets.asset import Asset
from backend.logging import BackendLogsAdapter
from constants import ONE
from constants.assets import A_KFEE, A_USD
from errors.asset import UnknownAsset, WrongAssetType
from fval import FVal
from globalcommon.manual_price_oracles import ManualPriceOracle
from history.types import HistoricalPriceOracle, HistoricalPriceOracleInstance
from types import Timestamp, Price

if TYPE_CHECKING:
    from externalapis.coingecko import Coingecko

logger = logging.getLogger(__name__)
log = BackendLogsAdapter(logger)

def query_usd_price_or_user_default(
        asset: Asset,
        time: Timestamp,
        default_value: FVal
) -> Price:
    pass

class PriceHistorian:
    _instance: Optional['PriceHistorian'] = None
    _cryptocompare: 'Cryptocompare'
    _coingecko: 'Coingecko'
    _defillama: 'Defillama'
    _manual: ManualPriceOracle
    _oracles: Optional[Sequence[HistoricalPriceOracle]] = None
    _oracle_instances: Optional[list[HistoricalPriceOracleInstance]] = None

    def __new__(
            cls,
            data_directory: Optional[Path] = None,
            cryptocompare: Optional['Cryptocompare'] = None,
            coingecko: Optional['Coingecko'] = None,
            defillama: Optional['Defillama'] = None
    ) -> 'PriceHistorian':
        if PriceHistorian._instance is not None:
            return PriceHistorian._instance

        error_msg = 'arguments should be given at the first instantiation'
        assert data_directory, error_msg
        assert cryptocompare, error_msg
        assert coingecko, error_msg
        assert defillama, error_msg

        PriceHistorian.__instance = object.__new__(cls)
        PriceHistorian._cryptocompare = cryptocompare
        PriceHistorian._coingecko = coingecko
        PriceHistorian._defillama = defillama
        PriceHistorian._manual = ManualPriceOracle()

        return PriceHistorian.__instance

    @staticmethod
    def set_oracles_order(oracles: Sequence[HistoricalPriceOracle]) -> None:
        assert len(oracles) != 0 and len(oracles) == len(set(oracles)), (
            "Oracle can't be empty or have repeated items"
        )
        instance = PriceHistorian()
        instance._oracles = oracles
        instance._oracle_instances = [getattr(instance, f'_{oracle!s}') for oracle in oracles]

    @staticmethod
    def get_price_for_special_asset(
            from_asset: Asset,
            to_asset: Asset,
            timestamp: Timestamp
    ) -> Optional[Price]:
        """
        Query the historical price on `timestamp` for `from_asset` in `to_asset`
        for the case where `from_asset` needs a special handling.

        Can return None if the from asset is not in the list of special cases

        Args:
            from_asset: The ticker symbol of the asset for which we want to know
                        the price.
            to_asset: The ticker symbol of the asset against which we want to
                      know the price.
            timestamp: The timestamp at which to query the price

        May raise:
        - NoPriceForGivenTimestamp if we can't find a price for the asset in the given
        timestamp from the external service.
        """

        if from_asset == A_KFEE:
            # for KFEE the price is fixed at 0.01$
            usd_price = Price(FVal(0.01))
            if to_asset == A_USD:
                return usd_price

            price_mapping = PriceHistorian().query_historical_price(
                from_asset=A_USD,
                to_asset=to_asset,
                timestamp=timestamp,
            )
            return Price(usd_price * price_mapping)
        return None

    @staticmethod
    def query_historical_price(
            from_asset: Asset,
            to_asset: Asset,
            timestamp: Timestamp
    ) -> Price:
        log.debug(
            'Querying historical price',
            from_asset=from_asset,
            to_asset=to_asset,
            timestamp=timestamp,
        )

        if from_asset == to_asset:
            return Price(ONE)

        special_asset_price = PriceHistorian().get_price_for_special_asset(
            from_asset=from_asset,
            to_asset=to_asset,
            timestamp=timestamp
        )

        if special_asset_price is not None:
            return special_asset_price

        # Querying historical forex data is attempted first via the external apis
        # and then via any price oracle that has fiat to fiat.
        with suppress(UnknownAsset, WrongAssetType):
            from_asset = from_asset.resolve_to_fiat_asset()
            to_asset = to_asset.resolve_to_fiat_asset()
            price = Inquirer()




