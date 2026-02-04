"""
Public streams для Bybit V5: kline и orderbook.

Документация:
- Kline: https://bybit-exchange.github.io/docs/v5/ws/public/kline
- Orderbook: https://bybit-exchange.github.io/docs/v5/ws/public/orderbook
"""

import time
from typing import Optional, Callable, Dict, Any
from collections import OrderedDict
from exchange.websocket_client import BybitWebSocketClient
from config import Config
from logger import setup_logger

logger = setup_logger(__name__)


class KlineStream:
    """
    Подписка на kline (свечи) через WebSocket.
    """

    def __init__(
        self,
        symbol: str,
        interval: str,
        on_kline: Callable[[Dict[Any, Any]], None],
        testnet: bool = True,
    ):
        """
        Args:
            symbol: Символ (например BTCUSDT)
            interval: Интервал (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            on_kline: Callback для обработки свечи
            testnet: Использовать testnet
        """
        self.symbol = symbol
        self.interval = interval
        self.on_kline = on_kline

        ws_url = Config.BYBIT_WS_PUBLIC_TESTNET if testnet else Config.BYBIT_WS_PUBLIC_MAINNET

        self.client = BybitWebSocketClient(ws_url, self._handle_message)
        logger.info(f"KlineStream initialized: {symbol} {interval}")

    def _handle_message(self, data: Dict[Any, Any]):
        """Обработка входящих сообщений"""
        topic = data.get("topic", "")

        # Подтверждение подписки
        if data.get("op") == "subscribe":
            if data.get("success"):
                logger.info(f"Successfully subscribed to {topic}")
            else:
                logger.error(f"Failed to subscribe: {data}")
            return

        # Данные kline
        if topic.startswith("kline"):
            kline_data = data.get("data", [])
            for kline in kline_data:
                self.on_kline(kline)

    def start(self):
        """Запуск stream"""
        self.client.start()
        time.sleep(1)  # Даём время на подключение

        # Подписка: kline.{interval}.{symbol}
        topic = f"kline.{self.interval}.{self.symbol}"
        self.client.subscribe([topic])

    def stop(self):
        """Остановка stream"""
        self.client.stop()


class OrderbookStream:
    """
    Подписка на orderbook через WebSocket с корректной сборкой snapshot/delta.

    Bybit отправляет:
    1. Snapshot (type='snapshot') - полный стакан
    2. Delta (type='delta') - изменения

    Документация: https://bybit-exchange.github.io/docs/v5/ws/public/orderbook
    """

    def __init__(
        self,
        symbol: str,
        depth: int,
        on_orderbook: Callable[[Dict[str, Any]], None],
        testnet: bool = True,
    ):
        """
        Args:
            symbol: Символ (например BTCUSDT)
            depth: Глубина стакана (1, 50, 200, 500)
            on_orderbook: Callback для обработки обновлённого стакана
            testnet: Использовать testnet
        """
        # Валидация допустимых значений depth
        valid_depths = [1, 50, 200, 500]
        if depth not in valid_depths:
            raise ValueError(f"Orderbook depth must be one of {valid_depths}, got {depth}")

        self.symbol = symbol
        self.depth = depth
        self.on_orderbook = on_orderbook

        # Локальный стакан
        self.bids: OrderedDict = OrderedDict()  # {price: qty}
        self.asks: OrderedDict = OrderedDict()  # {price: qty}
        self.last_update_id = 0
        self.snapshot_received = False

        ws_url = Config.BYBIT_WS_PUBLIC_TESTNET if testnet else Config.BYBIT_WS_PUBLIC_MAINNET

        self.client = BybitWebSocketClient(ws_url, self._handle_message)
        logger.info(f"OrderbookStream initialized: {symbol} depth={depth}")

    def _handle_message(self, data: Dict[Any, Any]):
        """Обработка входящих сообщений"""
        topic = data.get("topic", "")

        # Подтверждение подписки
        if data.get("op") == "subscribe":
            if data.get("success"):
                logger.info(f"Successfully subscribed to {topic}")
            else:
                logger.error(f"Failed to subscribe: {data}")
            return

        # Данные orderbook
        if topic.startswith("orderbook"):
            ob_data = data.get("data", {})
            msg_type = data.get("type", "")

            if msg_type == "snapshot":
                self._apply_snapshot(ob_data)
            elif msg_type == "delta":
                self._apply_delta(ob_data)

    def _apply_snapshot(self, data: Dict[str, Any]):
        """Применить snapshot (полный стакан)"""
        self.bids.clear()
        self.asks.clear()

        # Bids: [[price, qty], ...]
        for bid in data.get("b", []):
            price, qty = bid[0], bid[1]
            self.bids[price] = qty

        # Asks: [[price, qty], ...]
        for ask in data.get("a", []):
            price, qty = ask[0], ask[1]
            self.asks[price] = qty

        self.last_update_id = data.get("u", 0)
        self.snapshot_received = True

        logger.debug(f"Orderbook snapshot applied: {len(self.bids)} bids, {len(self.asks)} asks")
        self._notify_orderbook()

    def _apply_delta(self, data: Dict[str, Any]):
        """Применить delta (изменения)"""
        if not self.snapshot_received:
            logger.warning("Delta received before snapshot, ignoring")
            return

        # Обновляем bids
        for bid in data.get("b", []):
            price, qty = bid[0], bid[1]
            if float(qty) == 0:
                # Удаляем уровень
                self.bids.pop(price, None)
            else:
                self.bids[price] = qty

        # Обновляем asks
        for ask in data.get("a", []):
            price, qty = ask[0], ask[1]
            if float(qty) == 0:
                # Удаляем уровень
                self.asks.pop(price, None)
            else:
                self.asks[price] = qty

        self.last_update_id = data.get("u", self.last_update_id)

        logger.debug(f"Orderbook delta applied: {len(self.bids)} bids, {len(self.asks)} asks")
        self._notify_orderbook()

    def _notify_orderbook(self):
        """Отправить обновлённый стакан в callback"""
        # Сортируем и берём топ уровней
        sorted_bids = sorted(self.bids.items(), key=lambda x: float(x[0]), reverse=True)[
            : self.depth
        ]
        sorted_asks = sorted(self.asks.items(), key=lambda x: float(x[0]))[: self.depth]

        orderbook = {
            "symbol": self.symbol,
            "bids": [[price, qty] for price, qty in sorted_bids],
            "asks": [[price, qty] for price, qty in sorted_asks],
            "update_id": self.last_update_id,
            "timestamp": time.time(),
        }

        self.on_orderbook(orderbook)

    def start(self):
        """Запуск stream"""
        self.client.start()
        time.sleep(1)

        # Подписка: orderbook.{depth}.{symbol}
        topic = f"orderbook.{self.depth}.{self.symbol}"
        self.client.subscribe([topic])

    def stop(self):
        """Остановка stream"""
        self.client.stop()

    def get_spread(self) -> Optional[float]:
        """Получить текущий спред"""
        if not self.bids or not self.asks:
            return None

        best_bid = max(self.bids.keys(), key=lambda x: float(x))
        best_ask = min(self.asks.keys(), key=lambda x: float(x))

        return float(best_ask) - float(best_bid)


class MarkPriceStream:
    """
    Подписка на mark price через WebSocket (деривативы).
    """

    def __init__(
        self,
        symbol: str,
        on_mark_price: Callable[[Dict[Any, Any]], None],
        testnet: bool = True,
    ):
        """
        Args:
            symbol: Символ
            on_mark_price: Callback для обработки mark price
            testnet: Использовать testnet
        """
        self.symbol = symbol
        self.on_mark_price = on_mark_price

        ws_url = Config.BYBIT_WS_PUBLIC_TESTNET if testnet else Config.BYBIT_WS_PUBLIC_MAINNET

        self.client = BybitWebSocketClient(ws_url, self._handle_message)
        logger.info(f"MarkPriceStream initialized: {symbol}")

    def _handle_message(self, data: Dict[Any, Any]):
        """Обработка входящих сообщений"""
        topic = data.get("topic", "")

        if not topic.startswith("markPrice"):
            return

        data_list = data.get("data", {})
        if isinstance(data_list, dict):
            self.on_mark_price(data_list)

    def start(self):
        """Запуск stream"""
        self.client.start()
        time.sleep(1)

        topic = f"markPrice.{self.symbol}"
        self.client.subscribe([topic])

    def stop(self):
        """Остановка stream"""
        self.client.stop()


class FundingRateStream:
    """
    Подписка на funding rate через WebSocket.
    """

    def __init__(
        self,
        symbol: str,
        on_funding: Callable[[Dict[Any, Any]], None],
        testnet: bool = True,
    ):
        """
        Args:
            symbol: Символ
            on_funding: Callback для обработки funding rate
            testnet: Использовать testnet
        """
        self.symbol = symbol
        self.on_funding = on_funding

        ws_url = Config.BYBIT_WS_PUBLIC_TESTNET if testnet else Config.BYBIT_WS_PUBLIC_MAINNET

        self.client = BybitWebSocketClient(ws_url, self._handle_message)
        logger.info(f"FundingRateStream initialized: {symbol}")

    def _handle_message(self, data: Dict[Any, Any]):
        """Обработка входящих сообщений"""
        topic = data.get("topic", "")

        if not topic.startswith("funding"):
            return

        data_list = data.get("data", {})
        if isinstance(data_list, dict):
            self.on_funding(data_list)

    def start(self):
        """Запуск stream"""
        self.client.start()
        time.sleep(1)

        topic = f"funding.{self.symbol}"
        self.client.subscribe([topic])

    def stop(self):
        """Остановка stream"""
        self.client.stop()
