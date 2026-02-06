"""

Публичные market data эндпоинты Bybit V5.


Документация:

- Kline: https://bybit-exchange.github.io/docs/v5/market/kline

- Orderbook: https://bybit-exchange.github.io/docs/v5/market/orderbook

- Instruments: https://bybit-exchange.github.io/docs/v5/market/instrument

"""


from typing import Optional, Dict, Any

from exchange.base_client import BybitRestClient

from logger import setup_logger


logger = setup_logger(__name__)


class MarketDataClient:

    """Клиент для получения рыночных данных (публичные эндпоинты)"""

    def __init__(self, testnet: bool = True):

        self.client = BybitRestClient(testnet=testnet)

        logger.info("MarketDataClient initialized")

    def get_instruments_info(

        self, category: str = "linear", symbol: Optional[str] = None

    ) -> Dict[str, Any]:
        """

        Получить информацию об инструментах (tick size, qty step, min/max).


        Args:

            category: Категория продукта (linear, inverse, spot, option)

            symbol: Конкретный символ (опционально)


        Returns:

            Полный ответ API с информацией об инструментах


        Docs: https://bybit-exchange.github.io/docs/v5/market/instrument

        """

        params = {"category": category}

        if symbol:

            params["symbol"] = symbol

        logger.debug(f"Fetching instruments info: category={category}, symbol={symbol}")

        response = self.client.get("/v5/market/instruments-info", params=params)

        return response

    def get_kline(

        self,

        symbol: str,

        interval: str = "1",

        category: str = "linear",

        limit: int = 200,

        start: Optional[int] = None,

        end: Optional[int] = None,

    ) -> Dict[str, Any]:
        """

        Получить исторические свечи (kline/candlestick).


        Args:

            symbol: Символ (например BTCUSDT)

            interval: Интервал свечи (1,3,5,15,30,60,120,240,360,720,D,W,M)

            category: Категория (linear, inverse, spot)

            limit: Количество свечей (макс 1000)

            start: Начальная временная метка (мс)

            end: Конечная временная метка (мс)


        Returns:

            Полный ответ API со свечами


        Docs: https://bybit-exchange.github.io/docs/v5/market/kline

        """

        params = {"category": category, "symbol": symbol, "interval": interval, "limit": limit}

        if start:

            params["start"] = start

        if end:

            params["end"] = end

        logger.debug(f"Fetching kline: {symbol} {interval} (limit={limit})")

        response = self.client.get("/v5/market/kline", params=params)

        return response

    def get_orderbook(

        self, symbol: str, category: str = "linear", limit: int = 25

    ) -> Dict[str, Any]:
        """

        Получить snapshot стакана (orderbook).


        Args:

            symbol: Символ (например BTCUSDT)

            category: Категория (linear, inverse, spot, option)

            limit: Глубина стакана (1, 25, 50, 100, 200, 500)


        Returns:

            Полный ответ API со стаканом


        Docs: https://bybit-exchange.github.io/docs/v5/market/orderbook

        """

        params = {"category": category, "symbol": symbol, "limit": limit}

        logger.debug(f"Fetching orderbook: {symbol} (limit={limit})")

        response = self.client.get("/v5/market/orderbook", params=params)

        return response

    def get_server_time(self) -> Dict[str, Any]:
        """

        Получить время сервера Bybit.


        Returns:

            Время сервера в миллисекундах


        Docs: https://bybit-exchange.github.io/docs/v5/market/time

        """

        logger.debug("Fetching server time")

        response = self.client.get("/v5/market/time")

        return response

    def get_mark_price_kline(

        self,

        symbol: str,

        interval: str = "1",

        category: str = "linear",

        limit: int = 200,

        start: Optional[int] = None,

        end: Optional[int] = None,

    ) -> Dict[str, Any]:
        """

        Получить mark price свечи (деривативные инструменты).


        Args:

            symbol: Символ (например BTCUSDT)

            interval: Интервал (1,3,5,15,30,60,120,240,360,720,D,W,M)

            category: Категория (linear, inverse)

            limit: Количество свечей (макс 1000)

            start: Начальная временная метка (мс)

            end: Конечная временная метка (мс)


        Returns:

            Полный ответ API с mark price свечами


        Docs: https://bybit-exchange.github.io/docs/v5/market/mark-kline

        """

        params = {"category": category, "symbol": symbol, "interval": interval, "limit": limit}

        if start:

            params["start"] = start

        if end:

            params["end"] = end

        logger.debug(f"Fetching mark price kline: {symbol} {interval}")

        response = self.client.get("/v5/market/mark-price-kline", params=params)

        return response

    def get_index_price_kline(

        self,

        symbol: str,

        interval: str = "1",

        category: str = "linear",

        limit: int = 200,

        start: Optional[int] = None,

        end: Optional[int] = None,

    ) -> Dict[str, Any]:
        """

        Получить index price свечи.


        Args:

            symbol: Символ (например BTCUSDT)

            interval: Интервал

            category: Категория (linear, inverse)

            limit: Количество свечей

            start: Начальная временная метка

            end: Конечная временная метка


        Returns:

            Полный ответ API с index price свечами


        Docs: https://bybit-exchange.github.io/docs/v5/market/index-kline

        """

        params = {"category": category, "symbol": symbol, "interval": interval, "limit": limit}

        if start:

            params["start"] = start

        if end:

            params["end"] = end

        logger.debug(f"Fetching index price kline: {symbol} {interval}")

        response = self.client.get("/v5/market/index-price-kline", params=params)

        return response

    def get_open_interest(

        self,

        symbol: str,

        interval: str = "5min",

        category: str = "linear",

        limit: int = 200,

        cursor: Optional[str] = None,

    ) -> Dict[str, Any]:
        """

        Получить open interest (количество открытых позиций).


        Args:

            symbol: Символ

            interval: Интервал (5min, 15min, 30min, 1h, 4h, 12h, D, W, M)

            category: Категория (linear, inverse, option)

            limit: Количество записей (макс 500)

            cursor: Курсор для пагинации


        Returns:

            Полный ответ API с open interest


        Docs: https://bybit-exchange.github.io/docs/v5/market/oi

        """

        params = {"category": category, "symbol": symbol, "intervalTime": interval, "limit": limit}

        if cursor:

            params["cursor"] = cursor

        logger.debug(f"Fetching open interest: {symbol} {interval}")

        response = self.client.get("/v5/market/open-interest", params=params)

        return response

    def get_funding_rate_history(

        self,

        symbol: str,

        category: str = "linear",

        limit: int = 200,

        start: Optional[int] = None,

        end: Optional[int] = None,

    ) -> Dict[str, Any]:
        """

        Получить историю funding rate.


        Args:

            symbol: Символ

            category: Категория (linear, inverse)

            limit: Количество записей (макс 200)

            start: Начальная временная метка (мс)

            end: Конечная временная метка (мс)


        Returns:

            Полный ответ API с историей funding rate


        Docs: https://bybit-exchange.github.io/docs/v5/market/fundingrate-history

        """

        params = {"category": category, "symbol": symbol, "limit": limit}

        if start:

            params["startTime"] = start

        if end:

            params["endTime"] = end

        logger.debug(f"Fetching funding rate history: {symbol}")

        response = self.client.get("/v5/market/funding/history", params=params)

        return response
