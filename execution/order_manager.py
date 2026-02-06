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

    ) -> Dict[str, Any]:
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

            Результат создания ордера


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

            if response.get("retCode") == 0:

                result = response.get("result", {})

                order_id = result.get("orderId")

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

                        "metadata": result,

                    }

                )

                return {"success": True, "order_id": order_id, "order_link_id": order_link_id}

            else:

                error_msg = response.get("retMsg", "Unknown error")

                logger.error(f"Order creation failed: {error_msg}")

                return {"success": False, "error": error_msg}

        except Exception as e:

            logger.error(f"Order creation exception: {e}", exc_info=True)

            self.db.save_error("order_creation", str(e), metadata={"params": params})

            return {"success": False, "error": str(e)}

    def cancel_order(

        self,

        category: str,

        symbol: str,

        order_id: Optional[str] = None,

        order_link_id: Optional[str] = None,

    ) -> Dict[str, Any]:
        """

        Отменить ордер.


        Args:

            category: Категория

            symbol: Символ

            order_id: ID ордера (или order_link_id)

            order_link_id: Клиентский ID


        Returns:

            Результат отмены


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

            if response.get("retCode") == 0:

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

                return {"success": True}

            else:

                error_msg = response.get("retMsg", "Unknown error")

                logger.error(f"Order cancellation failed: {error_msg}")

                return {"success": False, "error": error_msg}

        except Exception as e:

            logger.error(f"Order cancellation exception: {e}", exc_info=True)

            return {"success": False, "error": str(e)}

    def cancel_all_orders(self, category: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """

        Отменить все ордера (для kill switch).


        Args:

            category: Категория

            symbol: Символ (опционально, если не указан - отменяются все)


        Returns:

            Результат отмены


        Docs: https://bybit-exchange.github.io/docs/v5/order/cancel-all

        """

        params = {"category": category}

        if symbol:

            params["symbol"] = symbol

        logger.warning(f"Cancelling ALL orders for {symbol or 'all symbols'}")

        try:

            response = self.client.post("/v5/order/cancel-all", params=params)

            if response.get("retCode") == 0:

                result = response.get("result", {})

                logger.info(f"✓ All orders cancelled: {result}")

                return {"success": True, "result": result}

            else:

                error_msg = response.get("retMsg", "Unknown error")

                logger.error(f"Cancel all failed: {error_msg}")

                return {"success": False, "error": error_msg}

        except Exception as e:

            logger.error(f"Cancel all exception: {e}", exc_info=True)

            return {"success": False, "error": str(e)}
