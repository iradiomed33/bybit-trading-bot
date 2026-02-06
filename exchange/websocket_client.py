"""

Базовый WebSocket клиент для Bybit V5 с авто-реконнектом.


Документация:

- Public WebSocket: https://bybit-exchange.github.io/docs/v5/ws/connect

- Heartbeat: https://bybit-exchange.github.io/docs/v5/ws/connect#how-to-send-heartbeat-packet

"""


import json

import time

import threading

from typing import Callable, Optional, Dict, Any

import websocket

from logger import setup_logger


logger = setup_logger(__name__)


class BybitWebSocketClient:

    """

    Базовый WebSocket клиент с реконнектом и ping/pong.

    """

    def __init__(
        self, 
        ws_url: str, 
        on_message: Callable[[Dict[Any, Any]], None],
        on_reconnect: Optional[Callable[[], None]] = None,
    ):
        """

        Args:

            ws_url: WebSocket URL (public или private)

            on_message: Callback функция для обработки сообщений

            on_reconnect: Callback функция при переподключении (для re-auth)

        """

        self.ws_url = ws_url

        self.on_message_callback = on_message

        self.on_reconnect_callback = on_reconnect

        self.ws: Optional[websocket.WebSocketApp] = None

        self.ws_thread: Optional[threading.Thread] = None

        self.is_running = False

        self.reconnect_count = 0

        self.max_reconnect_delay = 60  # Максимальная задержка реконнекта (сек)

        # Ping/Pong для keep-alive

        self.last_ping_time = 0

        self.ping_interval = 20  # Bybit рекомендует каждые 20 сек

        logger.info(f"WebSocket client initialized: {ws_url}")

    def _on_open(self, ws):
        """Callback при открытии соединения"""

        logger.info("WebSocket connection opened")

        self.reconnect_count = 0

        self.last_ping_time = time.time()

        # Вызываем callback при переподключении (для re-auth)
        if self.on_reconnect_callback:
            try:
                self.on_reconnect_callback()
            except Exception as e:
                logger.error(f"Error in on_reconnect callback: {e}", exc_info=True)

    def _on_message(self, ws, message):
        """Callback при получении сообщения"""

        try:

            data = json.loads(message)

            # Обработка pong от сервера

            if data.get("op") == "pong":

                logger.debug("Received pong from server")

                return

            # Передаём данные в пользовательский callback

            self.on_message_callback(data)

        except json.JSONDecodeError as e:

            logger.error(f"Failed to decode WebSocket message: {e}")

        except Exception as e:

            logger.error(f"Error in on_message callback: {e}", exc_info=True)

    def _on_error(self, ws, error):
        """Callback при ошибке"""

        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Callback при закрытии соединения"""

        logger.warning(f"WebSocket connection closed: code={close_status_code}, msg={close_msg}")

        if self.is_running:

            self._reconnect()

    def _reconnect(self):
        """Переподключение с exponential backof"""

        self.reconnect_count += 1

        delay = min(2**self.reconnect_count, self.max_reconnect_delay)

        logger.info(f"Reconnecting in {delay} seconds (attempt {self.reconnect_count})...")

        time.sleep(delay)

        if self.is_running:

            self.start()

    def _send_ping(self):
        """Отправка ping для keep-alive"""

        if self.ws and self.is_running and self.ws.sock and self.ws.sock.connected:

            current_time = time.time()

            if current_time - self.last_ping_time >= self.ping_interval:

                try:

                    ping_msg = json.dumps({"op": "ping"})

                    self.ws.send(ping_msg)

                    logger.debug("Sent ping to server")

                    self.last_ping_time = current_time

                except Exception as e:

                    logger.error(f"Failed to send ping: {e}")

    def _run_ping_thread(self):
        """Фоновый поток для отправки ping"""

        while self.is_running:

            self._send_ping()

            time.sleep(5)  # Проверяем каждые 5 секунд

    def subscribe(self, topics: list):
        """

        Подписка на топики.


        Args:

            topics: Список топиков (например ["kline.1.BTCUSDT", "orderbook.50.BTCUSDT"])


        Docs: https://bybit-exchange.github.io/docs/v5/ws/connect#how-to-subscribe-to-topics

        """

        if not self.ws:

            logger.error("WebSocket not connected, cannot subscribe")

            return

        subscribe_msg = {"op": "subscribe", "args": topics}

        try:

            self.ws.send(json.dumps(subscribe_msg))

            logger.info(f"Subscribed to topics: {topics}")

        except Exception as e:

            logger.error(f"Failed to subscribe: {e}")

    def start(self):
        """Запуск WebSocket соединения"""

        if self.is_running and self.ws_thread and self.ws_thread.is_alive():

            logger.warning("WebSocket already running")

            return

        self.is_running = True

        self.ws = websocket.WebSocketApp(

            self.ws_url,

            on_open=self._on_open,

            on_message=self._on_message,

            on_error=self._on_error,

            on_close=self._on_close,

        )

        # Запускаем WebSocket в отдельном потоке

        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)

        self.ws_thread.start()

        # Запускаем ping поток

        ping_thread = threading.Thread(target=self._run_ping_thread, daemon=True)

        ping_thread.start()

        logger.info("WebSocket client started")

    def stop(self):
        """Остановка WebSocket соединения"""

        logger.info("Stopping WebSocket client...")

        self.is_running = False

        if self.ws:

            self.ws.close()

        if self.ws_thread:

            self.ws_thread.join(timeout=5)

        logger.info("WebSocket client stopped")
