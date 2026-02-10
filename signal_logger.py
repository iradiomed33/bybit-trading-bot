"""

Детальное логирование сигналов для отладки.

Логирует ВСЕ сигналы (приняты и отклонены) с причинами в структурированном JSON формате.

"""


import logging

import json

from datetime import datetime

from pathlib import Path

from typing import Any, Optional, Dict, Iterable, List

from logging.handlers import RotatingFileHandler


class SignalLogger:

    """Специализированный логгер для сигналов торговли с поддержкой структурированных событий"""

    def __init__(self):

        self.log_dir = Path("logs")

        self.log_dir.mkdir(exist_ok=True)

        # Логгер для сигналов

        self.signal_logger = self._setup_signal_logger()
        
        # Event bus для WebSocket broadcast (устанавливается извне)
        self.event_callback = None

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

        metrics: Optional[Dict[str, Any]] = None,

        filters: Optional[List[Dict[str, Any]]] = None,

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

            metrics=metrics,

            filters=filters,

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

        metrics: Optional[Dict[str, Any]] = None,

        filters: Optional[List[Dict[str, Any]]] = None,

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

            metrics=metrics,

            filters=filters,

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

        metrics: Optional[Dict[str, Any]] = None,

        filters: Optional[List[Dict[str, Any]]] = None,

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

            metrics=metrics,

            filters=filters,

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

        metrics: Optional[Dict[str, Any]] = None,

        filters: Optional[List[Dict[str, Any]]] = None,

        **details,

    ) -> None:
        """
        Логирует решение по сигналу в структурированном JSON формате.
        
        Required:
        - stage: GENERATED|ACCEPTED|REJECTED
        - strategy_name: имя стратегии
        - symbol: торговая пара
        - direction: LONG|SHORT|NONE
        - confidence: 0..1
        
        Optional:
        - reasons: список причин (для rejected/warnings)
        - values: значения переменных {key: value}
        - metrics: метрики рынка/стратегии {atr, spread, adx, etc}
        - filters: результаты фильтров [{name, pass, value, threshold}]
        - **details: дополнительные поля
        """

        ts = timestamp or datetime.now()
        
        # Создаем структурированное событие
        event = self._create_event(
            ts=ts,
            level="SIGNAL",
            category="signal",
            symbol=symbol,
            message=self._create_signal_message(stage, strategy_name, reasons),
            stage=stage,
            strategy=strategy_name,
            direction=direction,
            confidence=confidence,
            reasons=list(reasons) if reasons else [],
            values=values,
            metrics=metrics,
            filters=filters,
            **details
        )
        
        # Логируем как JSON строку
        log_line = json.dumps(event, ensure_ascii=False)

        # Уровень логирования по стадии
        if stage == "REJECTED":
            self.signal_logger.warning(log_line)
        elif stage == "ACCEPTED" or stage == "GENERATED":
            self.signal_logger.info(log_line)
        else:
            self.signal_logger.info(log_line)
        
        # Broadcast через event callback if set
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception as e:
                self.signal_logger.error(f"Failed to broadcast event: {e}")

    def _create_event(
        self,
        ts: datetime,
        level: str,
        category: str,
        symbol: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Создает структурированное событие логирования.
        
        Required fields:
        - ts: timestamp
        - level: DEBUG|INFO|WARN|ERROR|SIGNAL|EXEC|RISK
        - category: market_analysis|strategy_analysis|signal|execution|risk|kill_switch|system
        - symbol: торговая пара
        - message: короткое описание
        
        Optional fields (через kwargs):
        - stage, strategy, direction, confidence, reasons, values, metrics, filters, details, etc.
        """
        event = {
            "ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "category": category,
            "symbol": symbol,
            "message": message
        }
        
        # Добавляем опциональные поля (только если они not None и not empty)
        for key, value in kwargs.items():
            if value is not None:
                # Пропускаем пустые списки/словари
                if isinstance(value, (list, dict)) and not value:
                    continue
                event[key] = value
        
        return event
    
    def _create_signal_message(self, stage: str, strategy: str, reasons: Optional[List[str]]) -> str:
        """Создает короткое текстовое сообщение для события сигнала"""
        if stage == "GENERATED":
            return f"Signal generated by {strategy}"
        elif stage == "ACCEPTED":
            return f"Signal accepted from {strategy}"
        elif stage == "REJECTED":
            reason_text = reasons[0] if reasons else "unknown"
            return f"Rejected by {reason_text}"
        return f"Signal {stage.lower()}"

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
        self, 
        symbol: str, 
        direction: str, 
        quantity: float, 
        price: float, 
        **details
    ):
        """Логирует попытку выполнить ордер в структурированном формате"""
        event = self._create_event(
            ts=datetime.now(),
            level="EXEC",
            category="execution",
            symbol=symbol,
            message=f"Order execution started: {direction}",
            stage="PLACING",
            direction=direction,
            details={"qty": quantity, "price": price, **details}
        )
        self.signal_logger.info(json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass

    def log_order_execution_failed(

        self, symbol: str, direction: str, reason: str, error: str = None, **details

    ):
        """Логирует неудачное выполнение ордера в структурированном формате"""
        event = self._create_event(
            ts=datetime.now(),
            level="ERROR",
            category="execution",
            symbol=symbol,
            message=f"Order execution failed: {reason}",
            stage="FAILED",
            direction=direction,
            reasons=[reason],
            details={"error": error, **details} if error else details
        )
        self.signal_logger.error(json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass

    def log_order_execution_success(

        self,

        symbol: str,

        direction: str,

        order_id: str,

        filled_qty: float,

        filled_price: float,

        **details,

    ):
        """Логирует успешное выполнение ордера в структурированном формате"""
        event = self._create_event(
            ts=datetime.now(),
            level="EXEC",
            category="execution",
            symbol=symbol,
            message=f"Order executed successfully",
            stage="FILLED",
            direction=direction,
            details={"order_id": order_id, "filled_qty": filled_qty, "filled_price": filled_price, **details}
        )
        self.signal_logger.info(json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass

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
        """Логирует отладочную информацию в структурированном формате"""
        event = self._create_event(
            ts=datetime.now(),
            level="DEBUG",
            category="system",
            symbol=info.get("symbol", "N/A"),
            message=f"Debug: {category}",
            details={"category_name": category, **info}
        )
        self.signal_logger.debug(json.dumps(event, ensure_ascii=False))
    
    def log_market_analysis(
        self,
        symbol: str,
        message: str,
        metrics: Optional[Dict[str, Any]] = None,
        **details
    ):
        """
        Логирует анализ рынка (market_analysis category).
        Используется когда бот анализирует рынок но не генерирует сигналы.
        
        Example:
            log_market_analysis(
                symbol="ETHUSDT",
                message="No strategy triggered",
                metrics={"close": 102947.67, "atr": 4139.10, "volume": 123456}
            )
        """
        event = self._create_event(
            ts=datetime.now(),
            level="DEBUG",
            category="market_analysis",
            symbol=symbol,
            message=message,
            metrics=metrics,
            **details
        )
        self.signal_logger.debug(json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass
    
    def log_strategy_analysis(
        self,
        symbol: str,
        strategy: str,
        message: str,
        regime: Optional[str] = None,
        active_strategies: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        **details
    ):
        """
        Логирует анализ стратегии (strategy_analysis category).
        Показывает какие стратегии активны, режим рынка и почему стратегия не сработала.
        
        Example:
            log_strategy_analysis(
                symbol="ETHUSDT",
                strategy="MetaLayer",
                message="Market regime check",
                regime="trending",
                active_strategies=["TrendPullback", "Breakout"],
                metrics={"adx": 39.89, "atr_%": 12.53, "mtf_score": 0.45},
                filters=[
                    {"name": "mtf_filter", "pass": False, "value": 0.45, "threshold": 0.65},
                    {"name": "volume_filter", "pass": True, "value": 4.21, "threshold": 2.0}
                ]
            )
        """
        event = self._create_event(
            ts=datetime.now(),
            level="DEBUG",
            category="strategy_analysis",
            symbol=symbol,
            message=message,
            strategy=strategy,
            regime=regime,
            active_strategies=active_strategies,
            metrics=metrics,
            filters=filters,
            **details
        )
        self.signal_logger.debug(json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass
    
    def log_risk_event(
        self,
        symbol: str,
        message: str,
        level: str = "WARN",
        reasons: Optional[List[str]] = None,
        values: Optional[Dict[str, Any]] = None,
        **details
    ):
        """
        Логирует события риск-менеджмента (risk category).
        
        Example:
            log_risk_event(
                symbol="ETHUSDT",
                message="Position size exceeded limit",
                level="WARN",
                reasons=["max_notional_exceeded"],
                values={"current_notional": 55000, "max_notional": 50000}
            )
        """
        event = self._create_event(
            ts=datetime.now(),
            level=level,
            category="risk",
            symbol=symbol,
            message=message,
            reasons=reasons,
            values=values,
            **details
        )
        log_level = getattr(logging, level, logging.INFO)
        self.signal_logger.log(log_level, json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass
    
    def log_kill_switch_event(
        self,
        symbol: str,
        message: str,
        triggered: bool = False,
        reasons: Optional[List[str]] = None,
        **details
    ):
        """
        Логирует события kill switch (kill_switch category).
        
        Example:
            log_kill_switch_event(
                symbol="ETHUSDT",
                message="Kill switch activated",
                triggered=True,
                reasons=["max_consecutive_errors", "daily_loss_limit"],
                details={"consecutive_errors": 5, "daily_loss_pct": 6.2}
            )
        """
        event = self._create_event(
            ts=datetime.now(),
            level="CRITICAL" if triggered else "WARN",
            category="kill_switch",
            symbol=symbol,
            message=message,
            triggered=triggered,
            reasons=reasons,
            **details
        )
        log_level = logging.CRITICAL if triggered else logging.WARNING
        self.signal_logger.log(log_level, json.dumps(event, ensure_ascii=False))
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass


# Глобальный экземпляр

_signal_logger_instance: Optional[SignalLogger] = None


def get_signal_logger() -> SignalLogger:
    """Получить или создать глобальный экземпляр логгера сигналов"""

    global _signal_logger_instance

    if _signal_logger_instance is None:

        _signal_logger_instance = SignalLogger()

    return _signal_logger_instance
