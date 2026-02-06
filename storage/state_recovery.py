"""

State recovery: восстановление состояния бота после рестарта.


При старте бота:

1. Подтягиваем позиции/ордера с биржи

2. Сверяем с локальным состоянием в БД

3. Синхронизируем расхождения

"""


from typing import Dict, Any

from storage.database import Database

from exchange.account import AccountClient

from logger import setup_logger


logger = setup_logger(__name__)


class StateRecovery:

    """Сервис восстановления состояния"""

    def __init__(self, db: Database, account_client: AccountClient):

        self.db = db

        self.account = account_client

        logger.info("StateRecovery initialized")

    def recover_state(self, category: str = "linear", symbol: str = None) -> Dict[str, Any]:
        """

        Восстановить состояние: подтянуть позиции/ордера с биржи и сверить с БД.


        Args:

            category: Категория инструментов

            symbol: Конкретный символ (опционально, для linear требуется указывать)


        Returns:

            Словарь с результатами восстановления

        """

        logger.info("=== Starting state recovery ===")

        result = {

            "positions_synced": 0,

            "orders_synced": 0,

            "discrepancies": [],

            "success": True,

        }

        try:

            # 1. Получаем позиции с биржи

            logger.info("Fetching positions from exchange...")

            positions_resp = self.account.get_positions(category, symbol)

            if positions_resp.get("retCode") == 0:

                exchange_positions = positions_resp.get("result", {}).get("list", [])

                logger.info(f"Found {len(exchange_positions)} positions on exchange")

                for pos in exchange_positions:

                    # Сохраняем snapshot в БД

                    if float(pos.get("size", 0)) > 0:  # Только если есть позиция

                        # Обработка пустых значений в полях

                        try:

                            liq_price = float(pos.get("liqPrice") or 0)

                        except (ValueError, TypeError):

                            liq_price = 0

                        self.db.save_position_snapshot(

                            {

                                "symbol": pos["symbol"],

                                "side": pos["side"],

                                "size": float(pos["size"]),

                                "entry_price": (

                                    float(pos.get("avgPrice", 0)) if pos.get("avgPrice") else 0

                                ),

                                "mark_price": (

                                    float(pos.get("markPrice", 0)) if pos.get("markPrice") else 0

                                ),

                                "liquidation_price": liq_price,

                                "leverage": (

                                    float(pos.get("leverage", 0)) if pos.get("leverage") else 0

                                ),

                                "unrealised_pnl": (

                                    float(pos.get("unrealisedPnl", 0))

                                    if pos.get("unrealisedPnl")

                                    else 0

                                ),

                                "realised_pnl": (

                                    float(pos.get("cumRealisedPnl", 0))

                                    if pos.get("cumRealisedPnl")

                                    else 0

                                ),

                                "metadata": pos,

                            }

                        )

                        result["positions_synced"] += 1

            # 2. Получаем открытые ордера с биржи

            logger.info("Fetching open orders from exchange...")

            orders_resp = self.account.get_open_orders(category, symbol)

            if orders_resp.get("retCode") == 0:

                exchange_orders = orders_resp.get("result", {}).get("list", [])

                logger.info(f"Found {len(exchange_orders)} open orders on exchange")

                # Получаем локальные активные ордера

                local_orders = self.db.get_active_orders()

                local_order_ids = {order["order_id"] for order in local_orders}

                exchange_order_ids = {order["orderId"] for order in exchange_orders}

                # Сохраняем ордера с биржи

                for order in exchange_orders:

                    self.db.save_order(

                        {

                            "order_id": order["orderId"],

                            "order_link_id": order.get("orderLinkId"),

                            "symbol": order["symbol"],

                            "side": order["side"],

                            "order_type": order["orderType"],

                            "price": float(order.get("price", 0)),

                            "qty": float(order["qty"]),

                            "filled_qty": float(order.get("cumExecQty", 0)),

                            "status": order["orderStatus"],

                            "time_in_force": order.get("timeInForce"),

                            "created_time": float(order.get("createdTime", 0)),

                            "updated_time": float(order.get("updatedTime", 0)),

                            "metadata": order,

                        }

                    )

                    result["orders_synced"] += 1

                # Проверяем расхождения

                missing_in_local = exchange_order_ids - local_order_ids

                missing_on_exchange = local_order_ids - exchange_order_ids

                if missing_in_local:

                    result["discrepancies"].append(

                        f"Orders on exchange but not in local DB: {missing_in_local}"

                    )

                    logger.warning(f"Discrepancy: {len(missing_in_local)} orders not in local DB")

                if missing_on_exchange:

                    result["discrepancies"].append(

                        f"Orders in local DB but not on exchange: {missing_on_exchange}"

                    )

                    logger.warning(

                        f"Discrepancy: {len(missing_on_exchange)} orders not on exchange"

                    )

            logger.info("=== State recovery completed ===")

            logger.info(

                f"Synced: {result['positions_synced']} positions, {result['orders_synced']} orders"

            )

        except Exception as e:

            logger.error(f"State recovery failed: {e}", exc_info=True)

            result["success"] = False

            self.db.save_error("state_recovery", str(e))

        return result
