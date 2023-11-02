from errors.serialization import DeserializationError
from fval import AcceptableFValInitInput, FVal
from types import Price


def deserialize_price(amount: AcceptableFValInitInput) -> Price:
    try:
        result = Price(FVal(amount))
    except ValueError as e:
        raise DeserializationError(f'Failed to deserialize a price/rate entry: {e!s}') from e

    return result
