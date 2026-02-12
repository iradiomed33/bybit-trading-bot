"""

Управление информацией об инструментах (tickSize, qtyStep, минималы).


Функции:

- Кэширование instrument info с минимизацией API запросов

- Получение параметров округления для цены/количества

- Нормализация ордеров согласно требованиям биржи

- Проверка минимальных значений (qty, notional)


Документация:

- Bybit Instruments: https://bybit-exchange.github.io/docs/v5/market/instrument

- Risk Limit: https://bybit-exchange.github.io/docs/v5/account/risk-limit

"""


import time

from typing import Dict, Any, Optional

from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

from logger import setup_logger


logger = setup_logger(__name__)


# Fallback значения для популярных символов (если instruments-info не работает на testnet)
# Значения взяты из реальных спецификаций Bybit для perpetual futures
DEFAULT_INSTRUMENT_PARAMS = {
    "BTCUSDT": {
        "tickSize": "0.1",
        "qtyStep": "0.001",
        "minOrderQty": "0.001",
        "maxOrderQty": "100.0",
        "minNotional": "5.0",
        "basePrecision": 3,
        "quotePrecision": 1,
    },
    "ETHUSDT": {
        "tickSize": "0.01",
        "qtyStep": "0.01",
        "minOrderQty": "0.01",
        "maxOrderQty": "1000.0",
        "minNotional": "5.0",
        "basePrecision": 2,
        "quotePrecision": 2,
    },
    "SOLUSDT": {
        "tickSize": "0.001",
        "qtyStep": "0.1",
        "minOrderQty": "0.1",
        "maxOrderQty": "10000.0",
        "minNotional": "5.0",
        "basePrecision": 1,
        "quotePrecision": 3,
    },
    "XRPUSDT": {
        "tickSize": "0.0001",
        "qtyStep": "0.1",
        "minOrderQty": "0.1",
        "maxOrderQty": "100000.0",
        "minNotional": "5.0",
        "basePrecision": 1,
        "quotePrecision": 4,
    },
}


class InstrumentsManager:

    """

    Управление кэшем информации об инструментах Bybit.


    Получает параметры округления (tickSize, qtyStep) и минималы (minOrderQty, minNotional)

    один раз при инициализации, затем использует кэш.

    """

    def __init__(self, rest_client, category: str = "linear"):
        """

        Args:

            rest_client: BybitRestClient instance

            category: Категория инструментов (linear, inverse, spot)

        """

        self.client = rest_client

        self.category = category

        self.instruments_cache: Dict[str, Dict[str, Any]] = {}

        self._cache_time = 0

        self._cache_ttl = 3600  # 1 час

    def _get_all_instruments(self) -> Dict[str, Dict[str, Any]]:
        """

        Получить информацию о всех инструментах из Bybit API.


        Returns:

            Dict с информацией об инструментах по символу

        """

        try:

            response = self.client.get(

                "/v5/market/instruments-info",

                params={

                    "category": self.category,

                    "limit": 1000,  # Максимум за один запрос

                },

                signed=False,

            )

            if response.get("retCode") != 0:

                error_msg = response.get('retMsg', '')
                logger.error(f"Failed to get instruments: {error_msg}")
                
                # Fallback: используем дефолтные значения для популярных символов
                if "Illegal category" in error_msg or response.get("retCode") == 10001:
                    logger.warning("instruments-info failed (likely testnet issue), using DEFAULT_INSTRUMENT_PARAMS fallback")
                    instruments = {}
                    for symbol, params in DEFAULT_INSTRUMENT_PARAMS.items():
                        instruments[symbol] = {
                            "symbol": symbol,
                            "tickSize": Decimal(params["tickSize"]),
                            "qtyStep": Decimal(params["qtyStep"]),
                            "minOrderQty": Decimal(params["minOrderQty"]),
                            "maxOrderQty": Decimal(params["maxOrderQty"]),
                            "minNotional": Decimal(params["minNotional"]),
                            "basePrecision": params["basePrecision"],
                            "quotePrecision": params["quotePrecision"],
                        }
                        logger.info(f"Using fallback params for {symbol}")
                    return instruments
                
                return {}

            instruments = {}

            for instrument in response.get("result", {}).get("list", []):

                symbol = instrument.get("symbol", "")

                if not symbol:

                    continue

                # Получаем фильтры напрямую из API response
                price_filter = instrument.get("priceFilter", {})
                lot_size_filter = instrument.get("lotSizeFilter", {})

                # Используем значения напрямую из фильтров (не scale!)
                tick_size = price_filter.get("tickSize", "0.01")
                qty_step = lot_size_filter.get("qtyStep", "0.001")
                min_order_qty = lot_size_filter.get("minOrderQty", "0")
                max_order_qty = lot_size_filter.get("maxOrderQty", "0")
                min_notional = lot_size_filter.get("minNotionalValue", "0")

                instruments[symbol] = {

                    "symbol": symbol,

                    "tickSize": Decimal(tick_size),

                    "qtyStep": Decimal(qty_step),

                    "minOrderQty": Decimal(min_order_qty),

                    "maxOrderQty": Decimal(max_order_qty),

                    "minNotional": Decimal(min_notional),

                    "basePrecision": len(qty_step.split('.')[-1]) if '.' in qty_step else 0,

                    "quotePrecision": len(tick_size.split('.')[-1]) if '.' in tick_size else 0,

                }

                logger.debug(

                    f"Loaded instrument {symbol}: "

                    f"tickSize={instruments[symbol]['tickSize']}, "

                    f"qtyStep={instruments[symbol]['qtyStep']}, "

                    f"minOrderQty={instruments[symbol]['minOrderQty']}, "

                    f"minNotional={instruments[symbol]['minNotional']}"

                )

            return instruments

        except Exception as e:

            logger.error(f"Error fetching instruments: {e}")

            return {}

    def _scale_to_decimal(self, scale: int) -> Decimal:
        """

        Конвертирует scale в Decimal.


        Args:

            scale: Количество знаков после запятой


        Returns:

            Decimal с шагом округления

        """

        if scale <= 0:

            return Decimal("1")

        return Decimal(10) ** (-scale)

    def load_instruments(self, force_refresh: bool = False) -> bool:
        """

        Загрузить информацию об инструментах в кэш.


        Args:

            force_refresh: Выполнить обновление даже если кэш свежий


        Returns:

            True если успешно, False если ошибка

        """

        current_time = time.time()

        # Проверяем TTL кэша

        if (

            not force_refresh

            and self.instruments_cache

            and (current_time - self._cache_time) < self._cache_ttl

        ):

            logger.debug(f"Using cached instruments ({len(self.instruments_cache)} symbols)")

            return True

        logger.info(f"Loading instruments for category={self.category}")

        instruments = self._get_all_instruments()

        if not instruments:

            logger.warning("No instruments loaded")

            return False

        self.instruments_cache = instruments

        self._cache_time = current_time

        logger.info(f"Loaded {len(instruments)} instruments into cache")

        return True

    def get_instrument(self, symbol: str) -> Optional[Dict[str, Any]]:
        """

        Получить информацию об инструменте из кэша.


        Args:

            symbol: Торговая пара (BTCUSDT, ETHUSDT и т.д.)


        Returns:

            Dict с информацией или None если не найдено

        """

        if not self.instruments_cache:

            logger.warning("Instruments cache is empty, try calling load_instruments()")

            return None

        instrument = self.instruments_cache.get(symbol)

        if not instrument:

            logger.warning(f"Instrument {symbol} not found in cache")

            return None

        return instrument

    def normalize_price(self, symbol: str, price: float) -> Optional[Decimal]:
        """

        Округлить цену согласно tickSize инструмента.


        Args:

            symbol: Торговая пара

            price: Цена для округления


        Returns:

            Округленная цена в виде Decimal или None если инструмент не найден

        """

        instrument = self.get_instrument(symbol)

        if not instrument:

            return None

        price_decimal = Decimal(str(price))

        tick_size = instrument["tickSize"]

        # Округляем к ближайшему кратному tickSize

        normalized = (price_decimal / tick_size).quantize(

            Decimal("1"), rounding=ROUND_HALF_UP

        ) * tick_size

        return normalized

    def normalize_qty(self, symbol: str, qty: float) -> Optional[Decimal]:
        """

        Округлить количество согласно qtyStep инструмента.


        Args:

            symbol: Торговая пара

            qty: Количество для округления


        Returns:

            Округленное количество в виде Decimal или None если инструмент не найден

        """

        instrument = self.get_instrument(symbol)

        if not instrument:

            return None

        qty_decimal = Decimal(str(qty))

        qty_step = instrument["qtyStep"]

        # Округляем вниз (ROUND_DOWN) чтобы не превысить доступное количество

        normalized = (qty_decimal / qty_step).quantize(Decimal("1"), rounding=ROUND_DOWN) * qty_step

        return normalized

    def validate_order(self, symbol: str, price: float, qty: float) -> tuple[bool, str]:
        """

        Проверить ордер согласно требованиям биржи.


        Args:

            symbol: Торговая пара

            price: Цена ордера

            qty: Количество


        Returns:

            (is_valid, error_message)

        """

        instrument = self.get_instrument(symbol)

        if not instrument:

            return False, f"Instrument {symbol} not found"

        qty_decimal = Decimal(str(qty))

        price_decimal = Decimal(str(price))

        # Проверяем минимальное количество

        min_order_qty = instrument["minOrderQty"]

        if qty_decimal < min_order_qty:

            return (

                False,

                f"Qty {qty} < minOrderQty {min_order_qty} for {symbol}",

            )

        # Проверяем минимальный notional (qty * price)

        notional = qty_decimal * price_decimal

        min_notional = instrument["minNotional"]

        if notional < min_notional:

            return (

                False,

                f"Notional {notional} < minNotional {min_notional} for {symbol}",

            )

        # Проверяем максимальное количество

        max_order_qty = instrument["maxOrderQty"]

        if max_order_qty > 0 and qty_decimal > max_order_qty:

            return (

                False,

                f"Qty {qty} > maxOrderQty {max_order_qty} for {symbol}",

            )

        return True, ""

    def normalize_order(

        self, symbol: str, price: float, qty: float

    ) -> tuple[Optional[Decimal], Optional[Decimal], str]:
        """

        Нормализовать и валидировать ордер.


        Этап 1: Округление price по tickSize и qty по qtyStep

        Этап 2: Валидация против минималов


        Args:

            symbol: Торговая пара

            price: Цена ордера

            qty: Количество


        Returns:

            (normalized_price, normalized_qty, error_message)

            Если error_message не пусто - ордер невалидный

        """

        # Нормализуем цену и количество

        normalized_price = self.normalize_price(symbol, price)

        if normalized_price is None:

            return None, None, f"Cannot normalize price for {symbol}"

        normalized_qty = self.normalize_qty(symbol, qty)

        if normalized_qty is None:

            return None, None, f"Cannot normalize qty for {symbol}"

        # Валидируем нормализованные значения

        is_valid, error_msg = self.validate_order(

            symbol, float(normalized_price), float(normalized_qty)

        )

        if not is_valid:

            return normalized_price, normalized_qty, error_msg

        return normalized_price, normalized_qty, ""


def normalize_order(

    instruments_manager: InstrumentsManager,

    symbol: str,

    price: float,

    qty: float,

) -> tuple[Optional[Decimal], Optional[Decimal], bool, str]:
    """

    Нормализовать ордер для отправки на биржу.


    Заготовка для использования в bot/trading_bot.py


    Args:

        instruments_manager: InstrumentsManager instance

        symbol: Торговая пара

        price: Цена ордера

        qty: Количество


    Returns:

        (normalized_price, normalized_qty, is_valid, message)

    """

    normalized_price, normalized_qty, error_msg = instruments_manager.normalize_order(

        symbol, price, qty

    )

    if error_msg:

        return normalized_price, normalized_qty, False, error_msg

    return normalized_price, normalized_qty, True, "Order validated"
