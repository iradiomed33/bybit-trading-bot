"""

Order Manager: создание, отмена, отслеживание ордеров.


Ключевые фичи:

- Идемпотентность через orderLinkId

- Retry логика

- Синхронизация с БД

"""


import uuid

import time

from typing import Dict, Any, Optional

from exchange.base_client import BybitRestClient

from storage.database import Database

from execution.order_result import OrderResult

from logger import setup_logger


logger = setup_logger(__name__)


class OrderManager:

    """Управление ордерами"""

    def __init__(self, client: BybitRestClient, db: Database):
        """

        Args:

            client: REST клиент

            db: Database instance

        """

        self.client = client

        self.db = db

        logger.info("OrderManager initialized")

    def create_order(

        self,

        category: str,

        symbol: str,

        side: str,

        order_type: str,

        qty: float,

        price: Optional[float] = None,

        time_in_force: str = "GTC",

        stop_loss: Optional[float] = None,

        take_profit: Optional[float] = None,

        order_link_id: Optional[str] = None,

    ) -> OrderResult:
        """

        Создать ордер с идемпотентностью.


        Args:

            category: Категория (linear, inverse, spot, option)

            symbol: Символ

            side: Buy или Sell

            order_type: Limit, Market

            qty: Количество

            price: Цена (для Limit)

            time_in_force: GTC, IOC, FOK, PostOnly

            stop_loss: Stop loss цена

            take_profit: Take profit цена

            order_link_id: Клиентский ID (для идемпотентности)


        Returns:

            OrderResult с информацией о результате создания ордера


        Docs: https://bybit-exchange.github.io/docs/v5/order/create-order

        """

        # Генерируем уникальный orderLinkId если не передан

        if not order_link_id:

            order_link_id = f"order_{uuid.uuid4().hex[:16]}"

        params = {

            "category": category,

            "symbol": symbol,

            "side": side,

            "orderType": order_type,

            "qty": str(qty),

            "orderLinkId": order_link_id,

        }

        # Limit order требует цену

        if order_type == "Limit":

            if not price:

                raise ValueError("Price required for Limit order")

            params["price"] = str(price)

            params["timeInForce"] = time_in_force

        # SL/TP

        if stop_loss:

            params["stopLoss"] = str(stop_loss)

        if take_profit:

            params["takeProfit"] = str(take_profit)

        logger.info(

            f"Creating order: {side} {qty} {symbol} @ {price or 'market'} (link_id={order_link_id})"

        )

        try:

            response = self.client.post("/v5/order/create", params=params)

            # Используем OrderResult.from_api_response для парсинга ответа
            result = OrderResult.from_api_response(response)

            if result.success:

                order_id = result.order_id

                logger.info(f"✓ Order created: {order_id}")

                # Сохраняем в БД

                self.db.save_order(

                    {

                        "order_id": order_id,

                        "order_link_id": order_link_id,

                        "symbol": symbol,

                        "side": side,

                        "order_type": order_type,

                        "price": price,

                        "qty": qty,

                        "filled_qty": 0,

                        "status": "New",

                        "time_in_force": time_in_force,

                        "created_time": time.time() * 1000,

                        "updated_time": time.time() * 1000,

                        "metadata": result.raw.get("result", {}),

                    }

                )

                # Добавляем order_link_id в сырой ответ для обратной совместимости
                result.raw["order_link_id"] = order_link_id

                return result

            else:

                logger.error(f"Order creation failed: {result.error}")

                return result

        except Exception as e:

            logger.error(f"Order creation exception: {e}", exc_info=True)

            self.db.save_error("order_creation", str(e), metadata={"params": params})

            return OrderResult.error_result(str(e))

    def cancel_order(

        self,

        category: str,

        symbol: str,

        order_id: Optional[str] = None,

        order_link_id: Optional[str] = None,

    ) -> OrderResult:
        """

        Отменить ордер.


        Args:

            category: Категория

            symbol: Символ

            order_id: ID ордера (или order_link_id)

            order_link_id: Клиентский ID


        Returns:

            OrderResult с информацией о результате отмены


        Docs: https://bybit-exchange.github.io/docs/v5/order/cancel-order

        """

        if not order_id and not order_link_id:

            raise ValueError("Either order_id or order_link_id required")

        params = {"category": category, "symbol": symbol}

        if order_id:

            params["orderId"] = order_id

        else:

            params["orderLinkId"] = order_link_id

        logger.info(f"Cancelling order: {order_id or order_link_id}")

        try:

            response = self.client.post("/v5/order/cancel", params=params)

            # Используем OrderResult.from_api_response для парсинга ответа
            result = OrderResult.from_api_response(response)

            if result.success:

                logger.info(f"✓ Order cancelled: {order_id or order_link_id}")

                # Обновляем в БД

                if order_id:

                    self.db.save_order(

                        {

                            "order_id": order_id,

                            "symbol": symbol,

                            "side": "Unknown",

                            "order_type": "Unknown",

                            "qty": 0,

                            "status": "Cancelled",

                            "updated_time": time.time() * 1000,

                        }

                    )

                # Сохраняем order_id для обратной совместимости
                if not result.order_id:
                    result.order_id = order_id

                return result

            else:

                logger.error(f"Order cancellation failed: {result.error}")

                return result

        except Exception as e:

            logger.error(f"Order cancellation exception: {e}", exc_info=True)

            return OrderResult.error_result(str(e))

    def cancel_all_orders(self, category: str, symbol: Optional[str] = None) -> OrderResult:
        """

        Отменить все ордера (для kill switch).


        Args:

            category: Категория

            symbol: Символ (опционально, если не указан - отменяются все)


        Returns:

            OrderResult с информацией о результате отмены


        Docs: https://bybit-exchange.github.io/docs/v5/order/cancel-all

        """

        params = {"category": category}

        if symbol:

            params["symbol"] = symbol

        logger.warning(f"Cancelling ALL orders for {symbol or 'all symbols'}")

        try:

            response = self.client.post("/v5/order/cancel-all", params=params)

            # Используем OrderResult.from_api_response для парсинга ответа
            result = OrderResult.from_api_response(response)

            if result.success:

                logger.info(f"✓ All orders cancelled: {result.raw.get('result', {})}")

                return result

            else:

                logger.error(f"Cancel all failed: {result.error}")

                return result

        except Exception as e:

            logger.error(f"Cancel all exception: {e}", exc_info=True)

            return OrderResult.error_result(str(e))

    def set_trading_stop(
        self,
        category: str,
        symbol: str,
        position_idx: int = 0,
        stop_loss: Optional[str] = None,
        take_profit: Optional[str] = None,
        sl_trigger_by: str = "LastPrice",
        tp_trigger_by: str = "LastPrice",
        tpsl_mode: str = "Full",
        sl_size: Optional[str] = None,
        tp_size: Optional[str] = None,
    ) -> OrderResult:
        """
        Установить Stop Loss и Take Profit на позицию через Trading Stop API.

        Args:
            category: Категория (linear, inverse, spot)
            symbol: Символ
            position_idx: 0 для one-way mode, 1 для Buy в hedge mode, 2 для Sell
            stop_loss: Цена Stop Loss
            take_profit: Цена Take Profit
            sl_trigger_by: Триггер для SL ("LastPrice", "IndexPrice", "MarkPrice")
            tp_trigger_by: Триггер для TP ("LastPrice", "IndexPrice", "MarkPrice")
            tpsl_mode: "Full" (вся позиция) или "Partial" (частичная)
            sl_size: Размер для SL (если tpsl_mode="Partial")
            tp_size: Размер для TP (если tpsl_mode="Partial")

        Returns:
            OrderResult с информацией о результате

        Docs: https://bybit-exchange.github.io/docs/v5/position/trading-stop
        """
        params = {
            "category": category,
            "symbol": symbol,
            "positionIdx": position_idx,
        }

        if stop_loss:
            params["stopLoss"] = stop_loss
            params["slTriggerBy"] = sl_trigger_by
            if sl_size and tpsl_mode == "Partial":
                params["slSize"] = sl_size

        if take_profit:
            params["takeProfit"] = take_profit
            params["tpTriggerBy"] = tp_trigger_by
            if tp_size and tpsl_mode == "Partial":
                params["tpSize"] = tp_size

        if tpsl_mode:
            params["tpslMode"] = tpsl_mode

        logger.info(f"Setting trading stop for {symbol}: SL={stop_loss}, TP={take_profit}")

        try:
            response = self.client.post("/v5/position/trading-stop", params=params)

            # Используем OrderResult.from_api_response для парсинга ответа
            result = OrderResult.from_api_response(response)

            if result.success:
                logger.info(f"✓ Trading stop set for {symbol}")
                return result
            else:
                logger.error(f"Failed to set trading stop: {result.error}")
                return result

        except Exception as e:
            logger.error(f"Trading stop exception: {e}", exc_info=True)
            return OrderResult.error_result(str(e))

    def cancel_trading_stop(
        self,
        category: str,
        symbol: str,
        position_idx: int = 0,
    ) -> OrderResult:
        """
        Отменить Stop Loss и Take Profit на позиции.

        Это делается путем установки пустых значений через set_trading_stop.

        Args:
            category: Категория (linear, inverse, spot)
            symbol: Символ
            position_idx: 0 для one-way mode, 1 для Buy в hedge mode, 2 для Sell

        Returns:
            OrderResult с информацией о результате
        """
        params = {
            "category": category,
            "symbol": symbol,
            "positionIdx": position_idx,
            "stopLoss": "0",  # Установка 0 отменяет SL
            "takeProfit": "0",  # Установка 0 отменяет TP
        }

        logger.info(f"Cancelling trading stop for {symbol}")

        try:
            response = self.client.post("/v5/position/trading-stop", params=params)

            # Используем OrderResult.from_api_response для парсинга ответа
            result = OrderResult.from_api_response(response)

            if result.success:
                logger.info(f"✓ Trading stop cancelled for {symbol}")
                return result
            else:
                logger.error(f"Failed to cancel trading stop: {result.error}")
                return result

        except Exception as e:
            logger.error(f"Cancel trading stop exception: {e}", exc_info=True)
            return OrderResult.error_result(str(e))
