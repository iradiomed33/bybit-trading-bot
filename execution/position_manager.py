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

        partial_exit_levels: Optional[list] = None,  # [(R_level, percent_to_close), ...]

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

            "partial_exit_levels": partial_exit_levels or [
                (2.0, 0.50),  # Закрыть 50% на 2R
                (3.0, 0.25),  # Закрыть 25% на 3R
            ],

        }

        logger.info(
            f"Position registered: {side} {size} {symbol} @ {entry_price}, "
            f"SL={stop_loss}, partial_exits={len(self.active_positions[symbol]['partial_exit_levels'])} levels"
        )

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

        # 1. Проверяем partial exits (scale-out)
        self._check_partial_exits(symbol, current_price)

        # 2. Проверяем breakeven

        if not pos["breakeven_moved"]:

            self._check_breakeven(symbol, current_price)

        # 3. Проверяем trailing

        self._check_trailing(symbol, current_price)

        # 4. Проверяем time stop

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

            # ИСПРАВЛЕНО: Реально обновляем стоп на бирже через order_manager
            try:
                from decimal import Decimal
                # Обновляем Trading Stop на бирже
                result = self.order_manager.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    position_idx=0,
                    stop_loss=str(new_stop),
                    sl_trigger_by="LastPrice",
                )
                
                if result.success:
                    pos["stop_loss"] = new_stop
                    pos["breakeven_moved"] = True
                    logger.info(f"✓ Breakeven set on exchange: new SL = {new_stop}")
                else:
                    logger.error(f"Failed to set breakeven on exchange: {result.error}")
            except Exception as e:
                logger.error(f"Error setting breakeven: {e}", exc_info=True)
                # Fallback: обновляем локально для виртуального мониторинга
                pos["stop_loss"] = new_stop
                pos["breakeven_moved"] = True
                logger.warning(f"Breakeven set locally only (exchange update failed)")

    def _check_partial_exits(self, symbol: str, current_price: float):
        """
        Проверка условий для частичного закрытия позиции (scale-out).
        
        ТЗ 7.2: "Частичные тейки (scale-out)"
        
        Закрывает часть позиции при достижении определённых уровней прибыли (в R).
        Например: 50% на 2R, 25% на 3R.
        """
        pos = self.active_positions[symbol]
        
        entry = pos["entry_price"]
        stop_loss = pos["stop_loss"]
        current_size = pos["current_size"]
        
        # Расстояние до стопа (risk)
        risk_distance = abs(entry - stop_loss)
        if risk_distance == 0:
            return
        
        # Текущая прибыль (в R)
        if pos["side"] == "Buy":
            profit_distance = current_price - entry
        else:
            profit_distance = entry - current_price
        
        r_multiple = profit_distance / risk_distance
        
        # Проверяем каждый уровень partial exit
        for r_level, percent_to_close in pos["partial_exit_levels"]:
            # Проверяем, не был ли этот уровень уже закрыт
            already_exited = any(
                exit_info["r_level"] == r_level 
                for exit_info in pos["partial_exits"]
            )
            
            if already_exited:
                continue
            
            # Если достигли R-уровня, закрываем часть позиции
            if r_multiple >= r_level:
                # Рассчитываем количество для закрытия
                qty_to_close = current_size * percent_to_close
                
                if qty_to_close < 0.00001:  # Минимальный размер
                    logger.debug(f"Partial exit qty too small: {qty_to_close}")
                    continue
                
                logger.info(
                    f"🎯 Partial exit triggered for {symbol}: "
                    f"R={r_multiple:.2f} >= {r_level}R, "
                    f"closing {percent_to_close*100:.0f}% ({qty_to_close:.6f})"
                )
                
                # Выполняем частичное закрытие через order_manager
                try:
                    close_side = "Sell" if pos["side"] == "Buy" else "Buy"
                    
                    result = self.order_manager.create_order(
                        category="linear",
                        symbol=symbol,
                        side=close_side,
                        order_type="Market",
                        qty=float(qty_to_close),
                    )
                    
                    if result.success:
                        # Обновляем размер позиции
                        new_size = current_size - qty_to_close
                        pos["current_size"] = new_size
                        
                        # Записываем информацию о partial exit
                        pos["partial_exits"].append({
                            "r_level": r_level,
                            "percent": percent_to_close,
                            "qty_closed": qty_to_close,
                            "price": current_price,
                            "timestamp": time.time(),
                        })
                        
                        logger.info(
                            f"✓ Partial exit executed: {qty_to_close:.6f} @ {current_price:.2f}, "
                            f"remaining size: {new_size:.6f}"
                        )
                    else:
                        logger.error(f"Partial exit failed: {result.error}")
                        
                except Exception as e:
                    logger.error(f"Error executing partial exit: {e}", exc_info=True)

    def _check_trailing(self, symbol: str, current_price: float):
        """
        Проверка трейлинг стопа с синхронизацией на бирже.
        
        УЛУЧШЕНО: Теперь реально обновляет SL на бирже через Trading Stop API.
        """

        pos = self.active_positions[symbol]

        offset_percent = pos["trailing_offset_percent"]

        if pos["side"] == "Buy":

            # Long: трейлим от highest

            trailing_stop = pos["highest_price"] * (1 - offset_percent / 100)

            # Двигаем стоп вверх если trailing_stop выше текущего стопа

            if trailing_stop > pos["stop_loss"]:
                old_stop = pos["stop_loss"]

                logger.info(

                    f"Trailing stop updated: {symbol} "

                    f"SL {old_stop:.2f} -> {trailing_stop:.2f}"

                )

                # УЛУЧШЕНО: Обновляем SL на бирже
                self._update_stop_on_exchange(symbol, trailing_stop)

                pos["stop_loss"] = trailing_stop

        else:

            # Short: трейлим от lowest

            trailing_stop = pos["lowest_price"] * (1 + offset_percent / 100)

            if trailing_stop < pos["stop_loss"]:
                old_stop = pos["stop_loss"]

                logger.info(

                    f"Trailing stop updated: {symbol} "

                    f"SL {old_stop:.2f} -> {trailing_stop:.2f}"

                )

                # УЛУЧШЕНО: Обновляем SL на бирже
                self._update_stop_on_exchange(symbol, trailing_stop)

                pos["stop_loss"] = trailing_stop

    def _check_time_stop(self, symbol: str, current_price: float):
        """Проверка тайм-стопа (закрыть если не движется)"""

        pos = self.active_positions[symbol]

        time_limit = pos["time_stop_minutes"] * 60  # в секундах

        elapsed = time.time() - pos["entry_time"]

        if elapsed > time_limit:

            logger.warning(f"⏱️ Time stop triggered for {symbol}: {elapsed / 60:.0f} minutes elapsed")

            # ИСПРАВЛЕНО: Реально закрываем позицию через order_manager
            try:
                # Создаём противоположный Market ордер для закрытия
                close_side = "Sell" if pos["side"] == "Buy" else "Buy"
                close_qty = pos["current_size"]
                
                logger.info(f"Closing {symbol} position due to time stop: {close_side} {close_qty}")
                
                result = self.order_manager.create_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    order_type="Market",
                    qty=float(close_qty),
                )
                
                if result.success:
                    logger.info(f"✓ Time stop executed: position closed at ~{current_price}")
                    self.close_position(symbol, reason="time_stop")
                else:
                    logger.error(f"Failed to close position on time stop: {result.error}")
            except Exception as e:
                logger.error(f"Error executing time stop: {e}", exc_info=True)

    def _update_stop_on_exchange(self, symbol: str, new_stop_loss: float) -> bool:
        """
        Обновить Stop Loss на бирже через Trading Stop API.
        
        Используется для синхронизации trailing stop с биржей.
        
        Args:
            symbol: Символ
            new_stop_loss: Новая цена SL
            
        Returns:
            True если обновление успешно
        """
        try:
            result = self.order_manager.set_trading_stop(
                category="linear",
                symbol=symbol,
                position_idx=0,
                stop_loss=str(new_stop_loss),
                sl_trigger_by="LastPrice",
            )
            
            if result.success:
                logger.info(f"✓ Trailing stop synced to exchange: {symbol} SL={new_stop_loss:.2f}")
                return True
            else:
                logger.warning(f"Failed to sync trailing stop to exchange: {result.error}")
                return False
                
        except Exception as e:
            logger.error(f"Error syncing trailing stop to exchange: {e}", exc_info=True)
            return False

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
