"""

Private WebSocket для Bybit V5: ордера и позиции.


Документация:

- Authentication: https://bybit-exchange.github.io/docs/v5/ws/connect#authentication

- Order stream: https://bybit-exchange.github.io/docs/v5/ws/private/order

- Position stream: https://bybit-exchange.github.io/docs/v5/ws/private/position

- Execution stream: https://bybit-exchange.github.io/docs/v5/ws/private/execution

"""


import json

import time

import hmac

import hashlib

from typing import Callable, Dict, Any, List, Optional

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

        on_execution: Optional[Callable[[Dict[Any, Any]], None]] = None,

        testnet: bool = True,

    ):
        """

        Args:

            api_key: API ключ

            api_secret: API secret

            on_order: Callback для обновлений ордеров

            on_position: Callback для обновлений позиций

            on_execution: Callback для исполнений (fills)

            testnet: Использовать testnet

        """

        self.api_key = api_key

        self.api_secret = api_secret

        self.on_order = on_order

        self.on_position = on_position

        self.on_execution = on_execution

        # Локальное состояние
        self.orders_state: Dict[str, Dict] = {}  # order_id -> order data
        self.positions_state: Dict[str, Dict] = {}  # symbol -> position data
        self.executions_history: List[Dict] = []  # История fills

        # Private WS URL

        ws_url = (

            "wss://stream-testnet.bybit.com/v5/private"

            if testnet

            else "wss://stream.bybit.com/v5/private"

        )

        self.client = BybitWebSocketClient(
            ws_url, 
            self._handle_message,
            on_reconnect=self._on_reconnect,
        )

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

            # ИСПРАВЛЕНО: правильная отправка через json.dumps
            self.client.ws.send(json.dumps(auth_msg))

            logger.info("Authentication request sent")

        except Exception as e:

            logger.error(f"Failed to send auth request: {e}")

    def _on_reconnect(self):
        """Callback при переподключении - повторная аутентификация"""
        logger.info("Reconnected, re-authenticating...")
        self.authenticated = False
        time.sleep(1)  # Даём время на стабилизацию соединения
        self._authenticate()

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

                logger.info(f"Successfully subscribed to {data.get('args', 'unknown')}")

            else:

                logger.error(f"Subscription failed: {data}")

            return

        # Данные ордеров

        topic = data.get("topic", "")

        if topic == "order":

            for order_data in data.get("data", []):
                # Обновляем локальное состояние
                order_id = order_data.get("orderId")
                if order_id:
                    self.orders_state[order_id] = order_data
                    logger.debug(f"Order update: {order_id} - {order_data.get('orderStatus')}")
                
                # Вызываем callback
                self.on_order(order_data)

        # Данные позиций

        if topic == "position":

            for position_data in data.get("data", []):
                # Обновляем локальное состояние
                symbol = position_data.get("symbol")
                if symbol:
                    self.positions_state[symbol] = position_data
                    logger.debug(f"Position update: {symbol} - size={position_data.get('size')}")
                
                # Вызываем callback
                self.on_position(position_data)

        # Данные исполнений (fills)
        if topic == "execution":
            for execution_data in data.get("data", []):
                # Сохраняем в историю
                self.executions_history.append(execution_data)
                
                # Ограничиваем размер истории (последние 1000)
                if len(self.executions_history) > 1000:
                    self.executions_history = self.executions_history[-1000:]
                
                logger.info(
                    f"Execution: {execution_data.get('symbol')} "
                    f"{execution_data.get('side')} {execution_data.get('execQty')} @ {execution_data.get('execPrice')}"
                )
                
                # Вызываем callback если есть
                if self.on_execution:
                    self.on_execution(execution_data)

    def _subscribe_to_topics(self):
        """Подписка на приватные топики после аутентификации"""

        topics = ["order", "position", "execution"]

        self.client.subscribe(topics)

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Получить статус ордера из локального состояния.
        
        Args:
            order_id: ID ордера
            
        Returns:
            Данные ордера или None если не найден
        """
        return self.orders_state.get(order_id)

    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Получить позицию по символу из локального состояния.
        
        Args:
            symbol: Символ (например "BTCUSDT")
            
        Returns:
            Данные позиции или None если нет позиции
        """
        return self.positions_state.get(symbol)

    def get_executions(self, limit: int = 100) -> List[Dict]:
        """
        Получить историю исполнений (fills).
        
        Args:
            limit: Максимальное количество записей
            
        Returns:
            Список последних исполнений
        """
        return self.executions_history[-limit:]

    def get_all_orders(self) -> Dict[str, Dict]:
        """Получить все ордера из локального состояния"""
        return self.orders_state.copy()

    def get_all_positions(self) -> Dict[str, Dict]:
        """Получить все позиции из локального состояния"""
        return self.positions_state.copy()

    def start(self):
        """Запуск private WS"""

        self.client.start()

        time.sleep(1)  # Даём время на подключение

        self._authenticate()

    def stop(self):
        """Остановка private WS"""

        self.client.stop()
