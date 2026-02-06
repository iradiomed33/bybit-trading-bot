"""

Account и Position API эндпоинты для Bybit V5.


Документация:

- Position: https://bybit-exchange.github.io/docs/v5/position

- Order: https://bybit-exchange.github.io/docs/v5/order/open-order

"""


from typing import Dict, Any, Optional

from exchange.base_client import BybitRestClient

from logger import setup_logger


logger = setup_logger(__name__)


class AccountClient:

    """Клиент для работы с аккаунтом, позициями и ордерами"""

    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = True):

        self.client = BybitRestClient(api_key, api_secret, testnet)

        logger.info("AccountClient initialized")

    def get_positions(

        self, category: str = "linear", symbol: Optional[str] = None

    ) -> Dict[str, Any]:
        """

        Получить список позиций.


        Args:

            category: Категория (linear, inverse, option)

            symbol: Конкретный символ (опционально для linear категории)


        Returns:

            Полный ответ API со списком позиций


        Docs: https://bybit-exchange.github.io/docs/v5/position/position-info

        """

        params = {"category": category}

        if symbol:

            params["symbol"] = symbol

        else:

            # Для linear категории, если символ не указан, используем settleCoin

            # это позволяет получить все позиции в USDT

            if category == "linear":

                params["settleCoin"] = "USDT"

        logger.debug(f"Fetching positions: category={category}, symbol={symbol}")

        response = self.client.get("/v5/position/list", params=params, signed=True)

        return response

    def get_open_orders(

        self, category: str = "linear", symbol: Optional[str] = None

    ) -> Dict[str, Any]:
        """

        Получить список открытых ордеров.


        Args:

            category: Категория (linear, inverse, spot, option)

            symbol: Конкретный символ (опционально для linear требуется указывать)


        Returns:

            Полный ответ API со списком ордеров


        Docs: https://bybit-exchange.github.io/docs/v5/order/open-order

        """

        params = {"category": category}

        if symbol:

            params["symbol"] = symbol

        else:

            # Для linear и inverse категорий, если символ не указан, используем settleCoin

            if category in ["linear", "inverse"]:

                params["settleCoin"] = "USDT"

            elif category == "spot":

                params["baseCoin"] = "BTC"

        logger.debug(f"Fetching open orders: category={category}, symbol={symbol}")

        response = self.client.get("/v5/order/realtime", params=params, signed=True)

        return response

    def get_executions(

        self, category: str = "linear", symbol: Optional[str] = None, limit: int = 50

    ) -> Dict[str, Any]:
        """

        Получить историю исполнений (trades).


        Args:

            category: Категория

            symbol: Символ (опционально)

            limit: Количество записей (макс 100)


        Returns:

            Полный ответ API с историей исполнений


        Docs: https://bybit-exchange.github.io/docs/v5/position/execution

        """

        params = {"category": category, "limit": limit}

        if symbol:

            params["symbol"] = symbol

        logger.debug(f"Fetching executions: symbol={symbol}, limit={limit}")

        response = self.client.get("/v5/execution/list", params=params, signed=True)

        return response

    def set_leverage(

        self, category: str, symbol: str, buy_leverage: str, sell_leverage: str

    ) -> Dict[str, Any]:
        """

        Установить кредитное плечо для позиции.


        Args:

            category: Категория (linear, inverse)

            symbol: Символ

            buy_leverage: Плечо для Buy позиций (строка, например "10")

            sell_leverage: Плечо для Sell позиций (строка)


        Returns:

            Ответ API


        Docs: https://bybit-exchange.github.io/docs/v5/position/leverage

        """

        params = {

            "category": category,

            "symbol": symbol,

            "buyLeverage": buy_leverage,

            "sellLeverage": sell_leverage,

        }

        logger.info(f"Setting leverage: {symbol} buy={buy_leverage} sell={sell_leverage}")

        response = self.client.post("/v5/position/set-leverage", params=params)

        return response

    def get_wallet_balance(self, coin: str = "USDT") -> Dict[str, Any]:
        """

        Получить баланс кошелька (wallet balance).


        Args:

            coin: Валюта (по умолчанию USDT)


        Returns:

            Dict с информацией о балансе (содержит 'balance' ключ с float значением)


        Docs: https://bybit-exchange.github.io/docs/v5/account/wallet-balance

        """

        params = {"accountType": "UNIFIED"}

        logger.debug(f"Fetching wallet balance for {coin}")

        response = self.client.get("/v5/account/wallet-balance", params=params, signed=True)

        try:

            # Структура: response['result']['list'][0]['coin'][0]

            if response.get("retCode") == 0:

                accounts = response.get("result", {}).get("list", [])

                for account in accounts:

                    coins = account.get("coin", [])

                    for coin_info in coins:

                        if coin_info.get("coin") == coin:

                            balance = float(coin_info.get("walletBalance", 0))

                            logger.debug(f"Wallet balance: {balance} {coin}")

                            return {"balance": balance, "coin": coin, "retCode": 0}

                # Если монета не найдена, возвращаем 0

                logger.warning(f"Coin {coin} not found in wallet balance")

                return {"balance": 0.0, "coin": coin, "retCode": 0}

            else:

                logger.error(f"Failed to get wallet balance: {response}")

                return {"balance": 0.0, "coin": coin, "retCode": response.get("retCode", -1)}

        except Exception as e:

            logger.error(f"Error parsing wallet balance: {e}")

            return {"balance": 0.0, "coin": coin, "retCode": -1}
