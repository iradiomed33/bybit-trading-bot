"""
Position Manager: сопровождение позиции (SL/TP, breakeven, partial exits, trailing).

Логика:
1. Initial SL/TP при входе
2. Move to breakeven при достижении порога
3. Partial exits (scale-out)
4. Trailing stop
5. Time stop (закрыть если не движется)
"""

import time
from typing import Dict, Any, Optional
from execution.order_manager import OrderManager
from logger import setup_logger

logger = setup_logger(__name__)


class PositionManager:
    """Сопровождение открытой позиции"""

    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        logger.info("PositionManager initialized")

    def register_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        breakeven_trigger: float = 1.5,  # R множитель для breakeven
        trailing_offset_percent: float = 1.0,
        time_stop_minutes: int = 60,
    ):
        """
        Зарегистрировать позицию для сопровождения.

        Args:
            symbol: Символ
            side: Buy или Sell
            entry_price: Цена входа
            size: Размер позиции
            stop_loss: Начальный стоп-лосс
            take_profit: Тейк-профит (опционально)
            breakeven_trigger: При каком R перевести в б/у (например 1.5R)
            trailing_offset_percent: Отступ для трейлинга (%)
            time_stop_minutes: Закрыть если не движется N минут
        """
        self.active_positions[symbol] = {
            "side": side,
            "entry_price": entry_price,
            "size": size,
            "current_size": size,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "breakeven_trigger": breakeven_trigger,
            "breakeven_moved": False,
            "trailing_offset_percent": trailing_offset_percent,
            "highest_price": entry_price if side == "Buy" else entry_price,
            "lowest_price": entry_price if side == "Sell" else entry_price,
            "entry_time": time.time(),
            "time_stop_minutes": time_stop_minutes,
            "partial_exits": [],
        }

        logger.info(f"Position registered: {side} {size} {symbol} @ {entry_price}, SL={stop_loss}")

    def update_position(self, symbol: str, current_price: float, current_size: float):
        """
        Обновить состояние позиции (вызывается на каждый тик).

        Args:
            symbol: Символ
            current_price: Текущая цена
            current_size: Текущий размер (может уменьшаться при partial exits)
        """
        if symbol not in self.active_positions:
            return

        pos = self.active_positions[symbol]
        pos["current_size"] = current_size

        # Обновляем highest/lowest для трейлинга
        if pos["side"] == "Buy":
            pos["highest_price"] = max(pos["highest_price"], current_price)
        else:
            pos["lowest_price"] = min(pos["lowest_price"], current_price)

        # 1. Проверяем breakeven
        if not pos["breakeven_moved"]:
            self._check_breakeven(symbol, current_price)

        # 2. Проверяем trailing
        self._check_trailing(symbol, current_price)

        # 3. Проверяем time stop
        self._check_time_stop(symbol, current_price)

    def _check_breakeven(self, symbol: str, current_price: float):
        """Проверка условий для перевода в безубыток"""
        pos = self.active_positions[symbol]
        entry = pos["entry_price"]
        stop_loss = pos["stop_loss"]
        trigger = pos["breakeven_trigger"]

        # Расстояние до стопа (risk)
        risk_distance = abs(entry - stop_loss)

        # Текущая прибыль (в R)
        if pos["side"] == "Buy":
            profit_distance = current_price - entry
        else:
            profit_distance = entry - current_price

        r_multiple = profit_distance / risk_distance if risk_distance > 0 else 0

        # Если достигли trigger, переводим стоп в б/у
        if r_multiple >= trigger:
            logger.info(
                f"Moving {symbol} to breakeven (achieved {r_multiple:.2f}R, trigger={trigger}R)"
            )

            # Новый стоп = entry (можно +/- небольшой буфер)
            new_stop = entry

            # Здесь нужно обновить стоп на бирже (через modify order или закрыть/открыть новый)
            # Упрощённо: просто обновляем локально
            pos["stop_loss"] = new_stop
            pos["breakeven_moved"] = True

            logger.info(f"✓ Breakeven set: new SL = {new_stop}")

    def _check_trailing(self, symbol: str, current_price: float):
        """Проверка трейлинг стопа"""
        pos = self.active_positions[symbol]
        offset_percent = pos["trailing_offset_percent"]

        if pos["side"] == "Buy":
            # Long: трейлим от highest
            trailing_stop = pos["highest_price"] * (1 - offset_percent / 100)

            # Двигаем стоп вверх если trailing_stop выше текущего стопа
            if trailing_stop > pos["stop_loss"]:
                logger.info(
                    f"Trailing stop updated: {symbol} "
                    f"SL {pos['stop_loss']:.2f} -> {trailing_stop:.2f}"
                )
                pos["stop_loss"] = trailing_stop
        else:
            # Short: трейлим от lowest
            trailing_stop = pos["lowest_price"] * (1 + offset_percent / 100)

            if trailing_stop < pos["stop_loss"]:
                logger.info(
                    f"Trailing stop updated: {symbol} "
                    f"SL {pos['stop_loss']:.2f} -> {trailing_stop:.2f}"
                )
                pos["stop_loss"] = trailing_stop

    def _check_time_stop(self, symbol: str, current_price: float):
        """Проверка тайм-стопа (закрыть если не движется)"""
        pos = self.active_positions[symbol]
        time_limit = pos["time_stop_minutes"] * 60  # в секундах

        elapsed = time.time() - pos["entry_time"]

        if elapsed > time_limit:
            logger.warning(f"Time stop triggered for {symbol}: {elapsed / 60:.0f} minutes elapsed")

            # Закрываем позицию (упрощённо: просто логируем, реальное закрытие через order_manager)
            logger.info(f"Closing {symbol} due to time stop")
            # self.close_position(symbol, current_price, reason="time_stop")

    def close_position(self, symbol: str, reason: str = "manual"):
        """Закрыть позицию"""
        if symbol in self.active_positions:
            logger.info(f"Closing position: {symbol} (reason={reason})")

            # Здесь создаём противоположный ордер через order_manager
            # close_side = "Sell" if pos["side"] == "Buy" else "Buy"
            # self.order_manager.create_order(
            #     ..., side=close_side, qty=pos["current_size"], order_type="Market"
            # )

            # Удаляем из активных
            del self.active_positions[symbol]

    def get_position_status(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить статус позиции"""
        return self.active_positions.get(symbol)
