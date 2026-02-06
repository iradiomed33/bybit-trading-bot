"""

Детальное логирование сигналов для отладки.

Логирует ВСЕ сигналы (приняты и отклонены) с причинами.

"""


import logging

import json

from datetime import datetime

from pathlib import Path

from typing import Any, Optional, Dict, Iterable

from logging.handlers import RotatingFileHandler


class SignalLogger:

    """Специализированный логгер для сигналов торговли"""

    def __init__(self):

        self.log_dir = Path("logs")

        self.log_dir.mkdir(exist_ok=True)

        # Логгер для сигналов

        self.signal_logger = self._setup_signal_logger()

    def _setup_signal_logger(self) -> logging.Logger:
        """Настраивает логгер для сигналов"""

        logger = logging.getLogger("signals")

        logger.setLevel(logging.DEBUG)

        logger.handlers.clear()  # Очищаем существующие handlers

        # Формат

        formatter = logging.Formatter(

            fmt="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"

        )

        # Консоль

        console = logging.StreamHandler()

        console.setLevel(logging.INFO)

        console.setFormatter(formatter)

        logger.addHandler(console)

        # Файл signals_YYYY-MM-DD.log с ротацией

        filename = self.log_dir / f"signals_{datetime.now().strftime('%Y-%m-%d')}.log"

        file_handler = RotatingFileHandler(

            filename, maxBytes=50 * 1024 * 1024, backupCount=10, encoding="utf-8"  # 50MB

        )

        file_handler.setLevel(logging.DEBUG)

        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        return logger

    def log_signal_generated(

        self,

        strategy_name: str,

        symbol: str,

        direction: str,  # "BUY" или "SELL"

        confidence: float,

        price: float,

        timestamp: datetime = None,

        reasons: Optional[Iterable[str]] = None,

        values: Optional[Dict[str, Any]] = None,

        **kwargs,

    ):
        """Логирует когда стратегия сгенерировала сигнал"""

        self._log_signal_decision(

            stage="GENERATED",

            strategy_name=strategy_name,

            symbol=symbol,

            direction=direction,

            confidence=confidence,

            price=price,

            timestamp=timestamp,

            reasons=reasons,

            values=values,

            **kwargs,

        )

    def log_signal_accepted(

        self,

        strategy_name: str,

        symbol: str,

        direction: str,

        confidence: float,

        order_id: Optional[str] = None,

        reasons: Optional[Iterable[str]] = None,

        values: Optional[Dict[str, Any]] = None,

        **kwargs,

    ):
        """Логирует когда сигнал был принят и ордер создан"""

        self._log_signal_decision(

            stage="ACCEPTED",

            strategy_name=strategy_name,

            symbol=symbol,

            direction=direction,

            confidence=confidence,

            order_id=order_id,

            reasons=reasons,

            values=values,

            **kwargs,

        )

    def log_signal_rejected(

        self,

        strategy_name: str,

        symbol: str,

        direction: str,

        confidence: float,

        reason: Optional[str] = None,

        reasons: Optional[Iterable[str]] = None,

        values: Optional[Dict[str, Any]] = None,

        **details,

    ):
        """Логирует когда сигнал был отклонен с указанием причины"""

        if reason and not reasons:

            reasons = [reason]

        self._log_signal_decision(

            stage="REJECTED",

            strategy_name=strategy_name,

            symbol=symbol,

            direction=direction,

            confidence=confidence,

            reasons=reasons,

            values=values,

            **details,

        )

    def _log_signal_decision(

        self,

        stage: str,

        strategy_name: str,

        symbol: str,

        direction: str,

        confidence: float,

        timestamp: datetime = None,

        reasons: Optional[Iterable[str]] = None,

        values: Optional[Dict[str, Any]] = None,

        **details,

    ) -> None:

        ts = timestamp or datetime.now()

        normalized_reasons = list(reasons) if reasons else []

        reasons_str = (

            json.dumps(normalized_reasons, ensure_ascii=False) if normalized_reasons else "[]"

        )

        values_str = json.dumps(values, ensure_ascii=False) if values else "{}"

        details_str = json.dumps(details, ensure_ascii=False) if details else "{}"

        msg = (

            "✅ SIGNAL"

            if stage == "GENERATED"

            else (

                "✅ SIGNAL"

                if stage == "ACCEPTED"

                else "❌ SIGNAL" if stage == "REJECTED" else "ℹ️ SIGNAL"

            )

        )

        line = (

            f"{msg} | Stage={stage} | Strategy={strategy_name} | Symbol={symbol} | "

            f"Direction={direction} | Confidence={confidence:.2f} | "

            f"Reasons={reasons_str} | Values={values_str} | Details={details_str}"

        )

        if stage == "REJECTED":

            self.signal_logger.warning(line)

        elif stage == "ACCEPTED" or stage == "GENERATED":

            self.signal_logger.info(line)

        else:

            self.signal_logger.info(line)

    def log_filter_check(

        self,

        filter_name: str,

        symbol: str,

        passed: bool,

        value: Any = None,

        threshold: Any = None,

        **details,

    ):
        """Логирует результаты проверки фильтров"""

        status = "✅ PASS" if passed else "❌ FAIL"

        value_str = f" | Value={value}" if value is not None else ""

        threshold_str = f" | Threshold={threshold}" if threshold is not None else ""

        details_str = f" | {json.dumps(details)}" if details else ""

        msg = f"{status} | Filter={filter_name} | Symbol={symbol}{value_str}{threshold_str}{details_str}"

        log_level = logging.DEBUG if passed else logging.WARNING

        self.signal_logger.log(log_level, msg)

    def log_order_execution_start(

        self, symbol: str, direction: str, quantity: float, price: float, **details

    ):
        """Логирует попытку выполнить ордер"""

        details_str = json.dumps(details) if details else ""

        msg = (

            f"⏳ ORDER EXEC START | Symbol={symbol} | Direction={direction} | "

            f"Qty={quantity} | Price={price} | {details_str}"

        )

        self.signal_logger.info(msg)

    def log_order_execution_failed(

        self, symbol: str, direction: str, reason: str, error: str = None, **details

    ):
        """Логирует неудачное выполнение ордера"""

        error_str = f" | Error={error}" if error else ""

        details_str = f" | {json.dumps(details)}" if details else ""

        msg = (

            f"❌ ORDER EXEC FAILED | Symbol={symbol} | Direction={direction} | "

            f"Reason={reason}{error_str}{details_str}"

        )

        self.signal_logger.error(msg)

    def log_order_execution_success(

        self,

        symbol: str,

        direction: str,

        order_id: str,

        filled_qty: float,

        filled_price: float,

        **details,

    ):
        """Логирует успешное выполнение ордера"""

        details_str = json.dumps(details) if details else ""

        msg = (

            f"✅ ORDER EXEC SUCCESS | Symbol={symbol} | Direction={direction} | "

            f"OrderID={order_id} | FilledQty={filled_qty} | FilledPrice={filled_price} | {details_str}"

        )

        self.signal_logger.info(msg)

    def log_position_update(

        self,

        symbol: str,

        direction: str,

        size: float,

        entry_price: float,

        current_price: float,

        pnl: float,

        **details,

    ):
        """Логирует обновление позиции"""

        details_str = json.dumps(details) if details else ""

        msg = (

            f"📊 POSITION | Symbol={symbol} | Direction={direction} | "

            f"Size={size} | EntryPrice={entry_price} | CurrentPrice={current_price} | "

            f"PnL={pnl} | {details_str}"

        )

        self.signal_logger.debug(msg)

    def log_debug_info(self, category: str, **info):
        """Логирует отладочную информацию"""

        info_str = json.dumps(info, default=str)

        msg = f"🔍 DEBUG | Category={category} | {info_str}"

        self.signal_logger.debug(msg)


# Глобальный экземпляр

_signal_logger_instance: Optional[SignalLogger] = None


def get_signal_logger() -> SignalLogger:
    """Получить или создать глобальный экземпляр логгера сигналов"""

    global _signal_logger_instance

    if _signal_logger_instance is None:

        _signal_logger_instance = SignalLogger()

    return _signal_logger_instance
