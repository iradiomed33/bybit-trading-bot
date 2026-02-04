"""
Private WebSocket для Bybit V5: ордера и позиции.

Документация:
- Authentication: https://bybit-exchange.github.io/docs/v5/ws/connect#authentication
- Order stream: https://bybit-exchange.github.io/docs/v5/ws/private/order
- Position stream: https://bybit-exchange.github.io/docs/v5/ws/private/position
"""

import time
import hmac
import hashlib
from typing import Callable, Dict, Any
from exchange.websocket_client import BybitWebSocketClient
from logger import setup_logger

logger = setup_logger(__name__)


class PrivateWebSocket:
    """
    Private WebSocket для получения обновлений ордеров и позиций.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        on_order: Callable[[Dict[Any, Any]], None],
        on_position: Callable[[Dict[Any, Any]], None],
        testnet: bool = True,
    ):
        """
        Args:
            api_key: API ключ
            api_secret: API secret
            on_order: Callback для обновлений ордеров
            on_position: Callback для обновлений позиций
            testnet: Использовать testnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.on_order = on_order
        self.on_position = on_position

        # Private WS URL
        ws_url = (
            "wss://stream-testnet.bybit.com/v5/private"
            if testnet
            else "wss://stream.bybit.com/v5/private"
        )

        self.client = BybitWebSocketClient(ws_url, self._handle_message)
        self.authenticated = False

        logger.info(f"PrivateWebSocket initialized: {ws_url}")

    def _generate_auth_signature(self, expires: int) -> str:
        """
        Генерация подписи для аутентификации.

        Args:
            expires: Timestamp в миллисекундах

        Returns:
            Hex подпись

        Docs: https://bybit-exchange.github.io/docs/v5/ws/connect#authentication
        """
        # V5: GET /realtime + expires
        param_str = f"GET/realtime{expires}"

        signature = hmac.new(
            self.api_secret.encode("utf-8"), param_str.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return signature

    def _authenticate(self):
        """Аутентификация на private WS"""
        expires = int((time.time() + 10) * 1000)  # +10 сек
        signature = self._generate_auth_signature(expires)

        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature],
        }

        try:
            self.client.ws.send(self.client.ws._app.send(auth_msg))
            logger.info("Authentication request sent")
        except Exception as e:
            logger.error(f"Failed to send auth request: {e}")

    def _handle_message(self, data: Dict[Any, Any]):
        """Обработка входящих сообщений"""
        # Ответ на аутентификацию
        if data.get("op") == "auth":
            if data.get("success"):
                self.authenticated = True
                logger.info("✓ Private WebSocket authenticated")
                # Подписываемся на топики после аутентификации
                self._subscribe_to_topics()
            else:
                logger.error(f"Authentication failed: {data}")
            return

        # Подтверждение подписки
        if data.get("op") == "subscribe":
            if data.get("success"):
                logger.info(f"Successfully subscribed to {data.get('topic', 'unknown')}")
            else:
                logger.error(f"Subscription failed: {data}")
            return

        # Данные ордеров
        topic = data.get("topic", "")
        if topic == "order":
            for order_data in data.get("data", []):
                self.on_order(order_data)

        # Данные позиций
        if topic == "position":
            for position_data in data.get("data", []):
                self.on_position(position_data)

    def _subscribe_to_topics(self):
        """Подписка на приватные топики после аутентификации"""
        topics = ["order", "position"]
        self.client.subscribe(topics)

    def start(self):
        """Запуск private WS"""
        self.client.start()
        time.sleep(1)  # Даём время на подключение
        self._authenticate()

    def stop(self):
        """Остановка private WS"""
        self.client.stop()
