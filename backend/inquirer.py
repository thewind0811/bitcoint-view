import logging
import operator
from collections.abc import Iterable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, Optional, Union

from assets.asset import EvmToken, Asset, FiatAsset
from backend.logging import BackendLogsAdapter
from constants import ONE
from constants.assets import A_YV1_RENWSBTC, A_FARM_CRVRENWBTC, A_FARM_RENBTC, A_FARM_WBTC, A_CRV_RENWBTC, \
    A_CRVP_RENWSBTC, A_YV1_DAIUSDCTBUSD, A_CRVP_DAIUSDCTBUSD, A_CRVP_DAIUSDCTTUSD, A_YV1_DAIUSDCTTUSD, A_CRV_YPAX, \
    A_CRV_GUSD, A_CRV_3CRV, A_YV1_3CRV, A_CRV_3CRVSUSD, A_YV1_ALINK, A_YV1_DAI, A_YV1_WETH, A_YV1_YFI, A_YV1_USDT, \
    A_YV1_USDC, A_YV1_TUSD, A_YV1_GUSD, A_FARM_USDC, A_FARM_USDT, A_FARM_DAI, A_FARM_TUSD, A_FARM_WETH, A_3CRV, A_USD, \
    A_WETH, A_BSQ, A_BTC, A_KFEE
from constants.prices import ZERO_PRICE
from errors.asset import WrongAssetType, UnknownAsset
from errors.defi import DefiPoolError
from errors.misc import RemoteError
from errors.price import PriceQueryUnsupportedAsset
from errors.serialization import DeserializationError
from fval import FVal
from intefaces import CurrentPriceOracleInterface
from oracles.structures import CurrentPriceOracle
from types import Price, LP_TOKEN_AS_POOL_PROTOCOLS, Timestamp, ChainID, ProtocolsWithPriceLogic
from utils.misc import ts_now
from utils.mixins.penalizable_oracle import PenalizablePriceOracleMixin

if TYPE_CHECKING:
    from chain.ethereum.oracles.uniswap import UniswapV2Oracle, UniswapV3Oracle
    from chain.evm.manager import EvmManager
    from externalapis.coingecko import Coingecko
    from externalapis.cryptocompare import Cryptocompare
    from externalapis.defillama import Defillama
    from globalcommon.manual_price_oracles import ManualCurrentOracle
    from user_messages import MessagesAggregator
    

logger = logging.getLogger(__name__)
log = BackendLogsAdapter(logger)

CURRENT_PRICE_CACHE_SECS = 300  # 5 mins
DEFAULT_RATE_LIMIT_WAITING_TIME = 60  # seconds
BTC_PER_BSQ = FVal('0.00000100')

ASSETS_UNDERLYING_BTC = (
    A_YV1_RENWSBTC,
    A_FARM_CRVRENWBTC,
    A_FARM_RENBTC,
    A_FARM_WBTC,
    A_CRV_RENWBTC,
    A_CRVP_RENWSBTC,
)


CurrentPriceOracleInstance = Union[
    'Coingecko',
    'Cryptocompare',
    'UniswapV3Oracle',
    'UniswapV2Oracle',
    'ManualCurrentOracle',
]

def _check_curve_contract_call(decoded: tuple[Any, ...]) -> bool:
    """
    Checks the result of decoding curve contract methods to verify:
    - The result is a tuple
    - It should return only one value
    - The value should be an integer
    Args:
        decoded:

    Returns:
        true if the decode was correct
    """
    return (
        isinstance(decoded, tuple) and
        len(decoded) == 1 and
        isinstance(decoded[0], int)
    )

def get_underlying_asset_price(token: EvmToken) -> tuple[Optional[Price], CurrentPriceOracle]:
    """Gets the underlying asset price for the given ethereum token

    TODO: This should be eventually pulled from the assets DB. All of these
    need to be updated, to contain proper protocol, and underlying assets.

    This function is neither in inquirer.py or chain/ethereum/defi.py
    due to recursive import problems
    """
    price, oracle = None, CurrentPriceOracle.BLOCKCHAIN
    if token.protocol in LP_TOKEN_AS_POOL_PROTOCOLS:
        price = Inquirer().find_lp_price_from_uniswaplike_pool(token)

class CachedPriceEntry(NamedTuple):
    price: Price
    time: Timestamp
    oracle: CurrentPriceOracle
    used_main_currency: bool

class Inquirer:
    __instance: Optional['Inquirer'] = None
    _cached_forex_data: dict
    _cached_current_price: dict[tuple[Asset, Asset], CachedPriceEntry]
    _data_directory: Path
    _cryptocompare: 'Cryptocompare'
    _coingecko: 'Coingecko'
    _defillama: 'Defillama'
    _manualcurrent: 'ManualCurrentOracle'
    _uniswapv2: Optional['UniswapV2Oracle'] = None
    _uniswapv3: Optional['UniswapV3Oracle'] = None
    _evm_managers: dict[ChainID, 'EvmManager']
    _oracles: Optional[Sequence[CurrentPriceOracle]] = None
    _oracle_instances: Optional[list[CurrentPriceOracleInstance]] = None
    _oracles_not_onchain: Optional[Sequence[CurrentPriceOracle]] = None
    _oracle_instances_not_onchain: Optional[list[CurrentPriceOracleInstance]] = None
    _msg_aggregator: 'MessagesAggregator'
    # save only the identifier of the special tokens since we only check if assets are in this set
    special_tokens: set[str]
    weth: EvmToken
    usd: FiatAsset

    def __new__(
            cls,
            data_dir: Optional[Path] = None,
            coingecko: Optional[Coingecko] = None,
            cryptocompare: Optional[Cryptocompare] = None,
            defillama: Optional[Defillama] = None,
            manualcurrent: Optional[ManualCurrentOracle] = None,
            msg_aggregator: Optional['MessagesAggregator'] = None
    ) -> 'Inquirer':
        if Inquirer.__instance is not None:
            return Inquirer.__instance

        error_msg = 'arguments should be given at the first instantiation'
        assert data_dir, error_msg
        assert cryptocompare, error_msg
        assert coingecko, error_msg
        assert defillama, error_msg
        assert manualcurrent, error_msg
        assert msg_aggregator, error_msg

        Inquirer.__instance = object.__new__(cls)
        Inquirer._cryptocompare = cryptocompare
        Inquirer._coingecko = coingecko
        Inquirer._defillama = defillama
        Inquirer._manualcurrent = manualcurrent
        Inquirer._cached_current_price = {}
        Inquirer._evm_managers = {}
        Inquirer._msg_aggregator = msg_aggregator
        Inquirer.special_tokens = {
            A_YV1_DAIUSDCTBUSD.identifier,
            A_CRVP_DAIUSDCTBUSD.identifier,
            A_CRVP_DAIUSDCTTUSD.identifier,
            A_YV1_DAIUSDCTTUSD.identifier,
            A_YV1_DAIUSDCTTUSD.identifier,
            A_CRVP_RENWSBTC.identifier,
            A_YV1_RENWSBTC.identifier,
            A_CRV_RENWBTC.identifier,
            A_CRV_YPAX.identifier,
            A_CRV_GUSD.identifier,
            A_CRV_3CRV.identifier,
            A_YV1_3CRV.identifier,
            A_CRV_3CRVSUSD.identifier,
            A_YV1_ALINK.identifier,
            A_YV1_DAI.identifier,
            A_YV1_WETH.identifier,
            A_YV1_YFI.identifier,
            A_YV1_USDT.identifier,
            A_YV1_USDC.identifier,
            A_YV1_TUSD.identifier,
            A_YV1_GUSD.identifier,
            A_FARM_USDC.identifier,
            A_FARM_USDT.identifier,
            A_FARM_DAI.identifier,
            A_FARM_TUSD.identifier,
            A_FARM_WETH.identifier,
            A_FARM_WBTC.identifier,
            A_FARM_RENBTC.identifier,
            A_FARM_CRVRENWBTC.identifier,
            A_3CRV.identifier,
        }
        try:
            Inquirer.usd = A_USD.resolve_to_fiat_asset()
            Inquirer.weth = A_WETH.resolve_to_evm_token()
        except (UnknownAsset, WrongAssetType) as e:
            message = f'One of the base assets was deleted/modified from the DB: {e!s}'
            log.critical(message)
            raise RuntimeError(message + '. Add it back manually or contact support') from e

        return Inquirer.__instance

    @staticmethod
    def inject_evm_manager(evm_managers: Sequence[tuple[ChainID, 'EvmManager']]) -> None:
        instance = Inquirer()
        for chain_id, evm_manager in evm_managers:
            instance._evm_managers[chain_id] = evm_manager

    def get_evm_manager(self, chain_id: ChainID) -> 'EvmManager':
        evm_manager = self._evm_managers.get(chain_id)
        assert evm_manager is not None, f'evm manager for chain id {chain_id} should have been injected'
        return evm_manager

    @staticmethod
    def add_defi_oracles(
            uniswap_v2: Optional['UniswapV2Oracle'],
            uniswap_v3: Optional['UniswapV3Oracle']
    ) -> None:
        Inquirer()._uniswapv2 = uniswap_v2
        Inquirer()._uniswapv3 = uniswap_v3

    @staticmethod
    def get_cached_current_price_entry(
            cache_key: tuple[Asset, Asset],
            match_main_currency: bool
    ) -> Optional[CachedPriceEntry]:
        cache = Inquirer()._cached_current_price.get(cache_key, None)
        if cache is None or ts_now() - cache.time > CURRENT_PRICE_CACHE_SECS or cache.used_main_currency != match_main_currency:  # noqa: E501
            return None
        return cache

    @staticmethod
    def remove_cache_prices_for_asset(pairs_to_invalidate: list(tuple[Asset, Asset])) -> None:
        """Deletes all prices cache that contains any asset in the possible pairs"""
        assets_to_invalidate = set()
        for asset_a, asset_b in pairs_to_invalidate:
            assets_to_invalidate.add(asset_a)
            assets_to_invalidate.add(asset_b)

        for asset_pair in list(Inquirer()._cached_current_price):
            if asset_pair[0] in assets_to_invalidate or asset_pair[1] in assets_to_invalidate:
                Inquirer()._cached_current_price.pop(asset_pair, None)

    @staticmethod
    def remove_cached_current_price_entry(cache_key: tuple[Asset, Asset]) -> None:
        Inquirer()._cached_current_price.pop(cache_key, None)
    
    @staticmethod
    def set_oracles_order(oracles: Sequence[CurrentPriceOracle]) -> None:
        assert len(oracles) != 0 and len(oracles) == len(set(oracles)), (
            "Oracles can't be empty or have repeated items"
        )
        instance = Inquirer()
        instance._oracles = oracles
        instance._oracle_instances = [getattr(instance, f'_{oracle!s}') for oracle in oracles]
        instance._oracles_not_onchain = []
        instance._oracle_instances_not_onchain = []
        for oracle, oracle_instance in zip(instance._oracles, instance._oracle_instances):
            if oracle not in (CurrentPriceOracle.UNISWAPV2, CurrentPriceOracle.UNISWAPV3):
                instance._oracles_not_onchain.append(oracle)
                instance._oracle_instances_not_onchain.append(oracle_instance)

    @staticmethod
    def _query_oracle_instances(
            from_asset: Asset,
            to_asset: Asset,
            coming_from_latest_price: bool,
            skip_onchains: bool = False,
            match_main_currency: bool = False
    ) -> tuple[Price, CurrentPriceOracle, bool]:
        """
        Query oracle instances.
        `coming_from_latest_price` is used by manual latest price oracle to handle price loops.
        Args:
            from_asset:
            to_asset:
            coming_from_latest_price:
            skip_onchains:
            match_main_currency:

        Returns:

        """
        instance = Inquirer()
        cache_key = (from_asset, to_asset)
        assert (
                instance._oracles is not None and
                instance._oracle_instances is not None and
                instance._oracles_not_onchain is not None and
                instance._oracle_instances_not_onchain is not None
        ), (
            'Inquirer should never be called before setting the oracles'
        )

        if from_asset.is_asset_with_oracles() is True:
            from_asset = from_asset.resolve_to_asset_with_oracles()
            to_asset = to_asset.resolve_to_asset_with_oracles()
            if skip_onchains:
                oracles = instance._oracles_not_onchain
                oracle_instances = instance._oracle_instances_not_onchain
            else:
                oracles = instance._oracles
                oracle_instances = instance._oracle_instances
        else:
            oracles = [CurrentPriceOracle.MANUALCURRENT]
            oracles_instances = [instance._manualcurrent]

        price = ZERO_PRICE
        oracle_queried = CurrentPriceOracle.BLOCKCHAIN
        used_main_currency = False
        for oracle, oracles_instance in zip(oracles, oracles_instances):
            if (
                isinstance(oracles_instance, CurrentPriceOracleInterface) and
                    (
                        oracles_instance.rate_limited_in_last(DEFAULT_RATE_LIMIT_WAITING_TIME) is True or
                        isinstance(oracles_instance, PenalizablePriceOracleMixin) and oracles_instance.is_penalized()
                        is True
                    )
            ):
                continue
            try:
                price, used_main_currency = oracles_instance.query_current_price(
                    from_asset=from_asset,
                    to_asset=to_asset,
                    match_main_currency=match_main_currency
                )
            except (DefiPoolError, PriceQueryUnsupportedAsset, RemoteError) as e:
                log.warning(
                    f'Current price oracle {oracle} failed to request {to_asset.identifier} '
                    f'price for {from_asset.identifier} due to: {e!s}'
                )
                continue
            except RecursionError:
                if coming_from_latest_price is True:
                    raise

                instance._msg_aggregator.add_warning(
                    f'Was not able to find price from {from_asset!s} to {to_asset!s} since your '
                    f'manual latest prices form a loop. For now, other oracles will be used.',
                )
                continue

            if price != ZERO_PRICE:
                oracle_queried = oracle
                log.debug(
                    f'Current price oracle {oracle} got price',
                    from_asset=from_asset,
                    to_asset=to_asset,
                    price=price,
                )
                break

        Inquirer._cached_current_price[cache_key] = CachedPriceEntry(
            price=price,
            time=ts_now(),
            oracle=oracle_queried,
            used_main_currency=used_main_currency,
        )
        return price, oracle_queried, used_main_currency

    @staticmethod
    def _find_price(
            from_asset: Asset,
            to_asset: Asset,
            ignore_cache: bool = False,
            skip_onchain: bool = False,
            coming_from_latest_price: bool = False,
            match_main_currency: bool = False
    ) -> tuple[Price, CurrentPriceOracle, bool]:
        """Returns:
        1. The current price of 'from_asset' in 'to_asset' valuation.
        2. Oracle that was used to get the price.
        3. Flag that shows whether returned price is in main currency.
        NB: prices for special symbols in any currency but USD are not supported.

        Returns ZERO_PRICE if all options have been exhausted and errors are logged in the logs.
        `coming_from_latest_price` is used by manual latest price oracle to handle price loops.
        """
        if from_asset == to_asset:
            return Price(ONE), CurrentPriceOracle.MANUALCURRENT, False

        instance = Inquirer()
        if to_asset == A_USD:
            price, oracle, used_main_currency = instance.find_usd_price_and_oracle(
                asset=from_asset,
                ignore_cache=ignore_cache,
                coming_from_latest_price=coming_from_latest_price,
                match_main_currency=match_main_currency
            )
            return price, oracle, used_main_currency

        if ignore_cache is False:
            cache = instance.get_cached_current_price_entry(cache_key=(from_asset, to_asset), match_main_currency=match_main_currency)
            if cache is not None:
                return cache.price, cache.oracle, cache.used_main_currency

        oracle_price, oracle_queried, used_main_currency = instance._query_oracle_instances(
            from_asset=from_asset,
            to_asset=to_asset,
            skip_onchains=skip_onchain,
            coming_from_latest_price=coming_from_latest_price,
            match_main_currency=match_main_currency
        )
        return oracle_price, oracle_queried, used_main_currency

    @staticmethod
    def find_price(
            from_asset: Asset,
            to_asset: Asset,
            ignore_cache: bool = False,
            skip_onchain: bool = False,
            coming_from_latest_price: bool = False,
    ) -> Price:
        """Wrapper around _find_price to ignore oracle queried when getting price"""
        price, _, _ = Inquirer()._find_price(
            from_asset=from_asset,
            to_asset=to_asset,
            ignore_cache=ignore_cache,
            skip_onchain=skip_onchain,
            coming_from_latest_price=coming_from_latest_price,
        )
        return price

    @staticmethod
    def find_price_add_oracle(
            from_asset: Asset,
            to_asset: Asset,
            ignore_cache: bool = False,
            skip_onchain: bool = False,
            coming_from_latest_price: bool = False,
            match_main_currency: bool = False,
    ) -> tuple[Price, CurrentPriceOracle, bool]:
        return Inquirer()._find_price(
            from_asset=from_asset,
            to_asset=to_asset,
            ignore_cache=ignore_cache,
            skip_onchain=skip_onchain,
            coming_from_latest_price=coming_from_latest_price,
            match_main_currency=match_main_currency,
        )

    @staticmethod
    def find_usd_price(
            asset: Asset,
            ignore_cache: bool = False,
            skip_onchain: bool = False,
            coming_from_latest_price: bool = False,
    ) -> Price:
        price, _, _ = Inquirer()._find_usd_price(
            asset=asset,
            ignore_cache=ignore_cache,
            skip_onchain=skip_onchain,
            coming_from_latest_price=coming_from_latest_price,
        )
        return price

    @staticmethod
    def find_usd_price_and_oracle(
            asset: Asset,
            ignore_cache: bool = False,
            skip_onchain: bool = False,
            coming_from_latest_price: bool = False,
            match_main_currency: bool = False,
    ) -> tuple[Price, CurrentPriceOracle, bool]:
        """
        Wrapper around _find_usd_price to include oracle queried when getting usd price and
        flag that shows whether returned price is in main currency
        """
        return Inquirer()._find_usd_price(
            asset=asset,
            ignore_cache=ignore_cache,
            skip_onchain=skip_onchain,
            coming_from_latest_price=coming_from_latest_price,
            match_main_currency=match_main_currency,
        )

    @staticmethod
    def _find_usd_price(
            asset: Asset,
            ignore_cache: bool = False,
            skip_onchain: bool = False,
            coming_from_latest_price: bool = False,
            match_main_currency: bool = False,
    ) -> tuple[Price, CurrentPriceOracle, bool]:
        if asset == A_USD:
            return  Price(ONE), CurrentPriceOracle, False

        instance = Inquirer()
        cache_key = (asset, A_USD)
        if ignore_cache is False:
            cache = instance.get_cached_current_price_entry(cache_key=cache_key,
                                                            match_main_currency=match_main_currency)  # noqa: E501
            if cache is not None:
                return cache.price, cache.oracle, cache.used_main_currency

        try:
            asset = asset.resolve()
        except UnknownAsset:
            log.error(f'Tried to ask for {asset.identifier} price but asset is missing from the DB')
            return ZERO_PRICE, CurrentPriceOracle.FIAT, False

        if isinstance(asset, FiatAsset):
            with suppress(RemoteError):
                price, oracle = instance._query_fiat_pair(base=asset, quote=instance.usd)
                return price, oracle, False

        # continue, asset isn't fiat or a price can be found by one of the oracles
        #Try and check if it is an ethereum token with specified protocol or underflying tokens
        is_known_protocol = False
        underlying_token = None
        if isinstance(asset, EvmToken):
            if asset.protocol is not None:
                is_known_protocol = asset.protocol in ProtocolsWithPriceLogic
            underlying_token = asset.underlying_tokens

            # Check if it is a special token
            if asset.identifier in instance.special_tokens:
                ethereum = instance.get_evm_manager(chain_id=ChainID.ETHEREUM)
                underlying_asset_price, oracle = get_underlying_asset_price(asset)
                usd_price = handle_defi_price_query(
                    ethereum=ethereum.node_inquirer,
                    token=asset,
                    underlying_asset_price=underlying_asset_price
                )
                prince = ZERO_PRICE if usd_price is None else Price(usd_price)
                Inquirer._cached_current_price[cache_key] = CachedPriceEntry(
                    price=price,
                    time=ts_now(),
                    oracle=CurrentPriceOracle.BLOCKCHAIN,
                    used_main_currency=False
                )
                return price, oracle, False

            if is_known_protocol or underlying_token is not None:
                result, oracle = get_underlying_asset_price(asset)
                if result is not None:
                    usd_price = Price(result)
                    Inquirer._cached_current_price[cache_key] = CachedPriceEntry(
                        price=usd_price,
                        time=ts_now(),
                        oracle=oracle,
                        used_main_currency=False,  # function is for usd only, so it doesn't matter
                    )
                    return usd_price, oracle, False
            # else known protocol on-chain query failed. Continue to external oracles

        if asset == A_BSQ:
            try:
                bsq = A_BSQ.resolve_to_crypto_asset()
            except (UnknownAsset, WrongAssetType):
                log.error('Asked for BSQ price but BSQ is missing or misclassified in the db')
                return ZERO_PRICE, oracle, False

            try:
                price_in_btc = get_bisq_market_price(bsq)
                btc_price, oracle, _ = Inquirer().find_usd_price_and_oracle(A_BTC)
                usd_price = Price(price_in_btc * btc_price)
                Inquirer._cached_current_price[cache_key] = CachedPriceEntry(
                    price=usd_price,
                    time=ts_now(),
                    oracle=oracle,
                    used_main_currency=False,  # this is for usd only, so it doesn't matter
                )
            except (RemoteError, DeserializationError) as e:
                msg = f'Could not find price for BSQ. {e!s}'
                instance._msg_aggregator.add_warning(msg)
                return Price(BTC_PER_BSQ * price_in_btc), CurrentPriceOracle.BLOCKCHAIN, False
            else:
                return  usd_price, oracle, False

        if asset == A_KFEE:
            return Price(FVal(0.01)), CurrentPriceOracle.FIAT, False

        price, oracle, used_main_currency = instance._query_oracle_instances(
            from_asset=asset,
            to_asset=A_USD,
            coming_from_latest_price=coming_from_latest_price,
            skip_onchain=skip_onchain,
            match_main_currency=match_main_currency,
        )
        return price, oracle, used_main_currency

    def find_lp_price_from_uniswaplike_pool(self, token: EvmToken) -> Optional[Price]:
        """Calculates the price for a uniswaplike LP token the contract of which is also
        the contract of the pool it represents. For example uniswap or velodrome LP tokens."""
        return lp_price_from_uniswaplike_pool_contract(
            evm_inquirer = self.get_evm_manager(token.chain_id).node_inquirer,
            token=token,
            token_price_func=self.find_usd_price,
            token_price_func_args=[],
            block_identifier='latest'
        )

    def find_curve_pool_price(self, lp_token: EvmToken) -> Optional[Price]:
        """
        1. Obtain the pool for this token
        2. Obtain prices for assets in pool
        3. Obtain the virtual price for share and the balances of each
        token in the pool
        4. Calc the price for a share

        Returns the price of 1 LP token from the pool
        """
        ethereum = self.get_evm_manager(chain_id=ChainID.ETHEREUM)
        ethereum.assure_curve_cache_is_queried_and_decoder_updated()  # type:ignore  # ethereum is an EthereumManager here